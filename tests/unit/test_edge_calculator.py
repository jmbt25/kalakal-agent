"""Unit tests for the integer edge and synthetic-fee calculator (§6.2.6)."""

from __future__ import annotations

import pytest

from kalakal.edge.calculator import (
    EdgeInputError,
    calculate_edge,
    ceil_div,
    compute_fee_estimate_micro,
)
from tests.unit import factories as f


class TestReferenceCase:
    def test_documented_worked_example_exact(self) -> None:
        edge = calculate_edge(
            estimate=f.make_estimate(),  # probability 650_000 ppm by construction
            snapshot=f.make_market_snapshot(),  # ask 600_000 micro
            fee_rate_ppm=10_000,
            fee_model_version=f.FEE_MODEL_VERSION,
            computed_at=f.ts(2),
        )
        assert edge.probability_ppm == 650_000
        assert edge.ask_price_micro == 600_000
        assert edge.fee_rate_ppm == 10_000
        assert edge.fee_estimate_micro == 6_000
        assert edge.gross_edge_ppm == 50_000
        assert edge.net_edge_ppm == 44_000


class TestCeilDiv:
    @pytest.mark.parametrize(
        ("numerator", "denominator", "expected"),
        [
            (0, 1, 0),
            (1, 1_000_000, 1),
            (999_999, 1_000_000, 1),
            (1_000_000, 1_000_000, 1),
            (1_000_001, 1_000_000, 2),
            (6, 3, 2),
            (7, 3, 3),
        ],
    )
    def test_ceiling_behavior(
        self, numerator: int, denominator: int, expected: int
    ) -> None:
        assert ceil_div(numerator, denominator) == expected

    def test_negative_numerator_rejected(self) -> None:
        with pytest.raises(EdgeInputError):
            ceil_div(-1, 10)

    def test_zero_denominator_rejected(self) -> None:
        with pytest.raises(EdgeInputError):
            ceil_div(1, 0)

    @pytest.mark.parametrize(("numerator", "denominator"), [(1.0, 2), (2, True)])
    def test_non_int_rejected(self, numerator: object, denominator: object) -> None:
        with pytest.raises(EdgeInputError):
            ceil_div(numerator, denominator)  # type: ignore[arg-type]


class TestFeeComputation:
    @pytest.mark.parametrize(
        ("ask", "rate", "expected"),
        [
            (600_000, 10_000, 6_000),  # reference case
            (600_000, 0, 0),  # zero fee-rate boundary
            (600_000, 1_000_000, 600_000),  # full fee-rate boundary
            (1, 1, 1),  # ceiling: 1e-6 of 1 micro rounds up
            (999_999, 1, 1),
            (333_333, 3, 1),  # ceil(0.999999) = 1
            (999_999, 1_000_000, 999_999),
        ],
    )
    def test_ceiling_fee(self, ask: int, rate: int, expected: int) -> None:
        assert compute_fee_estimate_micro(ask, rate) == expected

    @pytest.mark.parametrize("rate", [-1, 1_000_001, 2_000_000])
    def test_out_of_range_rate_rejected_not_clamped(self, rate: int) -> None:
        with pytest.raises(EdgeInputError, match="fee_rate_ppm"):
            compute_fee_estimate_micro(600_000, rate)

    @pytest.mark.parametrize("ask", [0, -1, 1_000_000])
    def test_out_of_range_ask_rejected_not_clamped(self, ask: int) -> None:
        with pytest.raises(EdgeInputError, match="ask_price_micro"):
            compute_fee_estimate_micro(ask, 10_000)

    @pytest.mark.parametrize(
        ("ask", "rate"),
        [(600_000.0, 10_000), (600_000, 10_000.0), (True, 10_000), (600_000, False)],
    )
    def test_non_int_inputs_rejected(self, ask: object, rate: object) -> None:
        with pytest.raises(EdgeInputError, match="must be an int"):
            compute_fee_estimate_micro(ask, rate)  # type: ignore[arg-type]


class TestCalculateEdge:
    @pytest.mark.parametrize("rate", [0, 1_000_000])
    def test_boundary_fee_rates_accepted(self, rate: int) -> None:
        edge = f.make_edge_assessment(fee_rate_ppm=rate)
        assert edge.fee_rate_ppm == rate

    @pytest.mark.parametrize("rate", [-1, 1_000_001])
    def test_out_of_range_fee_rate_rejected(self, rate: int) -> None:
        with pytest.raises(EdgeInputError, match="fee_rate_ppm"):
            f.make_edge_assessment(fee_rate_ppm=rate)

    @pytest.mark.parametrize("rate", [10_000.0, True])
    def test_non_int_fee_rate_rejected(self, rate: object) -> None:
        with pytest.raises(EdgeInputError, match="must be an int"):
            f.make_edge_assessment(fee_rate_ppm=rate)  # type: ignore[arg-type]

    def test_negative_edges_are_valid_outputs(self) -> None:
        snapshot = f.make_market_snapshot(side="no")
        estimate = f.make_estimate(side="no")  # 350_000 ppm
        edge = f.make_edge_assessment(estimate, snapshot)
        assert edge.gross_edge_ppm == -250_000
        assert edge.net_edge_ppm == -256_000

    def test_market_mismatch_rejected(self) -> None:
        snapshot = f.make_market_snapshot(market_id="mkt-2")
        with pytest.raises(EdgeInputError, match="same market"):
            f.make_edge_assessment(snapshot=snapshot)

    def test_side_mismatch_rejected(self) -> None:
        snapshot = f.make_market_snapshot(side="no")
        with pytest.raises(EdgeInputError, match="same side"):
            f.make_edge_assessment(snapshot=snapshot)

    def test_fee_model_version_mismatch_rejected(self) -> None:
        with pytest.raises(EdgeInputError, match="fee_model_version"):
            calculate_edge(
                estimate=f.make_estimate(),
                snapshot=f.make_market_snapshot(),
                fee_rate_ppm=10_000,
                fee_model_version="synthetic-fee-2",
                computed_at=f.ts(2),
            )

    def test_deterministic_bit_for_bit(self) -> None:
        first = f.make_edge_assessment()
        second = f.make_edge_assessment()
        assert first == second
        assert first.model_dump_json() == second.model_dump_json()
        assert first.inputs_digest == second.inputs_digest

    def test_digest_links_estimate_and_snapshot(self) -> None:
        edge = f.make_edge_assessment()
        assert edge.estimate_inputs_digest == f.make_estimate().inputs_digest
        assert (
            edge.snapshot_content_digest
            == f.make_market_snapshot().provenance.content_digest
        )
