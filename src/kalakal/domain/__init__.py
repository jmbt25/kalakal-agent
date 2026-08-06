"""Typed fixture-MVP domain contracts (architecture.md §6)."""

from kalakal.domain.draft import SimulatedDiscordDraft
from kalakal.domain.edge import EdgeAssessment, edge_inputs_digest
from kalakal.domain.eligibility import derive_ineligibility_reasons
from kalakal.domain.estimate import (
    EstimatorBasis,
    EstimatorRejection,
    ProbabilityEstimate,
    estimate_inputs_digest,
)
from kalakal.domain.explanation import DecisionExplanation, KeyFactor
from kalakal.domain.failure import FailedModelAttempt, RunFailure
from kalakal.domain.invocation import (
    Abstention,
    DeterministicSelectorMetadata,
    MarketSelection,
    ModelCallUsage,
    ModelInvocationInvoked,
    ModelInvocationMetadata,
    ModelInvocationNotInvoked,
    ToolCallRecord,
)
from kalakal.domain.market import (
    CANDIDATE_MARKET_MISSING_ALLOWLIST,
    MARKET_SNAPSHOT_MISSING_ALLOWLIST,
    CandidateMarket,
    MarketSnapshot,
)
from kalakal.domain.match import MATCH_ESTIMATOR_FIELDS, MatchContext, RosterEntry
from kalakal.domain.policy import PolicyCheck, PolicyDecision
from kalakal.domain.primitives import (
    DEMO_ESTIMATOR_DISPLAY_LABEL,
    SCHEMA_VERSION,
    SIMULATION_DRAFT_LABEL,
    SYNTHETIC_MARKET_LINK_PREFIX,
    EvidenceRef,
    FixtureProvenance,
    MarketSide,
    StrictModel,
    canonical_digest,
)
from kalakal.domain.quality import DataConflict, DataQuality
from kalakal.domain.record import (
    CandidateEligibility,
    CompletedProceedRecord,
    DecisionRecord,
    PolicyNoBetRecord,
    PreSelectionAbstentionRecord,
    StateTransition,
    validate_decision_record,
)
from kalakal.domain.run import RunRequest
from kalakal.domain.sensitive import find_sensitive_content

__all__ = [
    "CANDIDATE_MARKET_MISSING_ALLOWLIST",
    "DEMO_ESTIMATOR_DISPLAY_LABEL",
    "MARKET_SNAPSHOT_MISSING_ALLOWLIST",
    "MATCH_ESTIMATOR_FIELDS",
    "SCHEMA_VERSION",
    "SIMULATION_DRAFT_LABEL",
    "SYNTHETIC_MARKET_LINK_PREFIX",
    "Abstention",
    "CandidateEligibility",
    "CandidateMarket",
    "CompletedProceedRecord",
    "DataConflict",
    "DataQuality",
    "DecisionExplanation",
    "DecisionRecord",
    "DeterministicSelectorMetadata",
    "EdgeAssessment",
    "EstimatorBasis",
    "EstimatorRejection",
    "EvidenceRef",
    "FailedModelAttempt",
    "FixtureProvenance",
    "KeyFactor",
    "MarketSelection",
    "MarketSide",
    "MarketSnapshot",
    "MatchContext",
    "ModelCallUsage",
    "ModelInvocationInvoked",
    "ModelInvocationMetadata",
    "ModelInvocationNotInvoked",
    "PolicyCheck",
    "PolicyDecision",
    "PolicyNoBetRecord",
    "PreSelectionAbstentionRecord",
    "ProbabilityEstimate",
    "RosterEntry",
    "RunFailure",
    "RunRequest",
    "SimulatedDiscordDraft",
    "StateTransition",
    "StrictModel",
    "ToolCallRecord",
    "canonical_digest",
    "derive_ineligibility_reasons",
    "edge_inputs_digest",
    "estimate_inputs_digest",
    "find_sensitive_content",
    "validate_decision_record",
]
