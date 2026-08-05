"""Deterministic integer edge and synthetic-fee calculator (§6.2.6).

Pure integer arithmetic; conservative ceiling division for the fee so the
net edge is never overstated. The synthetic fee model is versioned fixture
configuration, not Jupiter's real (unpublished) fee formula.
"""

from __future__ import annotations

from datetime import datetime

from kalakal.domain.edge import EdgeAssessment, edge_inputs_digest
from kalakal.domain.estimate import ProbabilityEstimate
from kalakal.domain.market import MarketSnapshot
from kalakal.domain.primitives import MICRO_PER_UNIT, PPM_PER_UNIT, SCHEMA_VERSION


class EdgeInputError(ValueError):
    """A rejected (never clamped) edge-calculation input."""


def _require_int(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise EdgeInputError(f"{name} must be an int, got {type(value).__name__}")


def ceil_div(numerator: int, denominator: int) -> int:
    """Integer ceiling division without floats (non-negative numerator)."""
    _require_int("numerator", numerator)
    _require_int("denominator", denominator)
    if numerator < 0 or denominator <= 0:
        raise EdgeInputError("ceil_div requires numerator >= 0 and denominator > 0")
    return -(-numerator // denominator)


def compute_fee_estimate_micro(ask_price_micro: int, fee_rate_ppm: int) -> int:
    """``ceil(ask_price_micro * fee_rate_ppm / 1_000_000)`` in micro-USD."""
    _require_int("ask_price_micro", ask_price_micro)
    _require_int("fee_rate_ppm", fee_rate_ppm)
    if not 0 < ask_price_micro < MICRO_PER_UNIT:
        raise EdgeInputError(
            f"ask_price_micro must satisfy 0 < ask < {MICRO_PER_UNIT}, "
            f"got {ask_price_micro}"
        )
    if not 0 <= fee_rate_ppm <= PPM_PER_UNIT:
        raise EdgeInputError(
            f"fee_rate_ppm must satisfy 0 <= rate <= {PPM_PER_UNIT}, got {fee_rate_ppm}"
        )
    return ceil_div(ask_price_micro * fee_rate_ppm, MICRO_PER_UNIT)


def calculate_edge(
    *,
    estimate: ProbabilityEstimate,
    snapshot: MarketSnapshot,
    fee_rate_ppm: int,
    fee_model_version: str,
    computed_at: datetime,
) -> EdgeAssessment:
    """Compute the deterministic EdgeAssessment for one (market, side).

    ``computed_at`` is supplied by the caller; the calculator never reads the
    wall clock. Inconsistent inputs are rejected, never reconciled.
    """
    _require_int("fee_rate_ppm", fee_rate_ppm)
    if not 0 <= fee_rate_ppm <= PPM_PER_UNIT:
        raise EdgeInputError(
            f"fee_rate_ppm must satisfy 0 <= rate <= {PPM_PER_UNIT}, got {fee_rate_ppm}"
        )
    if estimate.market_id != snapshot.market_id:
        raise EdgeInputError("estimate and snapshot must describe the same market")
    if estimate.side != snapshot.side:
        raise EdgeInputError("estimate and snapshot must describe the same side")
    if fee_model_version != snapshot.fee_model_version:
        raise EdgeInputError(
            "fee_model_version must match the snapshot's fee-model reference"
        )
    fee_estimate_micro = compute_fee_estimate_micro(
        snapshot.ask_price_micro, fee_rate_ppm
    )
    gross_edge_ppm = estimate.probability_ppm - snapshot.ask_price_micro
    net_edge_ppm = gross_edge_ppm - fee_estimate_micro
    return EdgeAssessment(
        schema_version=SCHEMA_VERSION,
        market_id=snapshot.market_id,
        side=snapshot.side,
        probability_ppm=estimate.probability_ppm,
        ask_price_micro=snapshot.ask_price_micro,
        fee_rate_ppm=fee_rate_ppm,
        fee_model_version=fee_model_version,
        fee_estimate_micro=fee_estimate_micro,
        gross_edge_ppm=gross_edge_ppm,
        net_edge_ppm=net_edge_ppm,
        estimate_inputs_digest=estimate.inputs_digest,
        snapshot_content_digest=snapshot.provenance.content_digest,
        inputs_digest=edge_inputs_digest(
            market_id=snapshot.market_id,
            side=snapshot.side,
            probability_ppm=estimate.probability_ppm,
            ask_price_micro=snapshot.ask_price_micro,
            fee_rate_ppm=fee_rate_ppm,
            fee_model_version=fee_model_version,
            estimate_inputs_digest=estimate.inputs_digest,
            snapshot_content_digest=snapshot.provenance.content_digest,
        ),
        computed_at=computed_at,
    )
