"""Unit tests for ProbabilityEstimate and EstimatorRejection (§6.2.5)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest
from pydantic import ValidationError

from kalakal.domain import (
    EstimatorBasis,
    EstimatorRejection,
    ProbabilityEstimate,
    estimate_inputs_digest,
)
from tests.unit import factories as f


class TestProbabilityEstimate:
    def test_valid(self) -> None:
        estimate = ProbabilityEstimate(**f.probability_estimate_kwargs())
        assert estimate.probability_ppm == 650_000
        assert estimate.is_predictive is False

    @pytest.mark.parametrize("value", [0, 1_000_000])
    def test_probability_boundary_values_accepted(self, value: int) -> None:
        estimate = ProbabilityEstimate(
            **f.probability_estimate_kwargs(probability_ppm=value)
        )
        assert estimate.probability_ppm == value

    @pytest.mark.parametrize("value", [-1, 1_000_001])
    def test_probability_out_of_range_rejected(self, value: int) -> None:
        with pytest.raises(ValidationError):
            ProbabilityEstimate(**f.probability_estimate_kwargs(probability_ppm=value))

    @pytest.mark.parametrize("value", [650_000.0, True, "650000"])
    def test_non_int_probability_rejected(self, value: object) -> None:
        with pytest.raises(ValidationError):
            ProbabilityEstimate(**f.probability_estimate_kwargs(probability_ppm=value))

    @pytest.mark.parametrize("value", [True, 1, "false", None])
    def test_is_predictive_must_be_false(self, value: object) -> None:
        with pytest.raises(ValidationError):
            ProbabilityEstimate(**f.probability_estimate_kwargs(is_predictive=value))

    @pytest.mark.parametrize(
        "label",
        ["DEMO ESTIMATOR - NOT PREDICTIVE", "demo estimator — not predictive", ""],
    )
    def test_display_label_literal_enforced(self, label: str) -> None:
        with pytest.raises(ValidationError):
            ProbabilityEstimate(**f.probability_estimate_kwargs(display_label=label))

    def test_naive_computed_at_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ProbabilityEstimate(
                **f.probability_estimate_kwargs(computed_at=datetime(2026, 8, 5, 12, 0))
            )

    def test_malformed_digest_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ProbabilityEstimate(**f.probability_estimate_kwargs(inputs_digest="abc"))

    @pytest.mark.parametrize(
        "field",
        [
            "schema_version",
            "market_id",
            "side",
            "probability_ppm",
            "estimator_id",
            "estimator_version",
            "is_predictive",
            "display_label",
            "basis",
            "inputs_digest",
            "computed_at",
        ],
    )
    def test_required_fields(self, field: str) -> None:
        kwargs = f.probability_estimate_kwargs()
        del kwargs[field]
        with pytest.raises(ValidationError):
            ProbabilityEstimate(**kwargs)

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ProbabilityEstimate(**f.probability_estimate_kwargs(model_notes="x"))


def _tampered_basis(**over: Any) -> EstimatorBasis:
    kwargs: dict[str, Any] = {
        "match_id": f.MATCH_ID,
        "yes_team_rating": f.YES_TEAM_RATING,
        "yes_team_form": f.YES_TEAM_FORM,
        "no_team_rating": f.NO_TEAM_RATING,
        "no_team_form": f.NO_TEAM_FORM,
    }
    kwargs.update(over)
    return EstimatorBasis(**kwargs)


class TestInputsDigestValidation:
    def test_forged_well_formed_digest_rejected(self) -> None:
        with pytest.raises(ValidationError, match="inputs_digest does not match"):
            ProbabilityEstimate(
                **f.probability_estimate_kwargs(inputs_digest=f.sha_hex("forged"))
            )

    @pytest.mark.parametrize(
        "override",
        [
            {"estimator_id": "demo2"},
            {"estimator_version": "1.0.1"},
            {"market_id": "mkt-2"},
            {"side": "no"},
        ],
        ids=["estimator-id", "estimator-version", "market-id", "side"],
    )
    def test_changed_scalar_digest_input_rejected(
        self, override: dict[str, str]
    ) -> None:
        with pytest.raises(ValidationError, match="inputs_digest does not match"):
            ProbabilityEstimate(**f.probability_estimate_kwargs(**override))

    @pytest.mark.parametrize(
        "basis_override",
        [
            {"match_id": "match-2"},
            {"yes_team_rating": 601},
            {"yes_team_form": 51},
            {"no_team_rating": 311},
            {"no_team_form": 41},
        ],
        ids=["match-id", "yes-rating", "yes-form", "no-rating", "no-form"],
    )
    def test_changed_basis_field_rejected(
        self, basis_override: dict[str, object]
    ) -> None:
        with pytest.raises(ValidationError, match="inputs_digest does not match"):
            ProbabilityEstimate(
                **f.probability_estimate_kwargs(basis=_tampered_basis(**basis_override))
            )

    def test_consistently_recomputed_digest_accepted(self) -> None:
        basis = _tampered_basis(yes_team_form=51)
        digest = estimate_inputs_digest(
            estimator_id="demo",
            estimator_version="1.0.0",
            market_id="mkt-2",
            side="no",
            basis=basis,
        )
        estimate = ProbabilityEstimate(
            **f.probability_estimate_kwargs(
                market_id="mkt-2", side="no", basis=basis, inputs_digest=digest
            )
        )
        assert estimate.inputs_digest == digest

    def test_probability_not_bound_by_digest(self) -> None:
        # The schema validates the digest, never the estimator's formula:
        # a different probability with the same recorded inputs still passes.
        estimate = ProbabilityEstimate(
            **f.probability_estimate_kwargs(probability_ppm=123_456)
        )
        assert estimate.probability_ppm == 123_456


class TestEstimatorRejectionFieldSet:
    @pytest.mark.parametrize(
        "field", ["yes_team_rating", "yes_team_form", "no_team_rating", "no_team_form"]
    )
    def test_each_estimator_field_accepted_as_missing(self, field: str) -> None:
        rejection = EstimatorRejection(
            market_id=f.MARKET_ID,
            side="yes",
            estimator_id="demo",
            estimator_version="1.0.0",
            missing_fields=(field,),
            conflicted_fields=(),
        )
        assert rejection.missing_fields == (field,)

    @pytest.mark.parametrize(
        "field", ["yes_team_rating", "yes_team_form", "no_team_rating", "no_team_form"]
    )
    def test_each_estimator_field_accepted_as_conflicted(self, field: str) -> None:
        rejection = EstimatorRejection(
            market_id=f.MARKET_ID,
            side="yes",
            estimator_id="demo",
            estimator_version="1.0.0",
            missing_fields=(),
            conflicted_fields=(field,),
        )
        assert rejection.conflicted_fields == (field,)

    @pytest.mark.parametrize("field", ["patch_label", "wallet_key", "match_id"])
    @pytest.mark.parametrize("collection", ["missing_fields", "conflicted_fields"])
    def test_arbitrary_field_rejected(self, field: str, collection: str) -> None:
        kwargs: dict[str, object] = {
            "market_id": f.MARKET_ID,
            "side": "yes",
            "estimator_id": "demo",
            "estimator_version": "1.0.0",
            "missing_fields": (),
            "conflicted_fields": (),
            collection: (field,),
        }
        with pytest.raises(ValidationError, match="estimator-consumed fields only"):
            EstimatorRejection(**kwargs)  # type: ignore[arg-type]

    def test_duplicate_missing_path_rejected(self) -> None:
        with pytest.raises(ValidationError, match="duplicate"):
            EstimatorRejection(
                market_id=f.MARKET_ID,
                side="yes",
                estimator_id="demo",
                estimator_version="1.0.0",
                missing_fields=("yes_team_rating", "yes_team_rating"),
                conflicted_fields=(),
            )

    def test_duplicate_conflicted_path_rejected(self) -> None:
        with pytest.raises(ValidationError, match="duplicate"):
            EstimatorRejection(
                market_id=f.MARKET_ID,
                side="yes",
                estimator_id="demo",
                estimator_version="1.0.0",
                missing_fields=(),
                conflicted_fields=("no_team_form", "no_team_form"),
            )

    def test_overlap_between_collections_rejected(self) -> None:
        with pytest.raises(ValidationError, match="both missing and conflicted"):
            EstimatorRejection(
                market_id=f.MARKET_ID,
                side="yes",
                estimator_id="demo",
                estimator_version="1.0.0",
                missing_fields=("yes_team_rating",),
                conflicted_fields=("yes_team_rating",),
            )


class TestEstimatorRejection:
    def test_missing_only_valid(self) -> None:
        rejection = EstimatorRejection(
            market_id=f.MARKET_ID,
            side="yes",
            estimator_id="demo",
            estimator_version="1.0.0",
            missing_fields=("yes_team_rating",),
            conflicted_fields=(),
        )
        assert rejection.missing_fields == ("yes_team_rating",)

    def test_conflicted_only_valid(self) -> None:
        rejection = EstimatorRejection(
            market_id=f.MARKET_ID,
            side="yes",
            estimator_id="demo",
            estimator_version="1.0.0",
            missing_fields=(),
            conflicted_fields=("no_team_form",),
        )
        assert rejection.conflicted_fields == ("no_team_form",)

    def test_empty_rejection_rejected(self) -> None:
        with pytest.raises(ValidationError, match="at least one"):
            EstimatorRejection(
                market_id=f.MARKET_ID,
                side="yes",
                estimator_id="demo",
                estimator_version="1.0.0",
                missing_fields=(),
                conflicted_fields=(),
            )
