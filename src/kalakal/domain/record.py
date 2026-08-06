"""DecisionRecord terminal shapes and audit metadata (architecture.md §6.2.10).

A DecisionRecord exists in exactly three valid terminal shapes; every
inconsistent conditional-field combination is rejected before persistence.
Failures and timeouts persist a RunFailure instead — never a partial record.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter, model_validator

from kalakal.domain.draft import SimulatedDiscordDraft
from kalakal.domain.edge import EdgeAssessment
from kalakal.domain.estimate import ProbabilityEstimate
from kalakal.domain.explanation import DecisionExplanation
from kalakal.domain.invocation import (
    Abstention,
    DeterministicSelectorMetadata,
    MarketSelection,
    ModelInvocationInvoked,
    ModelInvocationMetadata,
    ModelInvocationNotInvoked,
)
from kalakal.domain.market import CandidateMarket, MarketSnapshot
from kalakal.domain.match import MATCH_ESTIMATOR_FIELDS, MatchContext
from kalakal.domain.policy import PolicyDecision
from kalakal.domain.primitives import (
    ORCHESTRATOR_ONLY_ABSTAIN_REASON,
    AbstentionSource,
    EligibilityReason,
    EvidenceRef,
    FixtureProvenance,
    Identifier,
    LatencyMs,
    RunState,
    SelectionSource,
    StrictModel,
    UtcDatetime,
    VersionStr,
)
from kalakal.domain.quality import DataQuality
from kalakal.domain.run import RunRequest
from kalakal.domain.sensitive import find_sensitive_content

_TERMINAL_STATES = frozenset({"completed", "abstained", "failed", "timed_out"})


class StateTransition(StrictModel):
    """One recorded state transition of the run state machine (§7.1)."""

    state: RunState
    at: UtcDatetime


class CandidateEligibility(StrictModel):
    """One considered candidate with its §5.6 eligibility result."""

    market: CandidateMarket
    eligible: bool
    ineligibility_reasons: Annotated[tuple[EligibilityReason, ...], Field(max_length=4)]

    @model_validator(mode="after")
    def _check_consistency(self) -> CandidateEligibility:
        reasons = self.ineligibility_reasons
        if len(set(reasons)) != len(reasons):
            raise ValueError("ineligibility_reasons must not contain duplicates")
        if self.eligible and reasons:
            raise ValueError("an eligible candidate must not carry reasons")
        if not self.eligible and not reasons:
            raise ValueError("an ineligible candidate requires at least one reason")
        if self.eligible and self.market.status != "open":
            raise ValueError("a market that is not open cannot be eligible")
        if (
            self.market.status == "closed"
            and not self.eligible
            and "NOT_OPEN" not in reasons
        ):
            raise ValueError("an ineligible closed market must carry NOT_OPEN")
        if self.market.status == "open" and "NOT_OPEN" in reasons:
            raise ValueError("an open market must not carry NOT_OPEN")
        return self


def _check_fixture_set(
    entity_name: str,
    entity_provenance: FixtureProvenance,
    record_provenance: FixtureProvenance,
) -> None:
    if (
        entity_provenance.fixture_set_id != record_provenance.fixture_set_id
        or entity_provenance.fixture_set_version
        != record_provenance.fixture_set_version
    ):
        raise ValueError(
            f"{entity_name} provenance names a different fixture set than the record"
        )


def _check_transitions(
    transitions: tuple[StateTransition, ...], terminal_state: str
) -> None:
    if transitions[0].state != "created":
        raise ValueError("state-transition history must start at 'created'")
    if transitions[-1].state != terminal_state:
        raise ValueError(
            f"state-transition history must end at {terminal_state!r}, "
            f"got {transitions[-1].state!r}"
        )
    for intermediate in transitions[:-1]:
        if intermediate.state in _TERMINAL_STATES:
            raise ValueError("only the final transition may be a terminal state")
    for earlier, later in zip(transitions, transitions[1:], strict=False):
        if later.at < earlier.at:
            raise ValueError("state-transition timestamps must be non-decreasing")


def _conflict_refs(data_quality: DataQuality) -> list[EvidenceRef]:
    return [
        ref for conflict in data_quality.conflicts for ref in conflict.evidence_refs
    ]


def _resolve_evidence_refs(
    refs: Iterable[EvidenceRef],
    *,
    market_ids: frozenset[str],
    match_ids: frozenset[str],
    snapshot_market_ids: frozenset[str],
    fixture_source_ids: frozenset[str],
) -> None:
    pools: dict[str, frozenset[str]] = {
        "market": market_ids,
        "match": match_ids,
        "snapshot": snapshot_market_ids,
        "fixture_source": fixture_source_ids,
    }
    for ref in refs:
        if ref.ref_id not in pools[ref.kind]:
            raise ValueError(
                f"evidence ref {ref.kind}:{ref.ref_id} does not resolve to a "
                "validated entity of this record"
            )


class _DecisionRecordBase(StrictModel):
    """Fields and invariants common to all three terminal shapes."""

    schema_version: Literal["1"]
    run_id: Identifier
    request: RunRequest
    provenance: FixtureProvenance
    candidates_considered: Annotated[
        tuple[CandidateEligibility, ...], Field(max_length=32)
    ]
    explanation: DecisionExplanation
    application_version: VersionStr
    transitions: Annotated[
        tuple[StateTransition, ...], Field(min_length=2, max_length=16)
    ]
    latency_ms: LatencyMs

    @model_validator(mode="after")
    def _check_base(self) -> _DecisionRecordBase:
        if self.request.run_id != self.run_id:
            raise ValueError("request.run_id must equal the record run_id")
        if self.explanation.run_id != self.run_id:
            raise ValueError("explanation.run_id must equal the record run_id")
        market_ids = [c.market.market_id for c in self.candidates_considered]
        if len(set(market_ids)) != len(market_ids):
            raise ValueError("candidates_considered must have unique market_ids")
        for candidate in self.candidates_considered:
            _check_fixture_set(
                f"candidate {candidate.market.market_id}",
                candidate.market.provenance,
                self.provenance,
            )
        sensitive = find_sensitive_content(self)
        if sensitive is not None:
            raise ValueError(f"record rejected by sensitive-content scan: {sensitive}")
        return self

    def _explanation_refs(self) -> list[EvidenceRef]:
        return list(self.explanation.evidence_refs) + [
            factor.evidence_ref for factor in self.explanation.key_factors
        ]

    def _candidate_conflict_refs(self) -> list[EvidenceRef]:
        refs: list[EvidenceRef] = []
        for candidate in self.candidates_considered:
            refs.extend(_conflict_refs(candidate.market.data_quality))
        return refs

    def _require_agent_explanation(self, invocation: ModelInvocationInvoked) -> None:
        if self.explanation.source != "agent":
            raise ValueError(
                "an invoked-model record requires an agent-sourced explanation"
            )
        if self.explanation.model_metadata_ref != invocation.invocation_id:
            raise ValueError(
                "explanation model_metadata_ref must resolve to the "
                "model-invocation metadata"
            )
        if self.explanation.prompt_version != invocation.prompt_version:
            raise ValueError(
                "explanation prompt_version must match the invocation prompt_version"
            )

    def _require_orchestrator_explanation(self, path_name: str) -> None:
        # The DecisionExplanation validator already forces the deterministic
        # explanation_template_version and forbids prompt/model refs for this
        # source; only the source itself is checked here.
        if self.explanation.source != "orchestrator":
            raise ValueError(
                f"{path_name} requires an orchestrator-sourced explanation"
            )


class PreSelectionAbstentionRecord(_DecisionRecordBase):
    """Shape A — pre-selection abstention: agent, orchestrator, or
    deterministic-stub variant."""

    outcome: Literal["abstained"]
    abstention_source: AbstentionSource
    selection: Abstention
    model_invocation: ModelInvocationMetadata
    deterministic_selector: DeterministicSelectorMetadata | None = None

    @model_validator(mode="after")
    def _check_shape(self) -> PreSelectionAbstentionRecord:
        _check_transitions(self.transitions, "abstained")
        eligible_count = sum(1 for c in self.candidates_considered if c.eligible)
        if self.abstention_source == "agent":
            if not isinstance(self.model_invocation, ModelInvocationInvoked):
                raise ValueError(
                    "an agent abstention requires invocation_status 'invoked' "
                    "with full model metadata"
                )
            self._require_agent_explanation(self.model_invocation)
            if self.selection.abstain_reason_code == ORCHESTRATOR_ONLY_ABSTAIN_REASON:
                raise ValueError(
                    "NO_VALID_CANDIDATES is reserved for the orchestrator variant"
                )
            if eligible_count == 0:
                raise ValueError(
                    "an agent abstention requires at least one eligible candidate"
                )
            if self.deterministic_selector is not None:
                raise ValueError(
                    "an agent abstention must not carry deterministic-selector metadata"
                )
        elif self.abstention_source == "orchestrator":
            if not isinstance(self.model_invocation, ModelInvocationNotInvoked):
                raise ValueError(
                    "an orchestrator abstention requires invocation_status "
                    "'not_invoked' with no model metadata"
                )
            self._require_orchestrator_explanation("an orchestrator abstention")
            if self.selection.abstain_reason_code != ORCHESTRATOR_ONLY_ABSTAIN_REASON:
                raise ValueError(
                    "an orchestrator abstention requires reason NO_VALID_CANDIDATES"
                )
            if eligible_count > 0:
                raise ValueError(
                    "NO_VALID_CANDIDATES requires zero eligible candidates"
                )
            if self.deterministic_selector is not None:
                raise ValueError(
                    "an orchestrator abstention must not carry "
                    "deterministic-selector metadata"
                )
        else:
            if not isinstance(self.model_invocation, ModelInvocationNotInvoked):
                raise ValueError(
                    "a deterministic-stub abstention requires invocation_status "
                    "'not_invoked' with no model metadata"
                )
            self._require_orchestrator_explanation("a deterministic-stub abstention")
            if self.selection.abstain_reason_code == ORCHESTRATOR_ONLY_ABSTAIN_REASON:
                raise ValueError(
                    "NO_VALID_CANDIDATES is reserved for the orchestrator variant"
                )
            if eligible_count == 0:
                raise ValueError(
                    "a deterministic-stub abstention requires at least one "
                    "eligible candidate"
                )
            if self.deterministic_selector is None:
                raise ValueError(
                    "a deterministic-stub abstention requires "
                    "deterministic-selector metadata"
                )
        _resolve_evidence_refs(
            self._explanation_refs() + self._candidate_conflict_refs(),
            market_ids=frozenset(
                c.market.market_id for c in self.candidates_considered
            ),
            match_ids=frozenset(),
            snapshot_market_ids=frozenset(),
            fixture_source_ids=frozenset({self.provenance.fixture_set_id}),
        )
        return self


class _PostSelectionBase(_DecisionRecordBase):
    """Fields and invariants shared by shapes B and C (after a selection).

    ``selection_source`` is record-layer source attribution (§6.2.10): the
    bounded agent or the test-only deterministic stub selector (§5.10). It is
    never taken from model output.
    """

    selection_source: SelectionSource
    selection: MarketSelection
    match_context: MatchContext
    market_snapshot: MarketSnapshot
    probability_estimate: ProbabilityEstimate
    edge_assessment: EdgeAssessment
    policy_decision: PolicyDecision
    model_invocation: ModelInvocationMetadata
    deterministic_selector: DeterministicSelectorMetadata | None = None

    @model_validator(mode="after")
    def _check_post_selection(self) -> _PostSelectionBase:
        selected_id = self.selection.selected_market_id
        selected_side = self.selection.selected_side
        candidate = next(
            (
                c
                for c in self.candidates_considered
                if c.market.market_id == selected_id
            ),
            None,
        )
        if candidate is None:
            raise ValueError("selected market is not among candidates_considered")
        if not candidate.eligible:
            raise ValueError("selected market is not an eligible candidate")
        if self.match_context.market_id != selected_id:
            raise ValueError("match_context.market_id must equal the selected market")
        if self.market_snapshot.market_id != selected_id:
            raise ValueError("market_snapshot.market_id must equal the selected market")
        if self.market_snapshot.side != selected_side:
            raise ValueError("market_snapshot.side must equal the selected side")
        estimate = self.probability_estimate
        if estimate.market_id != selected_id or estimate.side != selected_side:
            raise ValueError(
                "probability_estimate must target the selected market and side"
            )
        edge = self.edge_assessment
        if edge.market_id != selected_id or edge.side != selected_side:
            raise ValueError("edge_assessment must target the selected market and side")
        if edge.probability_ppm != estimate.probability_ppm:
            raise ValueError(
                "edge_assessment probability_ppm must equal the recorded estimate"
            )
        if edge.ask_price_micro != self.market_snapshot.ask_price_micro:
            raise ValueError(
                "edge_assessment ask_price_micro must equal the recorded snapshot"
            )
        if edge.fee_model_version != self.market_snapshot.fee_model_version:
            raise ValueError(
                "edge_assessment fee_model_version must equal the snapshot ref"
            )
        if edge.estimate_inputs_digest != estimate.inputs_digest:
            raise ValueError(
                "edge_assessment estimate_inputs_digest must equal the estimate "
                "inputs_digest"
            )
        snapshot_digest = self.market_snapshot.provenance.content_digest
        if edge.snapshot_content_digest != snapshot_digest:
            raise ValueError(
                "edge_assessment snapshot_content_digest must equal the snapshot "
                "content digest"
            )
        if estimate.basis.match_id != self.match_context.match_id:
            raise ValueError("estimate basis match_id must equal the match context")
        for field_name in MATCH_ESTIMATOR_FIELDS:
            if getattr(estimate.basis, field_name) != getattr(
                self.match_context, field_name
            ):
                raise ValueError(
                    f"estimate basis {field_name} must equal the recorded "
                    "match-context value"
                )
        if self.selection_source == "agent":
            if not isinstance(self.model_invocation, ModelInvocationInvoked):
                raise ValueError(
                    "an agent selection requires invocation_status 'invoked' "
                    "with full model metadata"
                )
            self._require_agent_explanation(self.model_invocation)
            if self.deterministic_selector is not None:
                raise ValueError(
                    "an agent selection must not carry deterministic-selector metadata"
                )
        else:
            if not isinstance(self.model_invocation, ModelInvocationNotInvoked):
                raise ValueError(
                    "a deterministic-stub selection requires invocation_status "
                    "'not_invoked' with no model metadata"
                )
            self._require_orchestrator_explanation("a deterministic-stub selection")
            if self.deterministic_selector is None:
                raise ValueError(
                    "a deterministic-stub selection requires "
                    "deterministic-selector metadata"
                )
        _check_fixture_set(
            "match_context", self.match_context.provenance, self.provenance
        )
        _check_fixture_set(
            "market_snapshot", self.market_snapshot.provenance, self.provenance
        )
        refs = (
            self._explanation_refs()
            + self._candidate_conflict_refs()
            + _conflict_refs(self.match_context.data_quality)
            + _conflict_refs(self.market_snapshot.data_quality)
        )
        _resolve_evidence_refs(
            refs,
            market_ids=frozenset(
                c.market.market_id for c in self.candidates_considered
            ),
            match_ids=frozenset({self.match_context.match_id}),
            snapshot_market_ids=frozenset({self.market_snapshot.market_id}),
            fixture_source_ids=frozenset({self.provenance.fixture_set_id}),
        )
        return self


class PolicyNoBetRecord(_PostSelectionBase):
    """Shape B — policy no-bet after selection; no draft may exist."""

    outcome: Literal["abstained"]

    @model_validator(mode="after")
    def _check_shape(self) -> PolicyNoBetRecord:
        _check_transitions(self.transitions, "abstained")
        if self.policy_decision.decision != "no_bet":
            raise ValueError("a policy no-bet record requires decision 'no_bet'")
        return self


class CompletedProceedRecord(_PostSelectionBase):
    """Shape C — completed proceed decision with its simulated draft."""

    outcome: Literal["completed"]
    draft: SimulatedDiscordDraft

    @model_validator(mode="after")
    def _check_shape(self) -> CompletedProceedRecord:
        _check_transitions(self.transitions, "completed")
        if self.policy_decision.decision != "proceed":
            raise ValueError("a completed record requires decision 'proceed'")
        draft = self.draft
        if draft.run_id != self.run_id:
            raise ValueError("draft.run_id must equal the record run_id")
        if draft.market_id != self.selection.selected_market_id:
            raise ValueError("draft.market_id must equal the selected market")
        if draft.side != self.selection.selected_side:
            raise ValueError("draft.side must equal the selected side")
        if draft.ask_price_micro != self.market_snapshot.ask_price_micro:
            raise ValueError("draft ask price must equal the recorded snapshot")
        if draft.probability_ppm != self.probability_estimate.probability_ppm:
            raise ValueError("draft probability must equal the recorded estimate")
        if draft.net_edge_ppm != self.edge_assessment.net_edge_ppm:
            raise ValueError("draft net edge must equal the recorded assessment")
        selected = next(
            c.market
            for c in self.candidates_considered
            if c.market.market_id == self.selection.selected_market_id
        )
        if draft.event_name != selected.event_name:
            raise ValueError("draft event_name must equal the selected market's")
        if draft.market_link != selected.market_link:
            raise ValueError("draft market_link must equal the selected market's")
        expected_meaning = (
            selected.yes_means
            if self.selection.selected_side == "yes"
            else selected.no_means
        )
        if draft.side_meaning != expected_meaning:
            raise ValueError(
                "draft side_meaning must equal the selected market's side semantics"
            )
        return self


DecisionRecord = (
    PreSelectionAbstentionRecord | PolicyNoBetRecord | CompletedProceedRecord
)

_DECISION_RECORD_ADAPTER: TypeAdapter[DecisionRecord] = TypeAdapter(
    PreSelectionAbstentionRecord | PolicyNoBetRecord | CompletedProceedRecord
)


def validate_decision_record(data: object) -> DecisionRecord:
    """Validate ``data`` as exactly one of the three terminal shapes."""
    return _DECISION_RECORD_ADAPTER.validate_python(data)
