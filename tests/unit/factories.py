"""Shared factories producing valid Slice 2 contract instances.

Each ``*_kwargs`` function returns a fresh dict of valid constructor
arguments so tests can override or delete individual fields; each ``make_*``
function returns a validated instance. All data is synthetic.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

from kalakal.domain import (
    DEMO_ESTIMATOR_DISPLAY_LABEL,
    SIMULATION_DRAFT_LABEL,
    SYNTHETIC_MARKET_LINK_PREFIX,
    Abstention,
    CandidateEligibility,
    CandidateMarket,
    DataConflict,
    DataQuality,
    DecisionExplanation,
    DeterministicSelectorMetadata,
    EdgeAssessment,
    EstimatorBasis,
    EvidenceRef,
    FailedModelAttempt,
    FixtureProvenance,
    KeyFactor,
    MarketSelection,
    MarketSnapshot,
    MatchContext,
    ModelCallUsage,
    ModelInvocationInvoked,
    ModelInvocationNotInvoked,
    PolicyCheck,
    PolicyDecision,
    ProbabilityEstimate,
    RosterEntry,
    RunFailure,
    RunRequest,
    SimulatedDiscordDraft,
    StateTransition,
    ToolCallRecord,
    estimate_inputs_digest,
)
from kalakal.domain.primitives import MarketSide, RunState
from kalakal.edge.calculator import calculate_edge
from kalakal.estimator.demo import DemoEstimator

T0 = datetime(2026, 8, 5, 12, 0, 0, tzinfo=timezone.utc)

MARKET_ID = "mkt-1"
MATCH_ID = "match-1"
RUN_ID = "run-1"
FIXTURE_SET_ID = "fixture-set-1"
FIXTURE_SET_VERSION = "2026.08.05"
FEE_MODEL_VERSION = "synthetic-fee-1"
MARKET_LINK = SYNTHETIC_MARKET_LINK_PREFIX + MARKET_ID
EVENT_NAME = "Synthetic Masters 2026"
YES_MEANS = "SYN-A wins the series"
NO_MEANS = "SYN-B wins the series"

# Chosen so the demo formula lands exactly on the §6.2.6 reference case:
# score_yes = 600 + 50 = 650, score_no = 310 + 40 = 350, total 1000
# -> probability 650_000 ppm for side "yes".
YES_TEAM_NAME = "SYN-A"
NO_TEAM_NAME = "SYN-B"
YES_TEAM_RATING = 600
YES_TEAM_FORM = 50
NO_TEAM_RATING = 310
NO_TEAM_FORM = 40


def ts(minutes: int = 0) -> datetime:
    return T0 + timedelta(minutes=minutes)


def sha_hex(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def complete_quality() -> DataQuality:
    return DataQuality(is_complete=True, missing_fields=(), conflicts=())


def make_conflict(field_path: str, ref: EvidenceRef | None = None) -> DataConflict:
    return DataConflict(
        field_path=field_path,
        description=f"Synthetic sources disagree about {field_path}.",
        evidence_refs=(
            ref or EvidenceRef(kind="fixture_source", ref_id=FIXTURE_SET_ID),
        ),
    )


def provenance_kwargs(**over: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "fixture_set_id": FIXTURE_SET_ID,
        "fixture_set_version": FIXTURE_SET_VERSION,
        "content_digest": sha_hex("content"),
        "is_synthetic": True,
    }
    kwargs.update(over)
    return kwargs


def make_provenance(**over: Any) -> FixtureProvenance:
    return FixtureProvenance(**provenance_kwargs(**over))


def candidate_market_kwargs(**over: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "schema_version": "1",
        "market_id": MARKET_ID,
        "event_name": EVENT_NAME,
        "series_description": "SYN-A vs SYN-B, grand final",
        "yes_means": YES_MEANS,
        "no_means": NO_MEANS,
        "status": "open",
        "market_link": MARKET_LINK,
        "as_of": ts(),
        "valid_until": ts(60),
        "data_quality": complete_quality(),
        "provenance": make_provenance(content_digest=sha_hex("candidate")),
    }
    kwargs.update(over)
    return kwargs


def make_candidate_market(**over: Any) -> CandidateMarket:
    return CandidateMarket(**candidate_market_kwargs(**over))


def match_context_kwargs(**over: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "schema_version": "1",
        "match_id": MATCH_ID,
        "market_id": MARKET_ID,
        "yes_team_name": YES_TEAM_NAME,
        "no_team_name": NO_TEAM_NAME,
        "best_of": 3,
        "tournament_name": "Synthetic Masters",
        "tournament_tier": "synthetic-tier-1",
        "rosters": (
            RosterEntry(team_name=YES_TEAM_NAME, player_handle="syn-a-one"),
            RosterEntry(team_name=NO_TEAM_NAME, player_handle="syn-b-one"),
        ),
        "patch_label": "7.99-synthetic",
        "scheduled_start": ts(120),
        "as_of": ts(),
        "valid_until": ts(60),
        "yes_team_rating": YES_TEAM_RATING,
        "yes_team_form": YES_TEAM_FORM,
        "no_team_rating": NO_TEAM_RATING,
        "no_team_form": NO_TEAM_FORM,
        "data_quality": complete_quality(),
        "provenance": make_provenance(content_digest=sha_hex("match")),
    }
    kwargs.update(over)
    return kwargs


def make_match_context(**over: Any) -> MatchContext:
    return MatchContext(**match_context_kwargs(**over))


def market_snapshot_kwargs(**over: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "schema_version": "1",
        "market_id": MARKET_ID,
        "side": "yes",
        "ask_price_micro": 600_000,
        "bid_price_micro": 590_000,
        "liquidity_hint_micro": 2_500_000,
        "captured_at": ts(),
        "valid_until": ts(60),
        "fee_model_version": FEE_MODEL_VERSION,
        "data_quality": complete_quality(),
        "provenance": make_provenance(content_digest=sha_hex("snapshot")),
    }
    kwargs.update(over)
    return kwargs


def make_market_snapshot(**over: Any) -> MarketSnapshot:
    return MarketSnapshot(**market_snapshot_kwargs(**over))


def make_estimate(
    match: MatchContext | None = None, side: MarketSide = "yes"
) -> ProbabilityEstimate:
    result = DemoEstimator().estimate(
        match or make_match_context(), side, computed_at=ts(1)
    )
    assert isinstance(result, ProbabilityEstimate)
    return result


def probability_estimate_kwargs(**over: Any) -> dict[str, Any]:
    basis = EstimatorBasis(
        match_id=MATCH_ID,
        yes_team_rating=YES_TEAM_RATING,
        yes_team_form=YES_TEAM_FORM,
        no_team_rating=NO_TEAM_RATING,
        no_team_form=NO_TEAM_FORM,
    )
    kwargs: dict[str, Any] = {
        "schema_version": "1",
        "market_id": MARKET_ID,
        "side": "yes",
        "probability_ppm": 650_000,
        "estimator_id": "demo",
        "estimator_version": "1.0.0",
        "is_predictive": False,
        "display_label": DEMO_ESTIMATOR_DISPLAY_LABEL,
        "basis": basis,
        "inputs_digest": estimate_inputs_digest(
            estimator_id="demo",
            estimator_version="1.0.0",
            market_id=MARKET_ID,
            side="yes",
            basis=basis,
        ),
        "computed_at": ts(1),
    }
    kwargs.update(over)
    return kwargs


def make_edge_assessment(
    estimate: ProbabilityEstimate | None = None,
    snapshot: MarketSnapshot | None = None,
    fee_rate_ppm: int = 10_000,
) -> EdgeAssessment:
    return calculate_edge(
        estimate=estimate or make_estimate(),
        snapshot=snapshot or make_market_snapshot(),
        fee_rate_ppm=fee_rate_ppm,
        fee_model_version=FEE_MODEL_VERSION,
        computed_at=ts(2),
    )


def edge_assessment_kwargs(**over: Any) -> dict[str, Any]:
    valid = make_edge_assessment()
    kwargs: dict[str, Any] = {
        "schema_version": "1",
        "market_id": valid.market_id,
        "side": valid.side,
        "probability_ppm": valid.probability_ppm,
        "ask_price_micro": valid.ask_price_micro,
        "fee_rate_ppm": valid.fee_rate_ppm,
        "fee_model_version": valid.fee_model_version,
        "fee_estimate_micro": valid.fee_estimate_micro,
        "gross_edge_ppm": valid.gross_edge_ppm,
        "net_edge_ppm": valid.net_edge_ppm,
        "estimate_inputs_digest": valid.estimate_inputs_digest,
        "snapshot_content_digest": valid.snapshot_content_digest,
        "inputs_digest": valid.inputs_digest,
        "computed_at": valid.computed_at,
    }
    kwargs.update(over)
    return kwargs


def make_policy_check(**over: Any) -> PolicyCheck:
    kwargs: dict[str, Any] = {
        "check_id": "entry_band_upper",
        "passed": True,
        "observed_value": 600_000,
        "threshold_value": 900_000,
        "threshold_source": "jup_callers_season1_config",
    }
    kwargs.update(over)
    return PolicyCheck(**kwargs)


def policy_decision_kwargs(decision: str = "proceed", **over: Any) -> dict[str, Any]:
    if decision == "proceed":
        checks: tuple[PolicyCheck, ...] = (make_policy_check(),)
        reason_codes: tuple[str, ...] = ()
    else:
        checks = (
            make_policy_check(
                check_id="min_net_edge",
                passed=False,
                observed_value=44_000,
                threshold_value=50_000,
            ),
        )
        reason_codes = ("POLICY_INSUFFICIENT_NET_EDGE",)
    kwargs: dict[str, Any] = {
        "schema_version": "1",
        "decision": decision,
        "reason_codes": reason_codes,
        "checks": checks,
        "policy_version": "policy-1",
        "evaluated_at": ts(3),
        "inputs_digest": sha_hex("policy-inputs"),
    }
    kwargs.update(over)
    return kwargs


def make_policy_decision(decision: str = "proceed", **over: Any) -> PolicyDecision:
    return PolicyDecision(**policy_decision_kwargs(decision, **over))


def explanation_kwargs(source: str = "agent", **over: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "schema_version": "1",
        "run_id": RUN_ID,
        "source": source,
        "summary": "Synthetic summary of the synthetic decision.",
        "key_factors": (
            KeyFactor(
                factor="Synthetic rating gap favors SYN-A.",
                direction="supports",
                evidence_ref=EvidenceRef(kind="market", ref_id=MARKET_ID),
            ),
        ),
        "conflicts": (),
        "data_gaps": (),
        "confidence_qualifier": "medium",
        "evidence_refs": (EvidenceRef(kind="market", ref_id=MARKET_ID),),
    }
    if source == "agent":
        kwargs["prompt_version"] = "prompt-1"
        kwargs["model_metadata_ref"] = "invocation-1"
    else:
        kwargs["explanation_template_version"] = "template-1"
    kwargs.update(over)
    return kwargs


def make_explanation(source: str = "agent", **over: Any) -> DecisionExplanation:
    return DecisionExplanation(**explanation_kwargs(source, **over))


def make_usage(model_id: str, **over: Any) -> ModelCallUsage:
    kwargs: dict[str, Any] = {
        "model_id": model_id,
        "call_count": 1,
        "input_tokens": 1200,
        "output_tokens": 300,
    }
    kwargs.update(over)
    return ModelCallUsage(**kwargs)


def invoked_kwargs(**over: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "invocation_status": "invoked",
        "invocation_id": "invocation-1",
        "model_id": "gemini-3.6-flash",
        "prompt_version": "prompt-1",
        "response_ids": ("resp-1",),
        "usage": (make_usage("gemini-3.6-flash"),),
        "fallback_used": False,
        "tool_calls": (
            ToolCallRecord(tool_name="list_candidate_markets", called_at=ts(1)),
        ),
    }
    kwargs.update(over)
    return kwargs


def make_invoked(**over: Any) -> ModelInvocationInvoked:
    return ModelInvocationInvoked(**invoked_kwargs(**over))


def make_not_invoked() -> ModelInvocationNotInvoked:
    return ModelInvocationNotInvoked(invocation_status="not_invoked")


def selector_metadata_kwargs(**over: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "selector_id": "deterministic-stub",
        "selector_version": "1.0.0",
        "test_only": True,
    }
    kwargs.update(over)
    return kwargs


def make_selector_metadata(**over: Any) -> DeterministicSelectorMetadata:
    return DeterministicSelectorMetadata(**selector_metadata_kwargs(**over))


def draft_kwargs(**over: Any) -> dict[str, Any]:
    warning = "Regenerate this draft if stale; prices move before posting."
    draft_text = (
        f"{SIMULATION_DRAFT_LABEL}\n"
        f"{EVENT_NAME} — {YES_MEANS}\n"
        f"{MARKET_LINK}\n"
        f"Ask 0.600000 | confidence 0.650000 "
        f"({DEMO_ESTIMATOR_DISPLAY_LABEL}) | net edge 0.044000\n"
        "#nfa\n"
        f"Generated 2026-08-05T12:04:00Z. {warning}"
    )
    kwargs: dict[str, Any] = {
        "schema_version": "1",
        "run_id": RUN_ID,
        "market_id": MARKET_ID,
        "side": "yes",
        "is_simulation": True,
        "simulation_label": SIMULATION_DRAFT_LABEL,
        "event_name": EVENT_NAME,
        "side_meaning": YES_MEANS,
        "market_link": MARKET_LINK,
        "ask_price_micro": 600_000,
        "probability_ppm": 650_000,
        "estimator_display_label": DEMO_ESTIMATOR_DISPLAY_LABEL,
        "net_edge_ppm": 44_000,
        "nfa_tag": "#nfa",
        "generated_at": ts(4),
        "expires_at": ts(34),
        "stale_regeneration_warning": warning,
        "draft_text": draft_text,
    }
    kwargs.update(over)
    return kwargs


def make_draft(**over: Any) -> SimulatedDiscordDraft:
    return SimulatedDiscordDraft(**draft_kwargs(**over))


def run_request_kwargs(**over: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "schema_version": "1",
        "run_id": RUN_ID,
        "idempotency_key": "idem-1",
        "scenario_id": "clear-edge",
        "mode": "fixture",
        "requested_at": ts(),
    }
    kwargs.update(over)
    return kwargs


def make_run_request(**over: Any) -> RunRequest:
    return RunRequest(**run_request_kwargs(**over))


def make_failed_attempt(**over: Any) -> FailedModelAttempt:
    kwargs: dict[str, Any] = {
        "model_id": "gemini-3.6-flash",
        "attempt_count": 1,
        "error_class": "timeout",
        "is_fallback": False,
    }
    kwargs.update(over)
    return FailedModelAttempt(**kwargs)


def run_failure_kwargs(**over: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "schema_version": "1",
        "run_id": RUN_ID,
        "state_at_failure": "validating",
        "classification": "permanent",
        "reason_code": "FIXTURE_INVALID",
        "message": "Synthetic fixture failed schema validation.",
        "occurred_at": ts(1),
    }
    kwargs.update(over)
    return kwargs


def make_run_failure(**over: Any) -> RunFailure:
    return RunFailure(**run_failure_kwargs(**over))


def make_transitions(path: tuple[RunState, ...]) -> tuple[StateTransition, ...]:
    return tuple(
        StateTransition(state=state, at=ts(index)) for index, state in enumerate(path)
    )


A_AGENT_PATH: tuple[RunState, ...] = (
    "created",
    "validating",
    "selecting",
    "explaining",
    "persisting",
    "abstained",
)
A_ORCH_PATH: tuple[RunState, ...] = (
    "created",
    "validating",
    "explaining",
    "persisting",
    "abstained",
)
B_PATH: tuple[RunState, ...] = (
    "created",
    "validating",
    "selecting",
    "estimating",
    "comparing",
    "policy_checking",
    "explaining",
    "persisting",
    "abstained",
)
C_PATH: tuple[RunState, ...] = (
    "created",
    "validating",
    "selecting",
    "estimating",
    "comparing",
    "policy_checking",
    "explaining",
    "persisting",
    "completed",
)


def _record_common_kwargs() -> dict[str, Any]:
    return {
        "schema_version": "1",
        "run_id": RUN_ID,
        "request": make_run_request(),
        "provenance": make_provenance(content_digest=sha_hex("scenario")),
        "candidates_considered": (
            CandidateEligibility(
                market=make_candidate_market(),
                eligible=True,
                ineligibility_reasons=(),
            ),
        ),
        "explanation": make_explanation("agent"),
        "application_version": "0.1.0",
        "latency_ms": 1500,
    }


def record_a_agent_kwargs(**over: Any) -> dict[str, Any]:
    kwargs = _record_common_kwargs()
    kwargs.update(
        {
            "outcome": "abstained",
            "abstention_source": "agent",
            "selection": Abstention(
                abstained=True, abstain_reason_code="INSUFFICIENT_EVIDENCE"
            ),
            "model_invocation": make_invoked(),
            "transitions": make_transitions(A_AGENT_PATH),
        }
    )
    kwargs.update(over)
    return kwargs


def record_a_orch_kwargs(**over: Any) -> dict[str, Any]:
    kwargs = _record_common_kwargs()
    kwargs.update(
        {
            "candidates_considered": (
                CandidateEligibility(
                    market=make_candidate_market(),
                    eligible=False,
                    ineligibility_reasons=("ESTIMATOR_INPUT_MISSING",),
                ),
            ),
            "explanation": make_explanation("orchestrator"),
            "outcome": "abstained",
            "abstention_source": "orchestrator",
            "selection": Abstention(
                abstained=True, abstain_reason_code="NO_VALID_CANDIDATES"
            ),
            "model_invocation": make_not_invoked(),
            "transitions": make_transitions(A_ORCH_PATH),
        }
    )
    kwargs.update(over)
    return kwargs


def record_a_stub_kwargs(**over: Any) -> dict[str, Any]:
    kwargs = _record_common_kwargs()
    kwargs.update(
        {
            "explanation": make_explanation("orchestrator"),
            "outcome": "abstained",
            "abstention_source": "deterministic_stub",
            "selection": Abstention(
                abstained=True, abstain_reason_code="CONFLICTING_EVIDENCE"
            ),
            "model_invocation": make_not_invoked(),
            "deterministic_selector": make_selector_metadata(),
            "transitions": make_transitions(A_AGENT_PATH),
        }
    )
    kwargs.update(over)
    return kwargs


def record_b_kwargs(**over: Any) -> dict[str, Any]:
    match = make_match_context()
    snapshot = make_market_snapshot()
    estimate = make_estimate(match)
    edge = make_edge_assessment(estimate, snapshot)
    kwargs = _record_common_kwargs()
    kwargs.update(
        {
            "outcome": "abstained",
            "selection_source": "agent",
            "selection": MarketSelection(
                abstained=False,
                selected_market_id=MARKET_ID,
                selected_side="yes",
            ),
            "match_context": match,
            "market_snapshot": snapshot,
            "probability_estimate": estimate,
            "edge_assessment": edge,
            "policy_decision": make_policy_decision("no_bet"),
            "model_invocation": make_invoked(),
            "transitions": make_transitions(B_PATH),
        }
    )
    kwargs.update(over)
    return kwargs


def record_c_kwargs(**over: Any) -> dict[str, Any]:
    kwargs = record_b_kwargs()
    kwargs.update(
        {
            "outcome": "completed",
            "policy_decision": make_policy_decision("proceed"),
            "draft": make_draft(),
            "transitions": make_transitions(C_PATH),
        }
    )
    kwargs.update(over)
    return kwargs


def _stub_selection_overrides() -> dict[str, Any]:
    return {
        "selection_source": "deterministic_stub",
        "explanation": make_explanation("orchestrator"),
        "model_invocation": make_not_invoked(),
        "deterministic_selector": make_selector_metadata(),
    }


def record_b_stub_kwargs(**over: Any) -> dict[str, Any]:
    kwargs = record_b_kwargs(**_stub_selection_overrides())
    kwargs.update(over)
    return kwargs


def record_c_stub_kwargs(**over: Any) -> dict[str, Any]:
    kwargs = record_c_kwargs(**_stub_selection_overrides())
    kwargs.update(over)
    return kwargs
