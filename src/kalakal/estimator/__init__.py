"""Probability-estimator interface and the deterministic demo binding."""

from kalakal.estimator.demo import (
    DEMO_ESTIMATOR_ID,
    DEMO_ESTIMATOR_VERSION,
    DemoEstimator,
)
from kalakal.estimator.interface import EstimationResult, ProbabilityEstimator

__all__ = [
    "DEMO_ESTIMATOR_ID",
    "DEMO_ESTIMATOR_VERSION",
    "DemoEstimator",
    "EstimationResult",
    "ProbabilityEstimator",
]
