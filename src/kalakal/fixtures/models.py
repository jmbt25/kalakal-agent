"""Repository-level fixture models (architecture.md §4.2, §8.1).

These wrap the unchanged Slice 2 domain contracts with the minimum scenario
and manifest metadata the fixture repository needs. Everything is strict and
frozen; scenario semantics (which downstream outcome a scenario produces)
are recorded as bounded typed metadata, never inferred from prose.
"""

from __future__ import annotations

from typing import Annotated, Final, Literal, get_args

from pydantic import Field, StringConstraints, model_validator

from kalakal.domain.market import CandidateMarket, MarketSnapshot
from kalakal.domain.match import MatchContext
from kalakal.domain.primitives import (
    AbstainReasonCode,
    FeeRatePpm,
    FixtureProvenance,
    Identifier,
    MarketSide,
    MediumText,
    PolicyReasonCode,
    Sha256Hex,
    StrictModel,
    UtcDatetime,
    VersionStr,
)
from kalakal.domain.quality import DataQuality

# Where each expected downstream outcome is decided (§5.6, §6.2.10, §7.1).
ExpectedOutcomeClass = Literal[
    "completed_proceed",
    "policy_no_bet",
    "agent_abstention",
    "orchestrator_abstention",
]
ExpectedReasonCode = PolicyReasonCode | AbstainReasonCode

_POLICY_REASON_CODES: Final = frozenset(get_args(PolicyReasonCode))
_ABSTAIN_REASON_CODES: Final = frozenset(get_args(AbstainReasonCode))

ScenarioId = Annotated[
    str,
    StringConstraints(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9-]*$"),
]
# No path separators, no dots except the mandatory .json suffix: traversal
# and absolute paths are unrepresentable, not merely checked.
FixtureFilename = Annotated[
    str,
    StringConstraints(
        min_length=6, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*\.json$"
    ),
]


class ManifestEntry(StrictModel):
    """Manifest mapping target: one scenario file and its raw-byte digest."""

    filename: FixtureFilename
    sha256: Sha256Hex


class FixtureManifest(StrictModel):
    """The fixture set's manifest: identity, version, and file mapping."""

    schema_version: Literal["1"]
    fixture_set_id: Identifier
    fixture_set_version: VersionStr
    scenarios: dict[ScenarioId, ManifestEntry]

    @model_validator(mode="after")
    def _check_invariants(self) -> FixtureManifest:
        if not self.scenarios:
            raise ValueError("manifest must map at least one scenario")
        if len(self.scenarios) > 64:
            raise ValueError("manifest must map at most 64 scenarios")
        filenames = [entry.filename for entry in self.scenarios.values()]
        if len(set(filenames)) != len(filenames):
            raise ValueError("manifest filenames must be unique")
        return self


class ScenarioCandidateBundle(StrictModel):
    """One candidate market with its match context and evaluated-side snapshot.

    ``evaluation_side`` is the explicit side this candidate is evaluated on;
    it must match the snapshot and is never inferred from prose.
    """

    evaluation_side: MarketSide
    candidate_market: CandidateMarket
    match_context: MatchContext
    market_snapshot: MarketSnapshot

    @model_validator(mode="after")
    def _check_cross_entity(self) -> ScenarioCandidateBundle:
        market_id = self.candidate_market.market_id
        if self.match_context.market_id != market_id:
            raise ValueError(
                "match_context.market_id must reference the bundle's market"
            )
        if self.market_snapshot.market_id != market_id:
            raise ValueError(
                "market_snapshot.market_id must reference the bundle's market"
            )
        if self.market_snapshot.side != self.evaluation_side:
            raise ValueError(
                "market_snapshot.side must equal the bundle's evaluation_side"
            )
        return self


class FixtureScenario(StrictModel):
    """One versioned synthetic scenario document."""

    schema_version: Literal["1"]
    scenario_id: ScenarioId
    description: MediumText
    evaluation_time: UtcDatetime
    expected_outcome_class: ExpectedOutcomeClass
    expected_reason_code: ExpectedReasonCode | None = None
    fee_rate_ppm: FeeRatePpm
    fee_model_version: VersionStr
    candidates: Annotated[
        tuple[ScenarioCandidateBundle, ...], Field(min_length=1, max_length=8)
    ]
    provenance: FixtureProvenance

    @model_validator(mode="after")
    def _check_invariants(self) -> FixtureScenario:
        self._check_expected_reason()
        market_ids = [b.candidate_market.market_id for b in self.candidates]
        if len(set(market_ids)) != len(market_ids):
            raise ValueError("candidate market IDs must be unique within a scenario")
        match_ids = [b.match_context.match_id for b in self.candidates]
        if len(set(match_ids)) != len(match_ids):
            raise ValueError("match IDs must be unique within a scenario")
        for bundle in self.candidates:
            if bundle.market_snapshot.fee_model_version != self.fee_model_version:
                raise ValueError(
                    "every snapshot's fee_model_version must equal the "
                    "scenario's fee_model_version"
                )
            for entity_name, entity_provenance in (
                ("candidate_market", bundle.candidate_market.provenance),
                ("match_context", bundle.match_context.provenance),
                ("market_snapshot", bundle.market_snapshot.provenance),
            ):
                if (
                    entity_provenance.fixture_set_id != self.provenance.fixture_set_id
                    or entity_provenance.fixture_set_version
                    != self.provenance.fixture_set_version
                ):
                    raise ValueError(
                        f"{entity_name} provenance must match the scenario's "
                        "fixture-set ID and version"
                    )
        self._check_conflict_refs_resolve(frozenset(market_ids), frozenset(match_ids))
        return self

    def _check_expected_reason(self) -> None:
        code = self.expected_reason_code
        outcome = self.expected_outcome_class
        if outcome == "completed_proceed":
            if code is not None:
                raise ValueError("completed_proceed must not carry a reason code")
        elif outcome == "policy_no_bet":
            if code not in _POLICY_REASON_CODES:
                raise ValueError("policy_no_bet requires a policy reason code")
        elif outcome == "agent_abstention":
            if code not in _ABSTAIN_REASON_CODES or code == "NO_VALID_CANDIDATES":
                raise ValueError(
                    "agent_abstention requires an agent abstain reason code"
                )
        elif code != "NO_VALID_CANDIDATES":
            raise ValueError(
                "orchestrator_abstention requires reason NO_VALID_CANDIDATES"
            )

    def _check_conflict_refs_resolve(
        self, market_ids: frozenset[str], match_ids: frozenset[str]
    ) -> None:
        # §6.2.12: every conflict evidence_ref must resolve to a validated
        # fixture entity of this scenario or to the fixture source itself.
        for bundle in self.candidates:
            for quality in (
                bundle.candidate_market.data_quality,
                bundle.match_context.data_quality,
                bundle.market_snapshot.data_quality,
            ):
                self._check_quality_refs(quality, market_ids, match_ids)

    def _check_quality_refs(
        self,
        quality: DataQuality,
        market_ids: frozenset[str],
        match_ids: frozenset[str],
    ) -> None:
        for conflict in quality.conflicts:
            for ref in conflict.evidence_refs:
                if ref.kind == "match":
                    resolvable = ref.ref_id in match_ids
                elif ref.kind == "fixture_source":
                    resolvable = ref.ref_id == self.provenance.fixture_set_id
                else:  # "market" and "snapshot" both resolve by market ID.
                    resolvable = ref.ref_id in market_ids
                if not resolvable:
                    raise ValueError(
                        f"conflict evidence ref ({ref.kind}, {ref.ref_id!r}) "
                        "does not resolve within the scenario"
                    )
