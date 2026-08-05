"""EdgeAssessment contract (architecture.md §6.2.6).

The model validator recomputes the documented integer arithmetic and the
inputs digest, so an internally inconsistent supplied assessment can never
validate. The public calculator lives in :mod:`kalakal.edge.calculator`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from kalakal.domain.primitives import (
    MICRO_PER_UNIT,
    AskPriceMicro,
    FeeMicro,
    FeeRatePpm,
    GrossEdgePpm,
    Identifier,
    MarketSide,
    NetEdgePpm,
    ProbabilityPpm,
    Sha256Hex,
    StrictModel,
    UtcDatetime,
    VersionStr,
    canonical_digest,
)


def edge_inputs_digest(
    *,
    market_id: str,
    side: str,
    probability_ppm: int,
    ask_price_micro: int,
    fee_rate_ppm: int,
    fee_model_version: str,
    estimate_inputs_digest: str,
    snapshot_content_digest: str,
) -> str:
    """Canonical, stable digest of the exact edge-calculation inputs."""
    return canonical_digest(
        {
            "market_id": market_id,
            "side": side,
            "probability_ppm": probability_ppm,
            "ask_price_micro": ask_price_micro,
            "fee_rate_ppm": fee_rate_ppm,
            "fee_model_version": fee_model_version,
            "estimate_inputs_digest": estimate_inputs_digest,
            "snapshot_content_digest": snapshot_content_digest,
        }
    )


class EdgeAssessment(StrictModel):
    """Deterministic integer edge and synthetic-fee assessment."""

    schema_version: Literal["1"]
    market_id: Identifier
    side: MarketSide
    probability_ppm: ProbabilityPpm
    ask_price_micro: AskPriceMicro
    fee_rate_ppm: FeeRatePpm
    fee_model_version: VersionStr
    fee_estimate_micro: FeeMicro
    gross_edge_ppm: GrossEdgePpm
    net_edge_ppm: NetEdgePpm
    estimate_inputs_digest: Sha256Hex
    snapshot_content_digest: Sha256Hex
    inputs_digest: Sha256Hex
    computed_at: UtcDatetime

    @model_validator(mode="after")
    def _check_arithmetic(self) -> EdgeAssessment:
        # Conservative ceiling division, integer-only (§6.2.6).
        expected_fee = -(-(self.ask_price_micro * self.fee_rate_ppm) // MICRO_PER_UNIT)
        if self.fee_estimate_micro != expected_fee:
            raise ValueError(
                f"fee_estimate_micro must equal ceil(ask*fee_rate/1e6)="
                f"{expected_fee}, got {self.fee_estimate_micro}"
            )
        expected_gross = self.probability_ppm - self.ask_price_micro
        if self.gross_edge_ppm != expected_gross:
            raise ValueError(
                f"gross_edge_ppm must equal probability-ask={expected_gross}, "
                f"got {self.gross_edge_ppm}"
            )
        expected_net = expected_gross - expected_fee
        if self.net_edge_ppm != expected_net:
            raise ValueError(
                f"net_edge_ppm must equal gross-fee={expected_net}, "
                f"got {self.net_edge_ppm}"
            )
        expected_digest = edge_inputs_digest(
            market_id=self.market_id,
            side=self.side,
            probability_ppm=self.probability_ppm,
            ask_price_micro=self.ask_price_micro,
            fee_rate_ppm=self.fee_rate_ppm,
            fee_model_version=self.fee_model_version,
            estimate_inputs_digest=self.estimate_inputs_digest,
            snapshot_content_digest=self.snapshot_content_digest,
        )
        if self.inputs_digest != expected_digest:
            raise ValueError("inputs_digest does not match the recorded inputs")
        return self
