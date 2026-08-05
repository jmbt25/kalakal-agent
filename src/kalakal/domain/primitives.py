"""Shared strict domain primitives (architecture.md §6.1).

Every externally supplied contract inherits :class:`StrictModel`: unknown
fields forbidden, strict (non-coercing) validation, frozen instances. Money
and prices are integer micro-USD (``_micro``); probabilities and edges are
integer parts-per-million (``_ppm``). Timestamps are UTC-aware only.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Annotated, Final, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
)

SCHEMA_VERSION: Final = "1"

# RFC 2606 reserves ".invalid": these links can never resolve, so synthetic
# fixture links can never be mistaken for a postable jup.ag call.
SYNTHETIC_MARKET_LINK_PREFIX: Final = "https://markets.kalakal.invalid/"

DEMO_ESTIMATOR_DISPLAY_LABEL: Final = "DEMO ESTIMATOR — NOT PREDICTIVE"
SIMULATION_DRAFT_LABEL: Final = "SIMULATION — DO NOT POST"

MICRO_PER_UNIT: Final = 1_000_000
PPM_PER_UNIT: Final = 1_000_000


class StrictModel(BaseModel):
    """Base for every domain contract: strict, frozen, unknown-field-free."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("timestamp must be timezone-aware UTC")
    return value


def _require_bool(value: object) -> object:
    # Literal[True]/Literal[False] alone accept (and coerce) the equal ints 1/0.
    if not isinstance(value, bool):
        raise ValueError("must be a boolean")
    return value


def _require_int_not_bool(value: object) -> object:
    # Int literals alone accept the equal bools True/False.
    if isinstance(value, bool):
        raise ValueError("must be an integer, not a boolean")
    return value


def _require_synthetic_link(value: str) -> str:
    if not value.startswith(SYNTHETIC_MARKET_LINK_PREFIX):
        raise ValueError(
            "market link must use the synthetic non-resolvable domain "
            f"prefix {SYNTHETIC_MARKET_LINK_PREFIX!r}"
        )
    return value


UtcDatetime = Annotated[datetime, AfterValidator(_require_utc)]

StrictTrue = Annotated[Literal[True], BeforeValidator(_require_bool)]
StrictFalse = Annotated[Literal[False], BeforeValidator(_require_bool)]
# Bounded series length; best-of-two is common in Dota group stages.
BestOf = Annotated[int, Field(ge=1, le=7), BeforeValidator(_require_int_not_bool)]

Identifier = Annotated[
    str,
    StringConstraints(
        min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$"
    ),
]
VersionStr = Annotated[
    str,
    StringConstraints(
        min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.+-]*$"
    ),
]
FieldPath = Annotated[
    str,
    StringConstraints(min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$"),
]
ShortText = Annotated[str, StringConstraints(min_length=1, max_length=200)]
MediumText = Annotated[str, StringConstraints(min_length=1, max_length=500)]
LongText = Annotated[str, StringConstraints(min_length=1, max_length=2000)]
Sha256Hex = Annotated[
    str,
    StringConstraints(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"),
]
SyntheticMarketLink = Annotated[
    str,
    StringConstraints(min_length=1, max_length=300),
    AfterValidator(_require_synthetic_link),
]

ProbabilityPpm = Annotated[int, Field(ge=0, le=PPM_PER_UNIT)]
FeeRatePpm = Annotated[int, Field(ge=0, le=PPM_PER_UNIT)]
FeeMicro = Annotated[int, Field(ge=0, le=MICRO_PER_UNIT)]
AskPriceMicro = Annotated[int, Field(gt=0, lt=MICRO_PER_UNIT)]
BidPriceMicro = Annotated[int, Field(gt=0, lt=MICRO_PER_UNIT)]
LiquidityMicro = Annotated[int, Field(ge=0, le=1_000_000_000_000)]
GrossEdgePpm = Annotated[int, Field(gt=-PPM_PER_UNIT, lt=PPM_PER_UNIT)]
NetEdgePpm = Annotated[int, Field(gt=-2 * PPM_PER_UNIT, lt=PPM_PER_UNIT)]
SyntheticRating = Annotated[int, Field(ge=1, le=10_000)]
SyntheticForm = Annotated[int, Field(ge=0, le=100)]
LatencyMs = Annotated[int, Field(ge=0, le=600_000)]
TokenCount = Annotated[int, Field(ge=0, le=10_000_000)]

MarketSide = Literal["yes", "no"]
MarketStatus = Literal["open", "closed"]
RunMode = Literal["fixture"]
PolicyOutcome = Literal["proceed", "no_bet"]
ExplanationSource = Literal["agent", "orchestrator"]
InvocationStatus = Literal["invoked", "not_invoked"]
AbstentionSource = Literal["agent", "orchestrator"]
TerminalOutcome = Literal["completed", "abstained"]
ConfidenceQualifier = Literal["low", "medium", "high"]
FactorDirection = Literal["supports", "opposes", "neutral"]

AbstainReasonCode = Literal[
    "CONFLICTING_EVIDENCE",
    "INSUFFICIENT_EVIDENCE",
    "NO_ATTRACTIVE_CANDIDATE",
    "NO_VALID_CANDIDATES",
]
ORCHESTRATOR_ONLY_ABSTAIN_REASON: Final = "NO_VALID_CANDIDATES"

PolicyReasonCode = Literal[
    "POLICY_STALE_DATA",
    "POLICY_OUTSIDE_ENTRY_BAND",
    "POLICY_INSUFFICIENT_NET_EDGE",
    "POLICY_INCOMPLETE_DATA",
    "POLICY_DUPLICATE_RUN",
]

FailureReasonCode = Literal[
    "SCENARIO_UNKNOWN",
    "FIXTURE_INVALID",
    "REQUEST_INVALID",
    "MODEL_UNAVAILABLE",
    "MODEL_OUTPUT_REJECTED",
    "RUN_DEADLINE_EXCEEDED",
    "POLICY_INVARIANT_BREACH",
    "TOOL_CALL_OUT_OF_BOUNDS",
    "PERSISTENCE_ERROR",
    "INTERNAL_ERROR",
]
FailureClassification = Literal["retryable", "permanent", "safety"]

RunState = Literal[
    "created",
    "validating",
    "selecting",
    "estimating",
    "comparing",
    "policy_checking",
    "explaining",
    "persisting",
    "completed",
    "abstained",
    "failed",
    "timed_out",
]
ActiveRunState = Literal[
    "created",
    "validating",
    "selecting",
    "estimating",
    "comparing",
    "policy_checking",
    "explaining",
    "persisting",
]

# Staleness is a post-selection policy concern (§5.6, §7.7), never a
# pre-agent ineligibility reason — hence no STALE entry here.
EligibilityReason = Literal[
    "NOT_OPEN",
    "ESTIMATOR_INPUT_MISSING",
    "ESTIMATOR_INPUT_CONFLICTED",
]

AgentToolName = Literal[
    "list_candidate_markets",
    "get_match_context",
    "get_market_snapshot",
    "get_edge_assessment",
    "get_policy_decision",
]

EvidenceRefKind = Literal["market", "match", "snapshot", "fixture_source"]


class EvidenceRef(StrictModel):
    """Typed reference that must resolve to a validated entity or source."""

    kind: EvidenceRefKind
    ref_id: Identifier


class FixtureProvenance(StrictModel):
    """Fixture provenance carried by every fixture-derived contract (§6.1)."""

    fixture_set_id: Identifier
    fixture_set_version: VersionStr
    content_digest: Sha256Hex
    is_synthetic: StrictTrue


def canonical_digest(payload: Mapping[str, str | int]) -> str:
    """SHA-256 hex digest of a canonical JSON encoding of ``payload``.

    Canonical form: sorted keys, compact separators, UTF-8. Values are
    restricted to strings and integers so the encoding is bit-stable.
    """
    for key, value in payload.items():
        if isinstance(value, bool) or not isinstance(value, str | int):
            raise ValueError(
                f"digest payload value for {key!r} must be str or int, "
                f"got {type(value).__name__}"
            )
    encoded = json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
