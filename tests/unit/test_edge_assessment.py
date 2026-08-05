"""Unit tests for EdgeAssessment (§6.2.6): internal consistency enforced."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kalakal.domain import EdgeAssessment
from tests.unit import factories as f


class TestEdgeAssessmentValidity:
    def test_valid_reference_case(self) -> None:
        edge = EdgeAssessment(**f.edge_assessment_kwargs())
        assert edge.fee_estimate_micro == 6_000
        assert edge.gross_edge_ppm == 50_000
        assert edge.net_edge_ppm == 44_000

    def test_zero_fee_rate_valid(self) -> None:
        edge = f.make_edge_assessment(fee_rate_ppm=0)
        assert edge.fee_estimate_micro == 0
        assert edge.net_edge_ppm == edge.gross_edge_ppm

    def test_full_fee_rate_valid(self) -> None:
        edge = f.make_edge_assessment(fee_rate_ppm=1_000_000)
        assert edge.fee_estimate_micro == 600_000
        assert edge.net_edge_ppm == 50_000 - 600_000

    def test_negative_edge_valid(self) -> None:
        snapshot = f.make_market_snapshot(side="no")
        estimate = f.make_estimate(side="no")
        edge = f.make_edge_assessment(estimate, snapshot)
        assert edge.gross_edge_ppm == 350_000 - 600_000
        assert edge.net_edge_ppm == edge.gross_edge_ppm - 6_000

    def test_zero_gross_edge_valid(self) -> None:
        snapshot = f.make_market_snapshot(ask_price_micro=650_000)
        edge = f.make_edge_assessment(snapshot=snapshot)
        assert edge.gross_edge_ppm == 0
        assert edge.net_edge_ppm == -6_500


class TestEdgeAssessmentInconsistencyRejected:
    @pytest.mark.parametrize(
        ("field", "value", "message"),
        [
            ("fee_estimate_micro", 5_999, "fee_estimate_micro"),
            ("fee_estimate_micro", 6_001, "fee_estimate_micro"),
            ("gross_edge_ppm", 50_001, "gross_edge_ppm"),
            ("net_edge_ppm", 44_001, "net_edge_ppm"),
            ("inputs_digest", f.sha_hex("tampered"), "inputs_digest"),
        ],
    )
    def test_tampered_result_fields_rejected(
        self, field: str, value: object, message: str
    ) -> None:
        with pytest.raises(ValidationError, match=message):
            EdgeAssessment(**f.edge_assessment_kwargs(**{field: value}))

    @pytest.mark.parametrize(
        "field", ["probability_ppm", "ask_price_micro", "fee_rate_ppm"]
    )
    def test_tampered_inputs_rejected(self, field: str) -> None:
        kwargs = f.edge_assessment_kwargs()
        kwargs[field] = kwargs[field] + 1
        with pytest.raises(ValidationError):
            EdgeAssessment(**kwargs)

    def test_tampered_estimate_digest_rejected(self) -> None:
        with pytest.raises(ValidationError, match="inputs_digest"):
            EdgeAssessment(
                **f.edge_assessment_kwargs(
                    estimate_inputs_digest=f.sha_hex("other-estimate")
                )
            )


class TestEdgeAssessmentStructure:
    @pytest.mark.parametrize(
        "field",
        [
            "schema_version",
            "market_id",
            "side",
            "probability_ppm",
            "ask_price_micro",
            "fee_rate_ppm",
            "fee_model_version",
            "fee_estimate_micro",
            "gross_edge_ppm",
            "net_edge_ppm",
            "estimate_inputs_digest",
            "snapshot_content_digest",
            "inputs_digest",
            "computed_at",
        ],
    )
    def test_required_fields(self, field: str) -> None:
        kwargs = f.edge_assessment_kwargs()
        del kwargs[field]
        with pytest.raises(ValidationError):
            EdgeAssessment(**kwargs)

    @pytest.mark.parametrize("value", [-1, 1_000_001])
    def test_fee_rate_out_of_range_rejected(self, value: int) -> None:
        with pytest.raises(ValidationError):
            EdgeAssessment(**f.edge_assessment_kwargs(fee_rate_ppm=value))

    @pytest.mark.parametrize(
        "field",
        [
            "probability_ppm",
            "ask_price_micro",
            "fee_rate_ppm",
            "fee_estimate_micro",
            "gross_edge_ppm",
            "net_edge_ppm",
        ],
    )
    def test_float_values_rejected(self, field: str) -> None:
        kwargs = f.edge_assessment_kwargs()
        kwargs[field] = float(kwargs[field])
        with pytest.raises(ValidationError):
            EdgeAssessment(**kwargs)

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EdgeAssessment(**f.edge_assessment_kwargs(slippage_ppm=0))
