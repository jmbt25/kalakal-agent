"""Deterministic demo estimator (architecture.md §10.1).

THIS IS NOT A PREDICTION MODEL. Its only purpose is exercising orchestration
over recorded synthetic integer inputs. It is versioned, labeled
``DEMO ESTIMATOR — NOT PREDICTIVE``, and must never be presented as if it
forecasts real matches.

Exact demo formula (versioned as demo/1.0.0), integer arithmetic only::

    score_yes = yes_team_rating + yes_team_form
    score_no  = no_team_rating + no_team_form
    p_yes_ppm = (score_yes * 1_000_000) // (score_yes + score_no)
    probability_ppm = p_yes_ppm               if side == "yes"
                      1_000_000 - p_yes_ppm   if side == "no"

The market-side mapping is structural: the MatchContext schema names each
estimator input for the side it belongs to (``yes_team_*`` / ``no_team_*``),
so the sides cannot be inverted positionally and team identity is never
inferred from free text. Ratings are bounded to [1, 10_000] and form to
[0, 100] by the MatchContext schema, so the denominator is provably positive
and the output provably within 0–1_000_000.
"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar, Final

from kalakal.domain.estimate import (
    EstimatorBasis,
    EstimatorRejection,
    ProbabilityEstimate,
    estimate_inputs_digest,
)
from kalakal.domain.match import MATCH_ESTIMATOR_FIELDS, MatchContext
from kalakal.domain.primitives import (
    DEMO_ESTIMATOR_DISPLAY_LABEL,
    PPM_PER_UNIT,
    SCHEMA_VERSION,
    MarketSide,
)
from kalakal.estimator.interface import EstimationResult, ProbabilityEstimator

DEMO_ESTIMATOR_ID: Final = "demo"
DEMO_ESTIMATOR_VERSION: Final = "1.0.0"


class DemoEstimator(ProbabilityEstimator):
    """The fixture-MVP binding: deterministic, non-predictive, side-effect free."""

    estimator_id: ClassVar[str] = DEMO_ESTIMATOR_ID
    estimator_version: ClassVar[str] = DEMO_ESTIMATOR_VERSION

    def estimate(
        self,
        match: MatchContext,
        side: MarketSide,
        *,
        computed_at: datetime,
    ) -> EstimationResult:
        missing = tuple(
            name
            for name in MATCH_ESTIMATOR_FIELDS
            if getattr(match, name) is None or name in match.data_quality.missing_fields
        )
        # A field reported missing is not repeated as conflicted: each field
        # appears in exactly one rejection collection.
        conflicted = tuple(
            name
            for name in MATCH_ESTIMATOR_FIELDS
            if name not in missing
            and any(
                conflict.field_path == name for conflict in match.data_quality.conflicts
            )
        )
        if missing or conflicted:
            return EstimatorRejection(
                market_id=match.market_id,
                side=side,
                estimator_id=self.estimator_id,
                estimator_version=self.estimator_version,
                missing_fields=missing,
                conflicted_fields=conflicted,
            )
        assert match.yes_team_rating is not None
        assert match.yes_team_form is not None
        assert match.no_team_rating is not None
        assert match.no_team_form is not None
        basis = EstimatorBasis(
            match_id=match.match_id,
            yes_team_rating=match.yes_team_rating,
            yes_team_form=match.yes_team_form,
            no_team_rating=match.no_team_rating,
            no_team_form=match.no_team_form,
        )
        score_yes = basis.yes_team_rating + basis.yes_team_form
        score_no = basis.no_team_rating + basis.no_team_form
        p_yes_ppm = (score_yes * PPM_PER_UNIT) // (score_yes + score_no)
        probability_ppm = p_yes_ppm if side == "yes" else PPM_PER_UNIT - p_yes_ppm
        return ProbabilityEstimate(
            schema_version=SCHEMA_VERSION,
            market_id=match.market_id,
            side=side,
            probability_ppm=probability_ppm,
            estimator_id=self.estimator_id,
            estimator_version=self.estimator_version,
            is_predictive=False,
            display_label=DEMO_ESTIMATOR_DISPLAY_LABEL,
            basis=basis,
            inputs_digest=estimate_inputs_digest(
                estimator_id=self.estimator_id,
                estimator_version=self.estimator_version,
                market_id=match.market_id,
                side=side,
                basis=basis,
            ),
            computed_at=computed_at,
        )
