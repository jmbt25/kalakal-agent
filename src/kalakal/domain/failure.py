"""RunFailure contract (architecture.md §6.2.11).

Failures and timeouts persist a RunFailure — never a partial DecisionRecord.
Model-attempt metadata stays truthful: a run with no successful model
response records typed failed attempts, never a fabricated invocation or
dummy response IDs.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from kalakal.domain.invocation import ModelInvocationInvoked
from kalakal.domain.primitives import (
    ActiveRunState,
    FailureClassification,
    FailureReasonCode,
    Identifier,
    StrictModel,
    TokenCount,
    UtcDatetime,
)
from kalakal.domain.sensitive import find_sensitive_content

FailureMessage = Annotated[str, StringConstraints(min_length=1, max_length=1000)]
TruncatedOutput = Annotated[str, StringConstraints(min_length=1, max_length=2000)]

ModelAttemptErrorClass = Literal[
    "timeout",
    "server_error",
    "rate_limited",
    "network_error",
    "invalid_response",
    "other",
]

# Classifications the architecture fixes (§5.4, §5.7, §7.4–§7.6).
_PINNED_CLASSIFICATIONS: dict[str, FailureClassification] = {
    "SCENARIO_UNKNOWN": "permanent",
    "FIXTURE_INVALID": "permanent",
    "REQUEST_INVALID": "permanent",
    "MODEL_UNAVAILABLE": "retryable",
    "RUN_DEADLINE_EXCEEDED": "retryable",
    "PERSISTENCE_ERROR": "retryable",
    "MODEL_OUTPUT_REJECTED": "safety",
    "POLICY_INVARIANT_BREACH": "safety",
    "TOOL_CALL_OUT_OF_BOUNDS": "safety",
}

# These failures occur before any model invocation, so no model metadata of
# any kind can truthfully exist for them.
_PRE_MODEL_REASONS = frozenset(
    {"REQUEST_INVALID", "SCENARIO_UNKNOWN", "FIXTURE_INVALID"}
)

# Separate failed-attempt series are genuinely relevant only when the model
# was unavailable, or when the run deadline expired during model attempts.
_ATTEMPT_RELEVANT_REASONS = frozenset({"MODEL_UNAVAILABLE", "RUN_DEADLINE_EXCEEDED"})


# §5.3: one transient retry at most, so a failed series is at most 2
# attempts; primary (≤2) plus a single fallback attempt caps the total at 3.
MAX_ATTEMPTS_PER_SERIES = 2
MAX_TOTAL_FAILED_ATTEMPTS = 3


class FailedModelAttempt(StrictModel):
    """One unsuccessful model-attempt series, recorded truthfully.

    Token and response metadata appear only when genuinely available from
    the failed attempt — never as dummy values.
    """

    model_id: Identifier
    attempt_count: Annotated[int, Field(ge=1, le=MAX_ATTEMPTS_PER_SERIES)]
    error_class: ModelAttemptErrorClass
    is_fallback: bool
    response_id: Identifier | None = None
    input_tokens: TokenCount | None = None
    output_tokens: TokenCount | None = None


class RunFailure(StrictModel):
    """Terminal failure record; redaction-safe and bounded."""

    schema_version: Literal["1"]
    run_id: Identifier
    state_at_failure: ActiveRunState
    classification: FailureClassification
    reason_code: FailureReasonCode
    message: FailureMessage
    occurred_at: UtcDatetime
    model_invocation: ModelInvocationInvoked | None = None
    failed_model_attempts: Annotated[
        tuple[FailedModelAttempt, ...], Field(max_length=2)
    ] = ()
    rejected_output_truncated: TruncatedOutput | None = None

    @model_validator(mode="after")
    def _check_consistency(self) -> RunFailure:
        pinned = _PINNED_CLASSIFICATIONS.get(self.reason_code)
        if pinned is not None and self.classification != pinned:
            raise ValueError(
                f"{self.reason_code} must be classified {pinned!r}, "
                f"got {self.classification!r}"
            )
        if self.reason_code == "MODEL_OUTPUT_REJECTED":
            if self.model_invocation is None:
                raise ValueError(
                    "MODEL_OUTPUT_REJECTED requires the model-invocation metadata"
                )
            if self.rejected_output_truncated is None:
                raise ValueError(
                    "MODEL_OUTPUT_REJECTED requires the truncated rejected output"
                )
        elif self.rejected_output_truncated is not None:
            raise ValueError(
                "rejected output is recorded only for MODEL_OUTPUT_REJECTED"
            )
        if self.reason_code == "MODEL_UNAVAILABLE":
            if not self.failed_model_attempts:
                raise ValueError(
                    "MODEL_UNAVAILABLE requires at least one failed model attempt"
                )
            if self.model_invocation is not None:
                raise ValueError(
                    "MODEL_UNAVAILABLE means no successful invocation exists; "
                    "record failed attempts, not invocation metadata"
                )
        if self.reason_code in _PRE_MODEL_REASONS and self.model_invocation is not None:
            raise ValueError(
                f"{self.reason_code} occurs before any model invocation; "
                "invocation metadata must be absent"
            )
        if (
            self.failed_model_attempts
            and self.reason_code not in _ATTEMPT_RELEVANT_REASONS
        ):
            raise ValueError(
                "failed model attempts are recorded only for MODEL_UNAVAILABLE "
                "or RUN_DEADLINE_EXCEEDED"
            )
        attempts = self.failed_model_attempts
        if attempts:
            model_ids = [attempt.model_id for attempt in attempts]
            if len(set(model_ids)) != len(model_ids):
                raise ValueError("failed-attempt series must have unique model IDs")
            primary_count = sum(1 for a in attempts if not a.is_fallback)
            fallback_count = sum(1 for a in attempts if a.is_fallback)
            if primary_count > 1:
                raise ValueError("at most one primary failed-attempt series is allowed")
            if fallback_count > 1:
                raise ValueError(
                    "at most one fallback failed-attempt series is allowed"
                )
            if fallback_count and not primary_count:
                raise ValueError("a fallback attempt series requires a primary series")
            if fallback_count and attempts[0].is_fallback:
                raise ValueError("the primary failed-attempt series must come first")
            total_attempts = sum(a.attempt_count for a in attempts)
            if total_attempts > MAX_TOTAL_FAILED_ATTEMPTS:
                raise ValueError(
                    "total failed attempts across series must not exceed "
                    f"{MAX_TOTAL_FAILED_ATTEMPTS}, got {total_attempts}"
                )
        sensitive = find_sensitive_content(self)
        if sensitive is not None:
            raise ValueError(
                f"failure record rejected by sensitive-content scan: {sensitive}"
            )
        return self
