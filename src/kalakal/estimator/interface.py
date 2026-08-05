"""Typed probability-estimator interface (architecture.md §10).

Implementations are pure functions of validated inputs: no wall clock, no
randomness, no LLM involvement, no invented values.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import ClassVar

from kalakal.domain.estimate import EstimatorRejection, ProbabilityEstimate
from kalakal.domain.match import MatchContext
from kalakal.domain.primitives import MarketSide

EstimationResult = ProbabilityEstimate | EstimatorRejection


class ProbabilityEstimator(ABC):
    """Interface every estimator binding must implement."""

    estimator_id: ClassVar[str]
    estimator_version: ClassVar[str]

    @abstractmethod
    def estimate(
        self,
        match: MatchContext,
        side: MarketSide,
        *,
        computed_at: datetime,
    ) -> EstimationResult:
        """Estimate the probability for ``side`` of the match's market.

        ``computed_at`` is supplied by the caller; implementations never read
        the wall clock. Missing or conflicted estimator-consumed inputs yield
        a typed :class:`EstimatorRejection`, never substituted defaults.
        """
