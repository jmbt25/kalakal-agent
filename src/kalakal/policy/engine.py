"""Deterministic policy and abstention engine (architecture.md §6.2.7).

Final authority outside the LLM. :func:`evaluate_policy` is a pure function
of already validated inputs: no clock lookup, no I/O, no floating point, no
mutation, no environment-dependent configuration. It independently
re-verifies completeness and freshness of the selected market's evidence,
trusting no upstream stage, and evaluates every check without
short-circuiting so the audit record truthfully shows every applicable
result. A failed policy check is a normal ``no_bet`` decision; a
cross-contract or structural mismatch between the supplied inputs is a
programmer/contract error and raises :class:`PolicyInputError` instead —
malformed input is never disguised as a policy abstention.

Check order (deterministic, documented; ``POLICY_CHECK_ORDER``):

1.  ``candidate_completeness`` — observed 1 iff the candidate's
    ``data_quality`` is complete and conflict-free; threshold 1.
2.  ``match_context_completeness`` — same representation.
3.  ``snapshot_completeness`` — same representation.
4.  ``candidate_freshness`` — observed integer seconds remaining until
    ``valid_until`` (floor; negative when expired), threshold 0. At exactly
    ``valid_until`` the evidence is still fresh; it becomes stale only when
    ``valid_until < evaluated_at`` (§7.7). The reported seconds saturate at
    ±2,000,000 (the ``PolicyCheck`` observed-value bound); saturation never
    crosses zero, so pass/fail semantics are unaffected.
5.  ``match_context_freshness`` — same representation.
6.  ``snapshot_freshness`` — same representation.
7.  ``entry_price_min`` — observed ask price, threshold
    ``min_entry_price_micro``, inclusive (ask >= min passes).
8.  ``entry_price_max`` — observed ask price, threshold
    ``max_entry_price_micro``, inclusive (ask <= max passes).
9.  ``min_net_edge`` — observed ``net_edge_ppm``, threshold
    ``min_net_edge_ppm``, inclusive (net >= min passes).
10. ``duplicate_run`` — observed 1 for a duplicate run and 0 otherwise,
    maximum threshold 0.

Reason codes are deduplicated and ordered by the documented stable priority
``POLICY_REASON_PRIORITY``, independent of incidental check order; every
applicable code is retained when several rules fail at once.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Final

from kalakal.domain.edge import EdgeAssessment
from kalakal.domain.market import CandidateMarket, MarketSnapshot
from kalakal.domain.match import MatchContext
from kalakal.domain.policy import PolicyCheck, PolicyDecision
from kalakal.domain.primitives import (
    SCHEMA_VERSION,
    PolicyOutcome,
    PolicyReasonCode,
    canonical_digest,
)
from kalakal.domain.quality import DataQuality
from kalakal.policy.config import PolicyConfig, policy_config_digest


class PolicyInputError(ValueError):
    """Cross-contract or structural input mismatch — an error, never a no-bet."""


CHECK_CANDIDATE_COMPLETENESS: Final = "candidate_completeness"
CHECK_MATCH_COMPLETENESS: Final = "match_context_completeness"
CHECK_SNAPSHOT_COMPLETENESS: Final = "snapshot_completeness"
CHECK_CANDIDATE_FRESHNESS: Final = "candidate_freshness"
CHECK_MATCH_FRESHNESS: Final = "match_context_freshness"
CHECK_SNAPSHOT_FRESHNESS: Final = "snapshot_freshness"
CHECK_ENTRY_PRICE_MIN: Final = "entry_price_min"
CHECK_ENTRY_PRICE_MAX: Final = "entry_price_max"
CHECK_MIN_NET_EDGE: Final = "min_net_edge"
CHECK_DUPLICATE_RUN: Final = "duplicate_run"

POLICY_CHECK_ORDER: Final[tuple[str, ...]] = (
    CHECK_CANDIDATE_COMPLETENESS,
    CHECK_MATCH_COMPLETENESS,
    CHECK_SNAPSHOT_COMPLETENESS,
    CHECK_CANDIDATE_FRESHNESS,
    CHECK_MATCH_FRESHNESS,
    CHECK_SNAPSHOT_FRESHNESS,
    CHECK_ENTRY_PRICE_MIN,
    CHECK_ENTRY_PRICE_MAX,
    CHECK_MIN_NET_EDGE,
    CHECK_DUPLICATE_RUN,
)

# Documented stable reason-code priority: emitted reason tuples are always
# ordered by this priority, never by incidental collection order.
POLICY_REASON_PRIORITY: Final[tuple[PolicyReasonCode, ...]] = (
    "POLICY_INCOMPLETE_DATA",
    "POLICY_STALE_DATA",
    "POLICY_OUTSIDE_ENTRY_BAND",
    "POLICY_INSUFFICIENT_NET_EDGE",
    "POLICY_DUPLICATE_RUN",
)

_CHECK_REASONS: Final[dict[str, PolicyReasonCode]] = {
    CHECK_CANDIDATE_COMPLETENESS: "POLICY_INCOMPLETE_DATA",
    CHECK_MATCH_COMPLETENESS: "POLICY_INCOMPLETE_DATA",
    CHECK_SNAPSHOT_COMPLETENESS: "POLICY_INCOMPLETE_DATA",
    CHECK_CANDIDATE_FRESHNESS: "POLICY_STALE_DATA",
    CHECK_MATCH_FRESHNESS: "POLICY_STALE_DATA",
    CHECK_SNAPSHOT_FRESHNESS: "POLICY_STALE_DATA",
    CHECK_ENTRY_PRICE_MIN: "POLICY_OUTSIDE_ENTRY_BAND",
    CHECK_ENTRY_PRICE_MAX: "POLICY_OUTSIDE_ENTRY_BAND",
    CHECK_MIN_NET_EDGE: "POLICY_INSUFFICIENT_NET_EDGE",
    CHECK_DUPLICATE_RUN: "POLICY_DUPLICATE_RUN",
}

# Provenance for the engine's structural rules; the entry band and minimum
# net edge carry the configured provenance from PolicyConfig instead.
COMPLETENESS_RULE_SOURCE: Final = (
    "Kalakal policy engine completeness rule (architecture.md §6.2.7, "
    "§6.2.12): selected evidence must be complete and conflict-free."
)
FRESHNESS_RULE_SOURCE: Final = (
    "Kalakal policy engine freshness rule (architecture.md §6.2.7, §7.7): "
    "evidence is stale when valid_until precedes the evaluation time."
)
DUPLICATE_RULE_SOURCE: Final = (
    "Kalakal policy engine duplicate-run rule (architecture.md §6.2.7, "
    "§9.3): a duplicate run must not produce a second decision."
)

# Mirrors the ObservedValue bound of kalakal.domain.policy. Freshness
# observations saturate here; the sign is preserved, so saturation can
# never flip a pass into a fail or vice versa.
_OBSERVED_SECONDS_LIMIT: Final = 2_000_000

_MICROSECONDS_PER_SECOND: Final = 1_000_000


def policy_inputs_digest(
    *,
    candidate: CandidateMarket,
    match_context: MatchContext,
    snapshot: MarketSnapshot,
    edge: EdgeAssessment,
    evaluated_at: datetime,
    config: PolicyConfig,
    is_duplicate_run: bool,
) -> str:
    """Canonical digest of every value that can affect the policy decision.

    Declared entity content digests are retained for audit linkage, but
    they are caller-declared: only the fixture repository verifies them
    against raw bytes, and a Pydantic-valid entity can carry an unchanged
    declared digest with changed content. Every field the engine reads
    directly is therefore also bound explicitly. Booleans are encoded as
    integers 0/1; timestamps as normalized UTC ISO 8601 strings.

    Binding audit for the ten checks:

    - Completeness (1-3) reads only ``data_quality.is_complete`` — bound
      directly (``*_is_complete``). ``DataQuality`` validators make
      ``is_complete`` consistent with ``missing_fields``/``conflicts``,
      and no other DataQuality content can change a check result, so
      nothing deeper is bound; the declared entity digests remain the
      audit link to that detail.
    - Freshness (4-6) reads ``valid_until`` and ``evaluated_at`` — both
      bound directly (``*_valid_until``, ``evaluated_at``).
    - Entry band (7-8) observes ``snapshot.ask_price_micro``, which the
      cross-contract check pins to ``edge.ask_price_micro``, a field the
      ``EdgeAssessment`` validator recomputes into ``edge.inputs_digest``.
      Thresholds and provenance are in the configuration digest.
    - Net edge (9) observes ``edge.net_edge_ppm``, validator-recomputed
      from fields inside ``edge.inputs_digest``; threshold and provenance
      are in the configuration digest.
    - Duplicate run (10) is bound directly (``is_duplicate_run``).
    - Market/side identity is bound directly and cross-checked against
      every entity. Engine-constant thresholds (1/0) and rule-source
      strings change only with the engine revision named by
      ``policy_version``, which is inside the configuration digest.
    """
    return canonical_digest(
        {
            "market_id": candidate.market_id,
            "side": snapshot.side,
            "candidate_content_digest": candidate.provenance.content_digest,
            "match_context_content_digest": match_context.provenance.content_digest,
            "snapshot_content_digest": snapshot.provenance.content_digest,
            "candidate_is_complete": 1 if candidate.data_quality.is_complete else 0,
            "match_context_is_complete": (
                1 if match_context.data_quality.is_complete else 0
            ),
            "snapshot_is_complete": 1 if snapshot.data_quality.is_complete else 0,
            "candidate_valid_until": _canonical_utc(candidate.valid_until),
            "match_context_valid_until": _canonical_utc(match_context.valid_until),
            "snapshot_valid_until": _canonical_utc(snapshot.valid_until),
            "edge_inputs_digest": edge.inputs_digest,
            "evaluated_at": _canonical_utc(evaluated_at),
            "is_duplicate_run": 1 if is_duplicate_run else 0,
            "policy_config_digest": policy_config_digest(config),
        }
    )


def _canonical_utc(value: datetime) -> str:
    """Stable UTC ISO 8601 representation for digest payloads."""
    return value.astimezone(timezone.utc).isoformat()


def evaluate_policy(
    *,
    candidate: CandidateMarket,
    match_context: MatchContext,
    snapshot: MarketSnapshot,
    edge: EdgeAssessment,
    evaluated_at: datetime,
    config: PolicyConfig,
    is_duplicate_run: bool,
) -> PolicyDecision:
    """Apply every policy check and return the binding ``PolicyDecision``.

    ``evaluated_at`` is the caller-supplied evaluation clock (the engine
    never reads the wall clock) and is echoed as the decision's
    ``evaluated_at``. ``is_duplicate_run`` is the caller-verified duplicate
    status (§9.3); the engine has no persistence to consult.
    """
    _require_input_types(
        candidate=candidate,
        match_context=match_context,
        snapshot=snapshot,
        edge=edge,
        evaluated_at=evaluated_at,
        config=config,
        is_duplicate_run=is_duplicate_run,
    )
    _verify_cross_contract(
        candidate=candidate, match_context=match_context, snapshot=snapshot, edge=edge
    )

    ask = snapshot.ask_price_micro
    checks = (
        _completeness_check(CHECK_CANDIDATE_COMPLETENESS, candidate.data_quality),
        _completeness_check(CHECK_MATCH_COMPLETENESS, match_context.data_quality),
        _completeness_check(CHECK_SNAPSHOT_COMPLETENESS, snapshot.data_quality),
        _freshness_check(
            CHECK_CANDIDATE_FRESHNESS, candidate.valid_until, evaluated_at
        ),
        _freshness_check(
            CHECK_MATCH_FRESHNESS, match_context.valid_until, evaluated_at
        ),
        _freshness_check(CHECK_SNAPSHOT_FRESHNESS, snapshot.valid_until, evaluated_at),
        PolicyCheck(
            check_id=CHECK_ENTRY_PRICE_MIN,
            passed=ask >= config.min_entry_price_micro,
            observed_value=ask,
            threshold_value=config.min_entry_price_micro,
            threshold_source=config.entry_band_source,
        ),
        PolicyCheck(
            check_id=CHECK_ENTRY_PRICE_MAX,
            passed=ask <= config.max_entry_price_micro,
            observed_value=ask,
            threshold_value=config.max_entry_price_micro,
            threshold_source=config.entry_band_source,
        ),
        PolicyCheck(
            check_id=CHECK_MIN_NET_EDGE,
            passed=edge.net_edge_ppm >= config.min_net_edge_ppm,
            observed_value=edge.net_edge_ppm,
            threshold_value=config.min_net_edge_ppm,
            threshold_source=config.min_net_edge_source,
        ),
        PolicyCheck(
            check_id=CHECK_DUPLICATE_RUN,
            passed=not is_duplicate_run,
            observed_value=1 if is_duplicate_run else 0,
            threshold_value=0,
            threshold_source=DUPLICATE_RULE_SOURCE,
        ),
    )
    failed_reasons = {
        _CHECK_REASONS[check.check_id] for check in checks if not check.passed
    }
    reason_codes = tuple(
        code for code in POLICY_REASON_PRIORITY if code in failed_reasons
    )
    decision: PolicyOutcome = "no_bet" if failed_reasons else "proceed"
    return PolicyDecision(
        schema_version=SCHEMA_VERSION,
        decision=decision,
        reason_codes=reason_codes,
        checks=checks,
        policy_version=config.policy_version,
        evaluated_at=evaluated_at,
        inputs_digest=policy_inputs_digest(
            candidate=candidate,
            match_context=match_context,
            snapshot=snapshot,
            edge=edge,
            evaluated_at=evaluated_at,
            config=config,
            is_duplicate_run=is_duplicate_run,
        ),
    )


def verify_policy_decision(
    *,
    decision: PolicyDecision,
    candidate: CandidateMarket,
    match_context: MatchContext,
    snapshot: MarketSnapshot,
    edge: EdgeAssessment,
    config: PolicyConfig,
    is_duplicate_run: bool,
) -> None:
    """Verify ``decision`` by exact recomputation, or raise ``PolicyInputError``.

    Re-runs :func:`evaluate_policy` over the supplied evidence, edge,
    configuration, and duplicate-run status at the supplied decision's own
    recorded ``evaluated_at``, and requires exact equality with the
    recomputed result: outcome, reason codes and their order, the complete
    ordered check series with observed values, thresholds, and threshold
    provenance, ``policy_version``, ``evaluated_at``, and the full
    recomputed ``inputs_digest``. A caller-supplied digest is never trusted
    without recomputation, and matching displayed observations are never
    treated as sufficient.

    Pure like the engine itself: no clock lookup, no I/O, no environment
    reads, no mutation. Slice 6 orchestration must call this before
    explanation assembly, draft assembly, and terminal-record construction;
    a mismatch is a policy invariant/contract failure (safety-classified,
    e.g. ``POLICY_INVARIANT_BREACH``), never a no-bet.
    """
    if not isinstance(decision, PolicyDecision):
        raise PolicyInputError("decision must be a PolicyDecision instance")
    recomputed = evaluate_policy(
        candidate=candidate,
        match_context=match_context,
        snapshot=snapshot,
        edge=edge,
        evaluated_at=decision.evaluated_at,
        config=config,
        is_duplicate_run=is_duplicate_run,
    )
    if decision != recomputed:
        raise PolicyInputError(
            "supplied policy decision does not equal the exact recomputed "
            "policy result for the supplied evidence and configuration"
        )


def _completeness_check(check_id: str, quality: DataQuality) -> PolicyCheck:
    observed = 1 if quality.is_complete else 0
    return PolicyCheck(
        check_id=check_id,
        passed=observed >= 1,
        observed_value=observed,
        threshold_value=1,
        threshold_source=COMPLETENESS_RULE_SOURCE,
    )


def _freshness_check(
    check_id: str, valid_until: datetime, evaluated_at: datetime
) -> PolicyCheck:
    return PolicyCheck(
        check_id=check_id,
        passed=valid_until >= evaluated_at,
        observed_value=_seconds_until(valid_until, evaluated_at),
        threshold_value=0,
        threshold_source=FRESHNESS_RULE_SOURCE,
    )


def _seconds_until(valid_until: datetime, evaluated_at: datetime) -> int:
    """Whole seconds remaining until ``valid_until``, floored, saturated.

    Integer arithmetic only. Floor division keeps the sign consistent with
    the freshness rule: any expiry, even one microsecond, yields a negative
    observation, while exactly ``valid_until`` yields 0 (still fresh).
    """
    delta = valid_until - evaluated_at
    total_microseconds = (
        delta.days * 86_400 + delta.seconds
    ) * _MICROSECONDS_PER_SECOND + delta.microseconds
    seconds_floor = total_microseconds // _MICROSECONDS_PER_SECOND
    return max(-_OBSERVED_SECONDS_LIMIT, min(_OBSERVED_SECONDS_LIMIT, seconds_floor))


def _require_input_types(
    *,
    candidate: CandidateMarket,
    match_context: MatchContext,
    snapshot: MarketSnapshot,
    edge: EdgeAssessment,
    evaluated_at: datetime,
    config: PolicyConfig,
    is_duplicate_run: bool,
) -> None:
    for name, value, expected in (
        ("candidate", candidate, CandidateMarket),
        ("match_context", match_context, MatchContext),
        ("snapshot", snapshot, MarketSnapshot),
        ("edge", edge, EdgeAssessment),
        ("config", config, PolicyConfig),
    ):
        if not isinstance(value, expected):
            raise PolicyInputError(f"{name} must be a {expected.__name__} instance")
    if not isinstance(evaluated_at, datetime):
        raise PolicyInputError("evaluated_at must be a datetime")
    if evaluated_at.tzinfo is None or evaluated_at.utcoffset() != timedelta(0):
        raise PolicyInputError("evaluated_at must be timezone-aware UTC")
    if not isinstance(is_duplicate_run, bool):
        raise PolicyInputError("is_duplicate_run must be a bool")


def _verify_cross_contract(
    *,
    candidate: CandidateMarket,
    match_context: MatchContext,
    snapshot: MarketSnapshot,
    edge: EdgeAssessment,
) -> None:
    if match_context.market_id != candidate.market_id:
        raise PolicyInputError(
            "match_context.market_id does not reference the candidate market"
        )
    if snapshot.market_id != candidate.market_id:
        raise PolicyInputError(
            "snapshot.market_id does not reference the candidate market"
        )
    if edge.market_id != candidate.market_id:
        raise PolicyInputError("edge.market_id does not reference the candidate market")
    if edge.side != snapshot.side:
        raise PolicyInputError("edge.side does not match the snapshot side")
    if edge.ask_price_micro != snapshot.ask_price_micro:
        raise PolicyInputError(
            "edge.ask_price_micro does not match the snapshot ask price"
        )
    if edge.fee_model_version != snapshot.fee_model_version:
        raise PolicyInputError(
            "edge.fee_model_version does not match the snapshot fee-model reference"
        )
    if edge.snapshot_content_digest != snapshot.provenance.content_digest:
        raise PolicyInputError(
            "edge.snapshot_content_digest does not match the snapshot content digest"
        )
