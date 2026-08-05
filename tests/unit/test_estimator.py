"""Unit tests for the deterministic demo estimator (§10.1).

The exact demo formula under test (versioned demo/1.0.0, NOT PREDICTIVE):

    score_yes = yes_team_rating + yes_team_form
    score_no  = no_team_rating + no_team_form
    p_yes_ppm = (score_yes * 1_000_000) // (score_yes + score_no)
    probability_ppm = p_yes_ppm (side "yes") | 1_000_000 - p_yes_ppm (side "no")

The market-side mapping is structural (side-named schema fields), never
positional.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from kalakal.domain import (
    DEMO_ESTIMATOR_DISPLAY_LABEL,
    MATCH_ESTIMATOR_FIELDS,
    DataQuality,
    EstimatorRejection,
    ProbabilityEstimate,
    estimate_inputs_digest,
)
from kalakal.domain.primitives import MarketSide
from kalakal.estimator.demo import (
    DEMO_ESTIMATOR_ID,
    DEMO_ESTIMATOR_VERSION,
    DemoEstimator,
)
from kalakal.estimator.interface import ProbabilityEstimator
from tests.unit import factories as f


def incomplete_quality(*missing: str) -> DataQuality:
    return DataQuality(is_complete=False, missing_fields=tuple(missing), conflicts=())


class TestDemoFormula:
    @pytest.mark.parametrize(
        ("yes_rating", "yes_form", "no_rating", "no_form", "side", "expected_ppm"),
        [
            # Factory reference inputs: scores 650 vs 350 of 1000.
            (600, 50, 310, 40, "yes", 650_000),
            (600, 50, 310, 40, "no", 350_000),
            # Symmetric teams.
            (1000, 0, 1000, 0, "yes", 500_000),
            (1000, 0, 1000, 0, "no", 500_000),
            # Floor division: scores 1 vs 2 -> 333_333 ppm.
            (1, 0, 2, 0, "yes", 333_333),
            (1, 0, 2, 0, "no", 666_667),
            # Extreme spread stays inside 0..1_000_000.
            (10_000, 100, 1, 0, "yes", 999_900),
            (10_000, 100, 1, 0, "no", 100),
        ],
    )
    def test_exact_formula(
        self,
        yes_rating: int,
        yes_form: int,
        no_rating: int,
        no_form: int,
        side: MarketSide,
        expected_ppm: int,
    ) -> None:
        match = f.make_match_context(
            yes_team_rating=yes_rating,
            yes_team_form=yes_form,
            no_team_rating=no_rating,
            no_team_form=no_form,
        )
        result = DemoEstimator().estimate(match, side, computed_at=f.ts(1))
        assert isinstance(result, ProbabilityEstimate)
        assert result.probability_ppm == expected_ppm
        assert 0 <= result.probability_ppm <= 1_000_000

    def test_side_mapping_is_structural_not_positional(self) -> None:
        # Swapping the side-named inputs must invert the yes-probability:
        # the formula binds to yes_/no_ fields, not to declaration order.
        swapped = f.make_match_context(
            yes_team_rating=f.NO_TEAM_RATING,
            yes_team_form=f.NO_TEAM_FORM,
            no_team_rating=f.YES_TEAM_RATING,
            no_team_form=f.YES_TEAM_FORM,
        )
        result = DemoEstimator().estimate(swapped, "yes", computed_at=f.ts(1))
        assert isinstance(result, ProbabilityEstimate)
        assert result.probability_ppm == 350_000
        assert result.basis.yes_team_rating == f.NO_TEAM_RATING

    def test_estimate_metadata(self) -> None:
        result = DemoEstimator().estimate(
            f.make_match_context(), "yes", computed_at=f.ts(1)
        )
        assert isinstance(result, ProbabilityEstimate)
        assert result.estimator_id == DEMO_ESTIMATOR_ID
        assert result.estimator_version == DEMO_ESTIMATOR_VERSION
        assert result.is_predictive is False
        assert result.display_label == DEMO_ESTIMATOR_DISPLAY_LABEL
        assert result.market_id == f.MARKET_ID
        assert result.side == "yes"
        assert result.computed_at == f.ts(1)
        assert result.basis.match_id == f.MATCH_ID

    def test_interface_binding(self) -> None:
        assert issubclass(DemoEstimator, ProbabilityEstimator)


class TestDeterminism:
    def test_same_inputs_bit_identical_output_and_digest(self) -> None:
        estimator = DemoEstimator()
        match = f.make_match_context()
        first = estimator.estimate(match, "yes", computed_at=f.ts(1))
        second = estimator.estimate(f.make_match_context(), "yes", computed_at=f.ts(1))
        assert isinstance(first, ProbabilityEstimate)
        assert isinstance(second, ProbabilityEstimate)
        assert first == second
        assert first.model_dump_json() == second.model_dump_json()
        assert first.inputs_digest == second.inputs_digest

    def test_digest_matches_canonical_recomputation(self) -> None:
        result = DemoEstimator().estimate(
            f.make_match_context(), "yes", computed_at=f.ts(1)
        )
        assert isinstance(result, ProbabilityEstimate)
        assert result.inputs_digest == estimate_inputs_digest(
            estimator_id=DEMO_ESTIMATOR_ID,
            estimator_version=DEMO_ESTIMATOR_VERSION,
            market_id=f.MARKET_ID,
            side="yes",
            basis=result.basis,
        )

    def test_digest_changes_with_inputs(self) -> None:
        base = DemoEstimator().estimate(
            f.make_match_context(), "yes", computed_at=f.ts(1)
        )
        changed = DemoEstimator().estimate(
            f.make_match_context(yes_team_form=51), "yes", computed_at=f.ts(1)
        )
        assert isinstance(base, ProbabilityEstimate)
        assert isinstance(changed, ProbabilityEstimate)
        assert base.inputs_digest != changed.inputs_digest

    def test_digest_stable_across_computed_at(self) -> None:
        first = DemoEstimator().estimate(
            f.make_match_context(), "yes", computed_at=f.ts(1)
        )
        second = DemoEstimator().estimate(
            f.make_match_context(), "yes", computed_at=f.ts(9)
        )
        assert isinstance(first, ProbabilityEstimate)
        assert isinstance(second, ProbabilityEstimate)
        assert first.inputs_digest == second.inputs_digest


class TestFieldSpecificRejection:
    @pytest.mark.parametrize("field", MATCH_ESTIMATOR_FIELDS)
    def test_missing_estimator_field_rejected(self, field: str) -> None:
        match = f.make_match_context(
            **{field: None}, data_quality=incomplete_quality(field)
        )
        result = DemoEstimator().estimate(match, "yes", computed_at=f.ts(1))
        assert isinstance(result, EstimatorRejection)
        assert result.missing_fields == (field,)
        assert result.conflicted_fields == ()

    @pytest.mark.parametrize("field", MATCH_ESTIMATOR_FIELDS)
    def test_conflicted_estimator_field_rejected(self, field: str) -> None:
        quality = DataQuality(
            is_complete=False,
            missing_fields=(),
            conflicts=(f.make_conflict(field),),
        )
        match = f.make_match_context(data_quality=quality)
        result = DemoEstimator().estimate(match, "yes", computed_at=f.ts(1))
        assert isinstance(result, EstimatorRejection)
        assert result.conflicted_fields == (field,)
        assert result.missing_fields == ()

    def test_missing_and_conflicted_both_reported(self) -> None:
        quality = DataQuality(
            is_complete=False,
            missing_fields=("yes_team_rating",),
            conflicts=(f.make_conflict("no_team_form"),),
        )
        match = f.make_match_context(yes_team_rating=None, data_quality=quality)
        result = DemoEstimator().estimate(match, "yes", computed_at=f.ts(1))
        assert isinstance(result, EstimatorRejection)
        assert result.missing_fields == ("yes_team_rating",)
        assert result.conflicted_fields == ("no_team_form",)

    def test_field_both_missing_and_conflicted_reported_once(self) -> None:
        # A conflict on a field that is also missing is reported as missing
        # only: each field appears in exactly one rejection collection.
        quality = DataQuality(
            is_complete=False,
            missing_fields=("yes_team_rating",),
            conflicts=(f.make_conflict("yes_team_rating"),),
        )
        match = f.make_match_context(yes_team_rating=None, data_quality=quality)
        result = DemoEstimator().estimate(match, "yes", computed_at=f.ts(1))
        assert isinstance(result, EstimatorRejection)
        assert result.missing_fields == ("yes_team_rating",)
        assert result.conflicted_fields == ()

    def test_rejection_invents_no_values(self) -> None:
        match = f.make_match_context(
            yes_team_rating=None, data_quality=incomplete_quality("yes_team_rating")
        )
        result = DemoEstimator().estimate(match, "yes", computed_at=f.ts(1))
        assert isinstance(result, EstimatorRejection)
        assert not hasattr(result, "probability_ppm")
        assert not hasattr(result, "basis")


class TestNonEstimatorGapsAccepted:
    def test_conflict_on_non_estimator_field_accepted(self) -> None:
        quality = DataQuality(
            is_complete=False,
            missing_fields=(),
            conflicts=(f.make_conflict("patch_label"),),
        )
        match = f.make_match_context(data_quality=quality)
        result = DemoEstimator().estimate(match, "yes", computed_at=f.ts(1))
        assert isinstance(result, ProbabilityEstimate)
        assert result.probability_ppm == 650_000

    def test_multiple_non_estimator_conflicts_accepted(self) -> None:
        quality = DataQuality(
            is_complete=False,
            missing_fields=(),
            conflicts=(
                f.make_conflict("patch_label"),
                f.make_conflict("tournament_tier"),
            ),
        )
        match = f.make_match_context(data_quality=quality)
        result = DemoEstimator().estimate(match, "yes", computed_at=f.ts(1))
        assert isinstance(result, ProbabilityEstimate)


class TestEstimatorInputHandling:
    def test_naive_computed_at_raises(self) -> None:
        with pytest.raises(ValidationError):
            DemoEstimator().estimate(
                f.make_match_context(),
                "yes",
                computed_at=datetime(2026, 8, 5, 12, 0),
            )
