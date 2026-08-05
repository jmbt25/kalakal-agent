"""ProbabilityEstimate contract and estimator result types (architecture.md §6.2.5)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from kalakal.domain.match import MATCH_ESTIMATOR_FIELDS
from kalakal.domain.primitives import (
    FieldPath,
    Identifier,
    MarketSide,
    ProbabilityPpm,
    Sha256Hex,
    StrictFalse,
    StrictModel,
    SyntheticForm,
    SyntheticRating,
    UtcDatetime,
    VersionStr,
    canonical_digest,
)


class EstimatorBasis(StrictModel):
    """The exact deterministic inputs an estimate was computed from.

    Fields are named for the market side they belong to; the side mapping is
    structural, never positional or inferred from free text.
    """

    match_id: Identifier
    yes_team_rating: SyntheticRating
    yes_team_form: SyntheticForm
    no_team_rating: SyntheticRating
    no_team_form: SyntheticForm


def estimate_inputs_digest(
    *,
    estimator_id: str,
    estimator_version: str,
    market_id: str,
    side: str,
    basis: EstimatorBasis,
) -> str:
    """Canonical, stable digest of the exact estimator inputs."""
    return canonical_digest(
        {
            "estimator_id": estimator_id,
            "estimator_version": estimator_version,
            "market_id": market_id,
            "side": side,
            "match_id": basis.match_id,
            "yes_team_rating": basis.yes_team_rating,
            "yes_team_form": basis.yes_team_form,
            "no_team_rating": basis.no_team_rating,
            "no_team_form": basis.no_team_form,
        }
    )


class ProbabilityEstimate(StrictModel):
    """A deterministic, reproducible probability estimate.

    MVP invariants (§6.2.5, §10.1): ``is_predictive`` is false and the
    display label is exactly the non-predictive demo label. The validator
    recomputes ``inputs_digest`` from the recorded inputs and rejects any
    mismatch; it stays estimator-formula-agnostic — the probability itself is
    the producing estimator's responsibility, enforced by estimator tests.
    """

    schema_version: Literal["1"]
    market_id: Identifier
    side: MarketSide
    probability_ppm: ProbabilityPpm
    estimator_id: Identifier
    estimator_version: VersionStr
    is_predictive: StrictFalse
    display_label: Literal["DEMO ESTIMATOR — NOT PREDICTIVE"]
    basis: EstimatorBasis
    inputs_digest: Sha256Hex
    computed_at: UtcDatetime

    @model_validator(mode="after")
    def _check_digest(self) -> ProbabilityEstimate:
        expected = estimate_inputs_digest(
            estimator_id=self.estimator_id,
            estimator_version=self.estimator_version,
            market_id=self.market_id,
            side=self.side,
            basis=self.basis,
        )
        if self.inputs_digest != expected:
            raise ValueError(
                "inputs_digest does not match the recorded estimator inputs"
            )
        return self


class EstimatorRejection(StrictModel):
    """Typed refusal to estimate: estimator-consumed input missing/conflicted.

    Only the closed set of estimator-consumed MatchContext fields may appear,
    each at most once and in at most one of the two collections.
    """

    market_id: Identifier
    side: MarketSide
    estimator_id: Identifier
    estimator_version: VersionStr
    missing_fields: Annotated[tuple[FieldPath, ...], Field(max_length=4)]
    conflicted_fields: Annotated[tuple[FieldPath, ...], Field(max_length=4)]

    @model_validator(mode="after")
    def _check_fields(self) -> EstimatorRejection:
        allowed = frozenset(MATCH_ESTIMATOR_FIELDS)
        for label, paths in (
            ("missing_fields", self.missing_fields),
            ("conflicted_fields", self.conflicted_fields),
        ):
            unknown = sorted(set(paths) - allowed)
            if unknown:
                raise ValueError(
                    f"{label} must name estimator-consumed fields only; "
                    f"unknown: {unknown}"
                )
            if len(set(paths)) != len(paths):
                raise ValueError(f"{label} must not contain duplicate paths")
        overlap = sorted(set(self.missing_fields) & set(self.conflicted_fields))
        if overlap:
            raise ValueError(
                f"a field cannot be both missing and conflicted: {overlap}"
            )
        if not self.missing_fields and not self.conflicted_fields:
            raise ValueError(
                "a rejection requires at least one missing or conflicted field"
            )
        return self
