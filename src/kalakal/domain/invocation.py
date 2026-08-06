"""Model-invocation, selector metadata, and selection/abstention output
(§6.2.10, §6.2.13, §5.2).

Two invocation shapes keep the record truthful: the ``not_invoked`` shape has
no model fields at all, so model identity, responses, tokens, and tool calls
can never be fabricated or dummy-valued for a run that made no model call.
:class:`DeterministicSelectorMetadata` identifies the test-only deterministic
selector (§5.10) the same way — structurally, with no model fields to fake.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from kalakal.domain.primitives import (
    AbstainReasonCode,
    AgentToolName,
    Identifier,
    MarketSide,
    MediumText,
    StrictFalse,
    StrictModel,
    StrictTrue,
    TokenCount,
    UtcDatetime,
    VersionStr,
)

# §5.3: at most 4 model turns plus one repair/retry for a single model
# series, so no per-model series can exceed 5 calls.
MAX_CALLS_PER_MODEL = 5
# §5.3: the budget-guarded fallback shares the same turn budget; 6 total
# calls is a conservative hard maximum across primary and fallback.
MAX_TOTAL_MODEL_CALLS = 6


class ModelCallUsage(StrictModel):
    """Per-model token usage (§5.9 requires per-model counts on fallback)."""

    model_id: Identifier
    call_count: Annotated[int, Field(ge=1, le=MAX_CALLS_PER_MODEL)]
    input_tokens: TokenCount
    output_tokens: TokenCount


class ToolCallRecord(StrictModel):
    """One read-only agent tool call (the closed §5.1 tool surface)."""

    tool_name: AgentToolName
    market_id: Identifier | None = None
    called_at: UtcDatetime

    @model_validator(mode="after")
    def _check_argument(self) -> ToolCallRecord:
        if self.tool_name == "list_candidate_markets":
            if self.market_id is not None:
                raise ValueError("list_candidate_markets takes no market_id")
        elif self.market_id is None:
            raise ValueError(f"{self.tool_name} requires a market_id")
        return self


class ModelInvocationInvoked(StrictModel):
    """Metadata for a run in which the model actually ran."""

    invocation_status: Literal["invoked"]
    invocation_id: Identifier
    model_id: Identifier
    prompt_version: VersionStr
    response_ids: Annotated[
        tuple[Identifier, ...],
        Field(min_length=1, max_length=MAX_TOTAL_MODEL_CALLS),
    ]
    usage: Annotated[tuple[ModelCallUsage, ...], Field(min_length=1, max_length=4)]
    fallback_used: bool
    fallback_model_id: Identifier | None = None
    fallback_reason: MediumText | None = None
    tool_calls: Annotated[tuple[ToolCallRecord, ...], Field(max_length=8)]

    @model_validator(mode="after")
    def _check_consistency(self) -> ModelInvocationInvoked:
        if len(set(self.response_ids)) != len(self.response_ids):
            raise ValueError("response_ids must be unique")
        usage_ids = [entry.model_id for entry in self.usage]
        if len(set(usage_ids)) != len(usage_ids):
            raise ValueError("usage entries must have unique model IDs")
        if self.model_id not in usage_ids:
            raise ValueError("usage must include the primary model_id")
        if self.fallback_used:
            if self.fallback_model_id is None or self.fallback_reason is None:
                raise ValueError(
                    "fallback_used requires fallback_model_id and fallback_reason"
                )
            if self.fallback_model_id == self.model_id:
                raise ValueError(
                    "the fallback model must differ from the primary model"
                )
            if self.fallback_model_id not in usage_ids:
                raise ValueError("usage must include the fallback model_id")
            allowed_models = {self.model_id, self.fallback_model_id}
        else:
            if self.fallback_model_id is not None or self.fallback_reason is not None:
                raise ValueError(
                    "fallback metadata must be absent when fallback_used is false"
                )
            allowed_models = {self.model_id}
        unrelated = set(usage_ids) - allowed_models
        if unrelated:
            raise ValueError(
                "usage must name only the models of this invocation; "
                f"unrelated: {sorted(unrelated)}"
            )
        total_calls = sum(entry.call_count for entry in self.usage)
        if total_calls > MAX_TOTAL_MODEL_CALLS:
            raise ValueError(
                f"total model calls must not exceed {MAX_TOTAL_MODEL_CALLS}, "
                f"got {total_calls}"
            )
        # A failed attempt has no response ID, so fewer responses than calls
        # is legitimate; more responses than calls is not.
        if len(self.response_ids) > total_calls:
            raise ValueError(
                "response_ids cannot outnumber the total call count "
                f"({len(self.response_ids)} > {total_calls})"
            )
        return self


class ModelInvocationNotInvoked(StrictModel):
    """Metadata for a run that made no model call: no model fields exist."""

    invocation_status: Literal["not_invoked"]


ModelInvocationMetadata = Annotated[
    ModelInvocationInvoked | ModelInvocationNotInvoked,
    Field(discriminator="invocation_status"),
]


class DeterministicSelectorMetadata(StrictModel):
    """Identity of the test-only deterministic selector (§5.10, §6.2.13).

    Required on every ``deterministic_stub``-sourced record and forbidden on
    every other source. It is structurally non-model: no model ID, prompt
    version, response IDs, token counts, fallback data, or tool-call fields
    exist, so a deterministic run can never dress up as a model invocation.
    """

    selector_id: Identifier
    selector_version: VersionStr
    test_only: StrictTrue


class MarketSelection(StrictModel):
    """The validated selection of one candidate market and side.

    Produced by whichever selector composition ran (the bounded agent or the
    test-only deterministic stub). It deliberately carries no source field:
    source attribution is owned by the application/record layer (§6.2.10), so
    a model can never claim its own trust source.
    """

    abstained: StrictFalse
    selected_market_id: Identifier
    selected_side: MarketSide


class Abstention(StrictModel):
    """The validated abstention output; it can never name a selected market."""

    abstained: StrictTrue
    selected_market_id: None = None
    abstain_reason_code: AbstainReasonCode
