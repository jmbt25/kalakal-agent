"""Deterministic simulated Discord-draft generation (§6.2.9, slice 5).

Pure and stateless: no clock, no I/O, no Discord, no environment reads,
and deliberately no process-local registry or other mutable state.

Slice 5 guarantees **deterministic rendering only**: identical complete
inputs produce an equal :class:`SimulatedDiscordDraft` with byte-identical
``draft_text``, and :func:`draft_identity_key` exposes the stable logical
identity ``(run_id, market_id, side)``. Deterministic repeatability is not
operational idempotency, and this module makes no operational uniqueness
claim. The architecture-level "at most one draft per (run, market, side)"
invariant (§6.2.9) is owned by slice 6 orchestration, which memoizes (or
otherwise retains) the first generated result per identity, never emits or
persists a second draft for the same identity, and answers a later call
with changed inputs for an existing identity by returning the original
result or failing with a typed conflict — never by creating a replacement
draft.

A draft exists only for a binding policy ``proceed`` that has been
verified by exact recomputation (:func:`kalakal.policy.engine.verify_policy_decision`):
a ``no_bet`` yields the typed :class:`DraftSkippedNoBet` absence (a normal
outcome, never a failure), and a snapshot already expired at generation
yields the typed :class:`DraftStaleAtGeneration` refusal — validity is
never extended artificially. All numbers are rendered from the validated
deterministic contracts with integer arithmetic only; no ``float`` exists
anywhere on these paths.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Final, Literal

from pydantic import Field, ValidationError

from kalakal.domain.draft import SimulatedDiscordDraft
from kalakal.domain.edge import EdgeAssessment
from kalakal.domain.estimate import ProbabilityEstimate
from kalakal.domain.invocation import MarketSelection
from kalakal.domain.match import MATCH_ESTIMATOR_FIELDS
from kalakal.domain.policy import PolicyDecision
from kalakal.domain.primitives import (
    DEMO_ESTIMATOR_DISPLAY_LABEL,
    MICRO_PER_UNIT,
    PPM_PER_UNIT,
    SCHEMA_VERSION,
    SIMULATION_DRAFT_LABEL,
    Identifier,
    MarketSide,
    MediumText,
    StrictModel,
    UtcDatetime,
    VersionStr,
)
from kalakal.domain.record import CandidateEligibility
from kalakal.policy.config import FIXTURE_POLICY_CONFIG, PolicyConfig
from kalakal.policy.engine import PolicyInputError, verify_policy_decision

# NetEdgePpm domain bound (§6.2.6): |value| stays inside 2_000_000 ppm.
_SIGNED_PPM_LIMIT: Final = 2_000_000

# Cents carry four fixed decimal places: 10_000 micro-USD per hundredth of
# a cent scale — 1¢ = 10_000 micro-USD.
_MICRO_PER_CENT: Final = 10_000
# Percent carries four fixed decimal places: 10_000 ppm per percent point.
_PPM_PER_PERCENT: Final = 10_000


class DraftGenerationError(ValueError):
    """Cross-contract or structural draft-input mismatch — never a no-bet.

    Messages name typed fields and validated identifiers only; they never
    echo arbitrary raw content.
    """


class SimulatedDraftConfig(StrictModel):
    """Immutable, versioned configuration of the fixture draft simulation.

    Constructor-supplied only: nothing reads environment variables, files,
    or mutable global state. ``renderer_version`` names the exact rendering
    revision for reproducibility and is recorded on every generated draft
    and on every stale result (both carry renderer-derived content);
    changing any template in this module requires a new version string.
    """

    renderer_version: VersionStr
    max_draft_lifetime_seconds: Annotated[int, Field(ge=1, le=86_400)]
    stale_regeneration_warning: MediumText


FIXTURE_DRAFT_CONFIG: Final = SimulatedDraftConfig(
    renderer_version="fixture-draft-1",
    max_draft_lifetime_seconds=1_800,
    stale_regeneration_warning=(
        "Simulation staleness warning: this synthetic draft is void after "
        "its expiry timestamp; regenerate the simulation for fresh "
        "synthetic values."
    ),
)


class DraftSkippedNoBet(StrictModel):
    """Documented normal absence: a policy no-bet produces no draft."""

    reason: Literal["policy_no_bet"]
    run_id: Identifier
    market_id: Identifier
    side: MarketSide


class DraftStaleAtGeneration(StrictModel):
    """Bounded typed refusal: the snapshot expired before generation began.

    The caller must regenerate from a fresh deterministic chain; the
    snapshot's validity is never extended artificially. Because the
    regeneration warning is renderer-configuration content, the producing
    renderer version is recorded here too.
    """

    reason: Literal["snapshot_expired"]
    run_id: Identifier
    market_id: Identifier
    side: MarketSide
    renderer_version: VersionStr
    snapshot_valid_until: UtcDatetime
    generated_at: UtcDatetime
    regeneration_warning: MediumText


SimulatedDraftOutcome = (
    SimulatedDiscordDraft | DraftSkippedNoBet | DraftStaleAtGeneration
)


def draft_identity_key(
    *, run_id: str, market_id: str, side: MarketSide
) -> tuple[str, str, str]:
    """The stable logical draft identity ``(run_id, market_id, side)``.

    Slice 5 only defines the key; it enforces no uniqueness. Slice 6
    orchestration owns the operational §6.2.9 invariant: it memoizes the
    first generated result per identity, never emits or persists a second
    draft for the same identity, and treats a later call with changed
    inputs for an existing identity as "return the original result or fail
    with a typed conflict" — never as a replacement draft.
    """
    return (run_id, market_id, side)


# --- Exact deterministic integer formatting (no float, no locale) ---


def _require_int(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise DraftGenerationError(f"{name} must be an int, got {type(value).__name__}")


def format_micro_as_cents(value_micro: int) -> str:
    """Render micro-USD as cents with four fixed decimals: 600_000 → 60.0000¢."""
    _require_int("value_micro", value_micro)
    if not 0 <= value_micro <= MICRO_PER_UNIT:
        raise DraftGenerationError(
            f"value_micro must satisfy 0 <= value <= {MICRO_PER_UNIT}, "
            f"got {value_micro}"
        )
    whole, fraction = divmod(value_micro, _MICRO_PER_CENT)
    return f"{whole}.{fraction:04d}¢"


def format_ppm_as_percent(value_ppm: int) -> str:
    """Render ppm as percent with four fixed decimals: 650_000 → 65.0000%."""
    _require_int("value_ppm", value_ppm)
    if not 0 <= value_ppm <= PPM_PER_UNIT:
        raise DraftGenerationError(
            f"value_ppm must satisfy 0 <= value <= {PPM_PER_UNIT}, got {value_ppm}"
        )
    whole, fraction = divmod(value_ppm, _PPM_PER_PERCENT)
    return f"{whole}.{fraction:04d}%"


def format_ppm_as_signed_points(value_ppm: int) -> str:
    """Render ppm as signed percentage points: 44_000 → +4.4000 percentage
    points; negative values retain their minus sign."""
    _require_int("value_ppm", value_ppm)
    if not -_SIGNED_PPM_LIMIT <= value_ppm <= _SIGNED_PPM_LIMIT:
        raise DraftGenerationError(
            f"value_ppm must satisfy |value| <= {_SIGNED_PPM_LIMIT}, got {value_ppm}"
        )
    sign = "-" if value_ppm < 0 else "+"
    whole, fraction = divmod(abs(value_ppm), _PPM_PER_PERCENT)
    return f"{sign}{whole}.{fraction:04d} percentage points"


def format_utc_timestamp(value: datetime) -> str:
    """Canonical UTC RFC 3339 ``Z`` rendering of one aware UTC timestamp."""
    if not isinstance(value, datetime):
        raise DraftGenerationError("timestamp must be a datetime")
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise DraftGenerationError("timestamp must be timezone-aware UTC")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# --- Draft generation ---


def _require_input_types(
    *,
    consideration: CandidateEligibility,
    selection: MarketSelection,
    estimate: ProbabilityEstimate,
    edge: EdgeAssessment,
    policy_decision: PolicyDecision,
    generated_at: datetime,
    config: SimulatedDraftConfig,
    policy_config: PolicyConfig,
    is_duplicate_run: bool,
) -> None:
    for name, value, expected in (
        ("consideration", consideration, CandidateEligibility),
        ("selection", selection, MarketSelection),
        ("estimate", estimate, ProbabilityEstimate),
        ("edge", edge, EdgeAssessment),
        ("policy_decision", policy_decision, PolicyDecision),
        ("config", config, SimulatedDraftConfig),
        ("policy_config", policy_config, PolicyConfig),
    ):
        if not isinstance(value, expected):
            raise DraftGenerationError(f"{name} must be a {expected.__name__} instance")
    if not isinstance(generated_at, datetime):
        raise DraftGenerationError("generated_at must be a datetime")
    if generated_at.tzinfo is None or generated_at.utcoffset() != timedelta(0):
        raise DraftGenerationError("generated_at must be timezone-aware UTC")
    if not isinstance(is_duplicate_run, bool):
        raise DraftGenerationError("is_duplicate_run must be a bool")


def generate_simulated_draft(
    *,
    run_id: str,
    consideration: CandidateEligibility,
    selection: MarketSelection,
    estimate: ProbabilityEstimate,
    edge: EdgeAssessment,
    policy_decision: PolicyDecision,
    generated_at: datetime,
    config: SimulatedDraftConfig = FIXTURE_DRAFT_CONFIG,
    policy_config: PolicyConfig = FIXTURE_POLICY_CONFIG,
    is_duplicate_run: bool = False,
) -> SimulatedDraftOutcome:
    """Generate the simulated draft for one validated ``proceed`` chain.

    Every contract must belong to the same deterministic input chain: the
    selection must target the considered candidate on its recorded
    evaluation side; the estimate must target that market and side **and**
    carry a basis equal, field for field, to the considered match context
    (matching displayed numbers or matching target IDs are never treated
    as sufficient evidence binding); the edge must match the estimate and
    snapshot by value and digest; and the supplied policy decision must
    equal, exactly, the policy result recomputed from that evidence with
    the supplied ``policy_config`` and ``is_duplicate_run`` — the fixture
    defaults are conveniences, and slice 6 passes both deliberately.

    A proceed draft additionally requires truthful stage-time ordering
    (``estimate.computed_at <= edge.computed_at <=
    policy_decision.evaluated_at <= generated_at``; equality is allowed
    because deterministic fixture stages may share one effective
    evaluation timestamp). ``expires_at`` is
    ``min(snapshot.valid_until, generated_at + configured lifetime)`` and
    must fall strictly after ``generated_at``.
    """
    _require_input_types(
        consideration=consideration,
        selection=selection,
        estimate=estimate,
        edge=edge,
        policy_decision=policy_decision,
        generated_at=generated_at,
        config=config,
        policy_config=policy_config,
        is_duplicate_run=is_duplicate_run,
    )
    market = consideration.market
    snapshot = consideration.market_snapshot
    if not consideration.eligible:
        raise DraftGenerationError(
            "the selected consideration is not an eligible candidate"
        )
    if selection.selected_market_id != market.market_id:
        raise DraftGenerationError("selection does not target the considered market")
    if selection.selected_side != consideration.evaluation_side:
        raise DraftGenerationError(
            "selection side does not equal the consideration's evaluation side"
        )
    side = selection.selected_side
    if estimate.market_id != market.market_id or estimate.side != side:
        raise DraftGenerationError(
            "probability estimate does not target the selected market and side"
        )
    # Record-layer basis binding (§6.2.10): the complete estimator basis
    # must equal the considered match context, so a foreign basis is
    # rejected even when it happens to reproduce the same probability.
    if estimate.basis.match_id != consideration.match_context.match_id:
        raise DraftGenerationError(
            "estimate basis does not reference the considered match context"
        )
    for field_name in MATCH_ESTIMATOR_FIELDS:
        if getattr(estimate.basis, field_name) != getattr(
            consideration.match_context, field_name
        ):
            raise DraftGenerationError(
                "estimate basis does not equal the recorded match-context evidence"
            )
    if edge.market_id != market.market_id or edge.side != side:
        raise DraftGenerationError(
            "edge assessment does not target the selected market and side"
        )
    if edge.probability_ppm != estimate.probability_ppm:
        raise DraftGenerationError(
            "edge probability does not equal the recorded estimate"
        )
    if edge.ask_price_micro != snapshot.ask_price_micro:
        raise DraftGenerationError(
            "edge ask price does not equal the recorded snapshot"
        )
    if edge.fee_model_version != snapshot.fee_model_version:
        raise DraftGenerationError(
            "edge fee-model version does not equal the snapshot reference"
        )
    if edge.estimate_inputs_digest != estimate.inputs_digest:
        raise DraftGenerationError(
            "edge estimate digest does not equal the estimate inputs digest"
        )
    if edge.snapshot_content_digest != snapshot.provenance.content_digest:
        raise DraftGenerationError(
            "edge snapshot digest does not equal the snapshot content digest"
        )
    # Exact policy verification: the supplied decision must equal the
    # result recomputed by the real engine over this exact evidence chain,
    # configuration, and duplicate-run status — outcome, ordered reason
    # codes, complete ordered check series, observed values, thresholds,
    # provenance, policy version, evaluation time, and full recomputed
    # inputs digest. A well-shaped caller-supplied digest is never trusted.
    try:
        verify_policy_decision(
            decision=policy_decision,
            candidate=market,
            match_context=consideration.match_context,
            snapshot=snapshot,
            edge=edge,
            config=policy_config,
            is_duplicate_run=is_duplicate_run,
        )
    except PolicyInputError:
        raise DraftGenerationError(
            "supplied policy decision does not equal the exact recomputed "
            "policy result for the selected evidence"
        ) from None
    if policy_decision.decision != "proceed":
        return DraftSkippedNoBet(
            reason="policy_no_bet",
            run_id=run_id,
            market_id=market.market_id,
            side=side,
        )
    # Truthful stage-time ordering for a proceed draft; equality is allowed
    # because deterministic fixture stages can share one effective
    # evaluation timestamp (§7.7).
    if estimate.computed_at > edge.computed_at:
        raise DraftGenerationError(
            "edge assessment must not be computed before the probability estimate"
        )
    if edge.computed_at > policy_decision.evaluated_at:
        raise DraftGenerationError(
            "policy decision must not be evaluated before the edge assessment"
        )
    if policy_decision.evaluated_at > generated_at:
        raise DraftGenerationError(
            "draft generation must not precede the policy evaluation"
        )
    if snapshot.valid_until <= generated_at:
        return DraftStaleAtGeneration(
            reason="snapshot_expired",
            run_id=run_id,
            market_id=market.market_id,
            side=side,
            renderer_version=config.renderer_version,
            snapshot_valid_until=snapshot.valid_until,
            generated_at=generated_at,
            regeneration_warning=config.stale_regeneration_warning,
        )
    ttl_expiry = generated_at + timedelta(seconds=config.max_draft_lifetime_seconds)
    expires_at = min(snapshot.valid_until, ttl_expiry)
    if expires_at <= generated_at:
        raise DraftGenerationError("draft expiry must fall strictly after generation")
    side_meaning = market.yes_means if side == "yes" else market.no_means
    ask_text = format_micro_as_cents(snapshot.ask_price_micro)
    probability_text = format_ppm_as_percent(estimate.probability_ppm)
    edge_text = format_ppm_as_signed_points(edge.net_edge_ppm)
    generated_text = format_utc_timestamp(generated_at)
    expires_text = format_utc_timestamp(expires_at)
    draft_text = "\n".join(
        (
            SIMULATION_DRAFT_LABEL,
            "Synthetic fixture data only; every value below is invented.",
            f"Event: {market.event_name}",
            f"Side: {side} — {side_meaning}",
            f"Synthetic market link: {market.market_link}",
            f"Ask: {ask_text}",
            f"Estimate: {probability_text} ({DEMO_ESTIMATOR_DISPLAY_LABEL})",
            f"Estimated net edge: {edge_text}",
            "#nfa",
            f"Generated: {generated_text}",
            f"Expires: {expires_text}",
            config.stale_regeneration_warning,
        )
    )
    try:
        return SimulatedDiscordDraft(
            schema_version=SCHEMA_VERSION,
            run_id=run_id,
            market_id=market.market_id,
            side=side,
            is_simulation=True,
            renderer_version=config.renderer_version,
            simulation_label=SIMULATION_DRAFT_LABEL,
            event_name=market.event_name,
            side_meaning=side_meaning,
            market_link=market.market_link,
            ask_price_micro=snapshot.ask_price_micro,
            probability_ppm=estimate.probability_ppm,
            estimator_display_label=DEMO_ESTIMATOR_DISPLAY_LABEL,
            net_edge_ppm=edge.net_edge_ppm,
            nfa_tag="#nfa",
            generated_at=generated_at,
            expires_at=expires_at,
            stale_regeneration_warning=config.stale_regeneration_warning,
            draft_text=draft_text,
        )
    except ValidationError:
        raise DraftGenerationError(
            "generated draft failed contract validation"
        ) from None
