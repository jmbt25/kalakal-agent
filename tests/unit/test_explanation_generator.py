"""Slice 5 tests: deterministic source-aware explanation generation.

Covers the three orchestrator no-model paths (§5.6, §5.10, §6.2.8), the
validated agent qualitative-content assembly (§5.2), the narrative-only
rule, and the shared evidence-scope validation.
"""

from __future__ import annotations

import inspect
from datetime import datetime
from typing import Any

import pytest
from pydantic import ValidationError

from kalakal.domain import (
    CandidateEligibility,
    DataQuality,
    DecisionExplanation,
    EdgeAssessment,
    EvidenceRef,
    KeyFactor,
    PolicyDecision,
    derive_ineligibility_reasons,
)
from kalakal.domain.primitives import SYNTHETIC_MARKET_LINK_PREFIX, EvidenceRefKind
from kalakal.explain import (
    EXPLANATION_TEMPLATE_VERSION,
    AgentQualitativeContent,
    EvidenceCatalog,
    ExplanationGenerationError,
    assemble_agent_explanation,
    build_evidence_catalog,
    find_numeric_narrative,
    find_unresolved_evidence_refs,
    generate_no_valid_candidates_explanation,
    generate_stub_abstention_explanation,
    generate_stub_post_selection_explanation,
)
from kalakal.fixtures import FixtureRepository
from kalakal.policy import FIXTURE_POLICY_CONFIG, PolicyConfig, evaluate_policy
from tests.unit import factories as f
from tests.unit.fixture_helpers import consideration_from_bundle, shipped_version_dir

RUN_ID = "run-explain-1"

GENERATORS = (
    generate_no_valid_candidates_explanation,
    generate_stub_abstention_explanation,
    generate_stub_post_selection_explanation,
)


@pytest.fixture(scope="module")
def repo() -> FixtureRepository:
    return FixtureRepository(shipped_version_dir())


def make_bundle(
    market_id: str,
    match_id: str,
    *,
    status: str = "open",
    match_over: dict[str, Any] | None = None,
    snapshot_over: dict[str, Any] | None = None,
) -> CandidateEligibility:
    """One considered bundle with its derived eligibility result."""
    market = f.make_candidate_market(
        market_id=market_id,
        market_link=SYNTHETIC_MARKET_LINK_PREFIX + market_id,
        status=status,
    )
    match_kwargs: dict[str, Any] = {"match_id": match_id, "market_id": market_id}
    match_kwargs.update(match_over or {})
    match = f.make_match_context(**match_kwargs)
    snapshot_kwargs: dict[str, Any] = {"market_id": market_id}
    snapshot_kwargs.update(snapshot_over or {})
    snapshot = f.make_market_snapshot(**snapshot_kwargs)
    reasons = derive_ineligibility_reasons(market, match)
    return CandidateEligibility(
        market=market,
        match_context=match,
        market_snapshot=snapshot,
        evaluation_side="yes",
        eligible=not reasons,
        ineligibility_reasons=reasons,
    )


def closed_bundle(
    market_id: str = "mkt-closed", match_id: str = "match-closed"
) -> CandidateEligibility:
    return make_bundle(market_id, match_id, status="closed")


def missing_estimator_bundle(
    market_id: str = "mkt-missing", match_id: str = "match-missing"
) -> CandidateEligibility:
    return make_bundle(
        market_id,
        match_id,
        match_over={
            "yes_team_rating": None,
            "data_quality": DataQuality(
                is_complete=False,
                missing_fields=("yes_team_rating",),
                conflicts=(),
            ),
        },
    )


def conflicted_estimator_bundle(
    market_id: str = "mkt-conflicted", match_id: str = "match-conflicted"
) -> CandidateEligibility:
    return make_bundle(
        market_id,
        match_id,
        match_over={
            "data_quality": DataQuality(
                is_complete=False,
                missing_fields=(),
                conflicts=(f.make_conflict("no_team_form"),),
            ),
        },
    )


def match_conflict_bundle(
    market_id: str = "mkt-patch", match_id: str = "match-patch"
) -> CandidateEligibility:
    """Eligible: the declared conflict touches non-estimator match evidence."""
    return make_bundle(
        market_id,
        match_id,
        match_over={
            "data_quality": DataQuality(
                is_complete=False,
                missing_fields=(),
                conflicts=(f.make_conflict("patch_label"),),
            ),
        },
    )


def snapshot_gap_bundle(
    market_id: str = "mkt-gap", match_id: str = "match-gap"
) -> CandidateEligibility:
    """Eligible: the declared gap is a non-estimator snapshot field."""
    return make_bundle(
        market_id,
        match_id,
        snapshot_over={
            "bid_price_micro": None,
            "data_quality": DataQuality(
                is_complete=False,
                missing_fields=("bid_price_micro",),
                conflicts=(),
            ),
        },
    )


def all_narrative_texts(explanation: DecisionExplanation) -> tuple[str, ...]:
    return (
        explanation.summary,
        *(factor.factor for factor in explanation.key_factors),
        *explanation.conflicts,
        *explanation.data_gaps,
    )


def assert_orchestrator_shape(explanation: DecisionExplanation) -> None:
    assert explanation.run_id == RUN_ID
    assert explanation.source == "orchestrator"
    assert explanation.explanation_template_version == EXPLANATION_TEMPLATE_VERSION
    assert explanation.prompt_version is None
    assert explanation.model_metadata_ref is None
    assert explanation.confidence_qualifier == "low"
    for text in all_narrative_texts(explanation):
        assert find_numeric_narrative(text) is None


def factor_refs(explanation: DecisionExplanation) -> tuple[EvidenceRef, ...]:
    return tuple(factor.evidence_ref for factor in explanation.key_factors)


class TestNumericNarrativeValidator:
    @pytest.mark.parametrize(
        "text",
        [
            "contains 3 digits",
            "about 50% likely",
            "$ price mentioned",
            "60¢ ask",
            "€ symbol",
            "£ symbol",
            "¥ symbol",
            "edge in ppm units",
            "PPM shouting",
            "micro-USD amounts",
            "micro usd amounts",
            "net_edge_ppm field talk",
            "ask_price_micro field talk",
        ],
    )
    def test_numeric_or_currency_prose_flagged(self, text: str) -> None:
        assert find_numeric_narrative(text) is not None

    @pytest.mark.parametrize(
        "text",
        [
            "Qualitative wording without numbers.",
            "The recorded ask price sits above the configured entry band.",
            "A microphone is not a unit.",
        ],
    )
    def test_clean_qualitative_prose_passes(self, text: str) -> None:
        assert find_numeric_narrative(text) is None


class TestEvidenceCatalog:
    def test_catalog_pools_built_from_considered_bundles(self) -> None:
        catalog = build_evidence_catalog(
            (f.make_consideration(),), fixture_source_id=f.FIXTURE_SET_ID
        )
        assert catalog.market_ids == frozenset({f.MARKET_ID})
        assert catalog.match_ids == frozenset({f.MATCH_ID})
        assert catalog.snapshot_market_ids == frozenset({f.MARKET_ID})
        assert catalog.fixture_source_ids == frozenset({f.FIXTURE_SET_ID})

    @pytest.mark.parametrize("kind", ["market", "match", "snapshot", "fixture_source"])
    def test_unresolved_ref_of_each_kind_reported(self, kind: EvidenceRefKind) -> None:
        catalog = build_evidence_catalog(
            (f.make_consideration(),), fixture_source_id=f.FIXTURE_SET_ID
        )
        ref = EvidenceRef(kind=kind, ref_id="unknown-entity")
        assert find_unresolved_evidence_refs((ref,), catalog) == (ref,)

    def test_resolved_refs_report_nothing(self) -> None:
        catalog = build_evidence_catalog(
            (f.make_consideration(),), fixture_source_id=f.FIXTURE_SET_ID
        )
        refs = (
            EvidenceRef(kind="market", ref_id=f.MARKET_ID),
            EvidenceRef(kind="match", ref_id=f.MATCH_ID),
            EvidenceRef(kind="snapshot", ref_id=f.MARKET_ID),
            EvidenceRef(kind="fixture_source", ref_id=f.FIXTURE_SET_ID),
        )
        assert find_unresolved_evidence_refs(refs, catalog) == ()


class TestNoValidCandidates:
    def generate(
        self, considered: tuple[CandidateEligibility, ...]
    ) -> DecisionExplanation:
        return generate_no_valid_candidates_explanation(
            run_id=RUN_ID,
            considered=considered,
            fixture_source_id=f.FIXTURE_SET_ID,
        )

    def test_all_ineligible_produces_valid_orchestrator_explanation(self) -> None:
        explanation = self.generate(
            (missing_estimator_bundle(), conflicted_estimator_bundle())
        )
        assert_orchestrator_shape(explanation)
        assert len(explanation.key_factors) == 2

    def test_not_open_factor_references_the_candidate_market(self) -> None:
        explanation = self.generate((closed_bundle(),))
        assert factor_refs(explanation) == (
            EvidenceRef(kind="market", ref_id="mkt-closed"),
        )
        assert "not open" in explanation.key_factors[0].factor

    def test_missing_estimator_factor_references_the_match_context(self) -> None:
        explanation = self.generate((missing_estimator_bundle(),))
        assert factor_refs(explanation) == (
            EvidenceRef(kind="match", ref_id="match-missing"),
        )
        assert "missing" in explanation.key_factors[0].factor
        assert explanation.data_gaps != ()

    def test_conflicted_estimator_factor_references_the_match_context(self) -> None:
        explanation = self.generate((conflicted_estimator_bundle(),))
        assert factor_refs(explanation) == (
            EvidenceRef(kind="match", ref_id="match-conflicted"),
        )
        assert "conflict" in explanation.key_factors[0].factor
        assert explanation.conflicts != ()
        # The recorded conflict's own evidence refs are propagated.
        assert (
            EvidenceRef(kind="fixture_source", ref_id=f.FIXTURE_SET_ID)
            in explanation.evidence_refs
        )

    def test_factors_ordered_by_ascending_market_id(self) -> None:
        explanation = self.generate(
            (
                closed_bundle("mkt-c", "match-c"),
                missing_estimator_bundle("mkt-a", "match-a"),
                conflicted_estimator_bundle("mkt-b", "match-b"),
            )
        )
        assert factor_refs(explanation) == (
            EvidenceRef(kind="match", ref_id="match-a"),
            EvidenceRef(kind="match", ref_id="match-b"),
            EvidenceRef(kind="market", ref_id="mkt-c"),
        )

    def test_no_staleness_claim_appears(self) -> None:
        explanation = self.generate(
            (missing_estimator_bundle(), conflicted_estimator_bundle())
        )
        for text in all_narrative_texts(explanation):
            assert "stale" not in text.lower()

    def test_eligible_candidate_rejected(self) -> None:
        with pytest.raises(ExplanationGenerationError, match="zero eligible"):
            self.generate((f.make_consideration(),))

    def test_empty_considered_rejected(self) -> None:
        with pytest.raises(ExplanationGenerationError, match="at least one"):
            self.generate(())

    def test_unresolvable_fixture_source_ref_rejected(self) -> None:
        with pytest.raises(ExplanationGenerationError, match="unresolved evidence ref"):
            generate_no_valid_candidates_explanation(
                run_id=RUN_ID,
                considered=(conflicted_estimator_bundle(),),
                fixture_source_id="a-different-source",
            )

    def test_repeatable_and_inputs_unchanged(self) -> None:
        considered = (missing_estimator_bundle(), conflicted_estimator_bundle())
        before = [candidate.model_dump() for candidate in considered]
        first = self.generate(considered)
        second = self.generate(considered)
        assert first == second
        assert [candidate.model_dump() for candidate in considered] == before

    def test_shipped_no_valid_candidates_fixture(self, repo: FixtureRepository) -> None:
        scenario = repo.load_scenario("no-valid-candidates")
        considered = tuple(
            consideration_from_bundle(bundle) for bundle in scenario.candidates
        )
        explanation = generate_no_valid_candidates_explanation(
            run_id=RUN_ID,
            considered=considered,
            fixture_source_id=scenario.provenance.fixture_set_id,
        )
        assert_orchestrator_shape(explanation)
        assert factor_refs(explanation) == (
            EvidenceRef(kind="match", ref_id="syn-match-no-valid-candidates-01"),
            EvidenceRef(kind="match", ref_id="syn-match-no-valid-candidates-02"),
        )
        assert "missing" in explanation.key_factors[0].factor
        assert "conflict" in explanation.key_factors[1].factor
        catalog = build_evidence_catalog(
            considered, fixture_source_id=scenario.provenance.fixture_set_id
        )
        assert find_unresolved_evidence_refs(explanation.evidence_refs, catalog) == ()


class TestStubAbstention:
    def generate(
        self,
        considered: tuple[CandidateEligibility, ...],
        reason: str = "CONFLICTING_EVIDENCE",
    ) -> DecisionExplanation:
        return generate_stub_abstention_explanation(
            run_id=RUN_ID,
            considered=considered,
            abstain_reason_code=reason,  # type: ignore[arg-type]
            fixture_source_id=f.FIXTURE_SET_ID,
        )

    def test_conflicting_evidence_cites_the_conflicted_match(self) -> None:
        explanation = self.generate((match_conflict_bundle(),))
        assert_orchestrator_shape(explanation)
        assert factor_refs(explanation) == (
            EvidenceRef(kind="match", ref_id="match-patch"),
        )
        assert explanation.conflicts != ()
        assert explanation.data_gaps == ()
        assert (
            EvidenceRef(kind="fixture_source", ref_id=f.FIXTURE_SET_ID)
            in explanation.evidence_refs
        )

    def test_insufficient_evidence_cites_the_snapshot_gap(self) -> None:
        explanation = self.generate((snapshot_gap_bundle(),), "INSUFFICIENT_EVIDENCE")
        assert_orchestrator_shape(explanation)
        assert factor_refs(explanation) == (
            EvidenceRef(kind="snapshot", ref_id="mkt-gap"),
        )
        assert explanation.data_gaps != ()
        assert explanation.conflicts == ()

    def test_only_eligible_candidate_evidence_is_cited(self) -> None:
        explanation = self.generate(
            (match_conflict_bundle(), conflicted_estimator_bundle())
        )
        cited_ids = {ref.ref_id for ref in explanation.evidence_refs}
        assert "match-patch" in cited_ids
        assert "match-conflicted" not in cited_ids

    @pytest.mark.parametrize(
        "reason", ["NO_VALID_CANDIDATES", "NO_ATTRACTIVE_CANDIDATE"]
    )
    def test_non_stub_reason_codes_rejected(self, reason: str) -> None:
        with pytest.raises(ExplanationGenerationError, match="requires reason"):
            self.generate((match_conflict_bundle(),), reason)

    def test_zero_eligible_candidates_rejected(self) -> None:
        with pytest.raises(ExplanationGenerationError, match="at least one eligible"):
            self.generate((missing_estimator_bundle(),))

    def test_conflicting_reason_without_recorded_conflict_rejected(self) -> None:
        with pytest.raises(ExplanationGenerationError, match="declared conflict"):
            self.generate((f.make_consideration(),))

    def test_insufficient_reason_without_recorded_gap_rejected(self) -> None:
        with pytest.raises(ExplanationGenerationError, match="evidence\\s+gap"):
            self.generate((f.make_consideration(),), "INSUFFICIENT_EVIDENCE")

    def test_unresolvable_conflict_source_ref_rejected(self) -> None:
        with pytest.raises(ExplanationGenerationError, match="unresolved evidence ref"):
            generate_stub_abstention_explanation(
                run_id=RUN_ID,
                considered=(match_conflict_bundle(),),
                abstain_reason_code="CONFLICTING_EVIDENCE",
                fixture_source_id="a-different-source",
            )

    def test_repeatable(self) -> None:
        considered = (match_conflict_bundle(),)
        assert self.generate(considered) == self.generate(considered)

    def test_shipped_conflicting_evidence_fixture_cites_the_match_conflict(
        self, repo: FixtureRepository
    ) -> None:
        scenario = repo.load_scenario("conflicting-evidence")
        considered = tuple(
            consideration_from_bundle(bundle) for bundle in scenario.candidates
        )
        explanation = generate_stub_abstention_explanation(
            run_id=RUN_ID,
            considered=considered,
            abstain_reason_code="CONFLICTING_EVIDENCE",
            fixture_source_id=scenario.provenance.fixture_set_id,
        )
        assert_orchestrator_shape(explanation)
        # The actual recorded MatchContext conflict is cited, not merely
        # the market: the factor and the propagated conflict refs point at
        # the match entity.
        match_ref = EvidenceRef(
            kind="match", ref_id="syn-match-conflicting-evidence-01"
        )
        assert match_ref in factor_refs(explanation)
        assert match_ref in explanation.evidence_refs
        assert explanation.conflicts != ()


def selected_chain(
    consideration: CandidateEligibility | None = None,
    *,
    evaluated_at: datetime | None = None,
    config: PolicyConfig | None = None,
    is_duplicate_run: bool = False,
) -> tuple[CandidateEligibility, EdgeAssessment, PolicyDecision]:
    """One consistent (consideration, edge, real engine decision) chain."""
    consideration = (
        consideration if consideration is not None else f.make_consideration()
    )
    estimate = f.make_estimate(
        consideration.match_context, consideration.evaluation_side
    )
    edge = f.make_edge_assessment(estimate, consideration.market_snapshot)
    policy = evaluate_policy(
        candidate=consideration.market,
        match_context=consideration.match_context,
        snapshot=consideration.market_snapshot,
        edge=edge,
        evaluated_at=evaluated_at if evaluated_at is not None else f.ts(3),
        config=config if config is not None else FIXTURE_POLICY_CONFIG,
        is_duplicate_run=is_duplicate_run,
    )
    return consideration, edge, policy


def thin_edge_consideration() -> CandidateEligibility:
    """Fresh, complete, in-band evidence whose net edge alone falls short."""
    return f.make_consideration(
        market_snapshot=f.make_market_snapshot(
            ask_price_micro=630_000, bid_price_micro=620_000
        )
    )


class TestStubPostSelection:
    def generate(
        self,
        chain: tuple[CandidateEligibility, EdgeAssessment, PolicyDecision],
        *,
        considered: tuple[CandidateEligibility, ...] | None = None,
        selected: CandidateEligibility | None = None,
        edge: EdgeAssessment | None = None,
        policy_decision: PolicyDecision | None = None,
        policy_config: PolicyConfig | None = None,
        is_duplicate_run: bool = False,
    ) -> DecisionExplanation:
        chain_consideration, chain_edge, chain_policy = chain
        selected = selected if selected is not None else chain_consideration
        return generate_stub_post_selection_explanation(
            run_id=RUN_ID,
            considered=considered if considered is not None else (selected,),
            selected=selected,
            edge=edge if edge is not None else chain_edge,
            policy_decision=(
                policy_decision if policy_decision is not None else chain_policy
            ),
            fixture_source_id=f.FIXTURE_SET_ID,
            policy_config=(
                policy_config if policy_config is not None else FIXTURE_POLICY_CONFIG
            ),
            is_duplicate_run=is_duplicate_run,
        )

    def test_proceed_states_all_checks_passed_without_numbers(self) -> None:
        chain = selected_chain()
        assert chain[2].decision == "proceed"
        explanation = self.generate(chain)
        assert_orchestrator_shape(explanation)
        assert "policy checks passed" in explanation.summary
        texts = [factor.factor for factor in explanation.key_factors]
        assert any("deterministic stub procedure" in text for text in texts)
        assert any("policy checks passed" in text for text in texts)

    def test_no_bet_renders_the_failed_check_qualitatively(self) -> None:
        chain = selected_chain(thin_edge_consideration())
        assert chain[2].decision == "no_bet"
        explanation = self.generate(chain)
        assert_orchestrator_shape(explanation)
        assert "no-bet" in explanation.summary
        opposing = [
            factor
            for factor in explanation.key_factors
            if factor.direction == "opposes"
        ]
        assert len(opposing) == 1
        assert "net edge" in opposing[0].factor
        assert opposing[0].evidence_ref == EvidenceRef(
            kind="snapshot", ref_id=f.MARKET_ID
        )

    def test_no_bet_renders_every_failed_check_in_recorded_order(self) -> None:
        outside_band = f.make_consideration(
            market_snapshot=f.make_market_snapshot(
                ask_price_micro=950_000, bid_price_micro=940_000
            )
        )
        chain = selected_chain(outside_band)
        assert chain[2].decision == "no_bet"
        explanation = self.generate(chain)
        opposing = [
            factor.factor
            for factor in explanation.key_factors
            if factor.direction == "opposes"
        ]
        assert len(opposing) == 2
        assert "above the configured entry band" in opposing[0]
        assert "net edge" in opposing[1]

    def test_duplicate_run_status_is_explicit_and_rendered(self) -> None:
        chain = selected_chain(is_duplicate_run=True)
        assert chain[2].decision == "no_bet"
        explanation = self.generate(chain, is_duplicate_run=True)
        opposing = [
            factor.factor
            for factor in explanation.key_factors
            if factor.direction == "opposes"
        ]
        assert opposing == [
            "The run duplicates a previously decided run for this market."
        ]

    def test_forged_inputs_digest_rejected(self) -> None:
        chain = selected_chain()
        forged = f.rebuild_policy_decision(
            chain[2], inputs_digest=f.sha_hex("forged-policy-digest")
        )
        with pytest.raises(ExplanationGenerationError, match="recomputed"):
            self.generate(chain, policy_decision=forged)

    def test_decision_from_other_policy_configuration_rejected(self) -> None:
        alt_config = f.alt_policy_config()
        chain = selected_chain(config=alt_config)
        assert chain[2].decision == "proceed"
        with pytest.raises(ExplanationGenerationError, match="recomputed"):
            self.generate(chain)  # verified against the fixture config

    def test_explicit_policy_configuration_is_honored(self) -> None:
        alt_config = f.alt_policy_config()
        chain = selected_chain(config=alt_config)
        explanation = self.generate(chain, policy_config=alt_config)
        assert "policy checks passed" in explanation.summary

    def test_mismatched_edge_rejected(self) -> None:
        chain = selected_chain()
        other_snapshot = f.make_market_snapshot(
            ask_price_micro=610_000, bid_price_micro=600_000
        )
        other_edge = f.make_edge_assessment(
            f.make_estimate(chain[0].match_context), other_snapshot
        )
        with pytest.raises(ExplanationGenerationError, match="recomputed"):
            self.generate(chain, edge=other_edge)

    def test_selected_not_among_considered_rejected(self) -> None:
        chain = selected_chain()
        with pytest.raises(ExplanationGenerationError, match="among the"):
            self.generate(chain, considered=(f.make_second_consideration(),))

    def test_ineligible_selected_rejected(self) -> None:
        chain = selected_chain()
        ineligible = f.make_ineligible_consideration()
        with pytest.raises(ExplanationGenerationError, match="eligible"):
            self.generate(chain, selected=ineligible, considered=(ineligible,))

    def test_repeatable_and_inputs_unchanged(self) -> None:
        chain = selected_chain(thin_edge_consideration())
        selected, edge, decision = chain
        before = (selected.model_dump(), edge.model_dump(), decision.model_dump())
        first = self.generate(chain)
        second = self.generate(chain)
        assert first == second
        assert (
            selected.model_dump(),
            edge.model_dump(),
            decision.model_dump(),
        ) == before


class TestNoOracleInputs:
    @pytest.mark.parametrize("generator", GENERATORS)
    def test_no_scenario_or_oracle_parameters(self, generator: Any) -> None:
        parameters = set(inspect.signature(generator).parameters)
        assert not parameters & {
            "scenario_id",
            "scenario",
            "expected_outcome_class",
            "expected_reason_code",
        }


def content_kwargs(**over: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "summary": "Synthetic qualitative summary of the considered evidence.",
        "key_factors": (
            KeyFactor(
                factor="The synthetic rating gap favors the yes side.",
                direction="supports",
                evidence_ref=EvidenceRef(kind="match", ref_id=f.MATCH_ID),
            ),
        ),
        "conflicts": ("Synthetic sources disagree about the patch.",),
        "data_gaps": ("The recorded bid depth is declared unavailable.",),
        "confidence_qualifier": "medium",
        "evidence_refs": (EvidenceRef(kind="market", ref_id=f.MARKET_ID),),
    }
    kwargs.update(over)
    return kwargs


def make_content(**over: Any) -> AgentQualitativeContent:
    return AgentQualitativeContent(**content_kwargs(**over))


def default_catalog() -> EvidenceCatalog:
    return build_evidence_catalog(
        (f.make_consideration(),), fixture_source_id=f.FIXTURE_SET_ID
    )


def assemble(
    content: AgentQualitativeContent,
    catalog: EvidenceCatalog | None = None,
) -> DecisionExplanation:
    return assemble_agent_explanation(
        run_id=RUN_ID,
        content=content,
        prompt_version="prompt-1",
        model_metadata_ref="invocation-1",
        catalog=catalog if catalog is not None else default_catalog(),
    )


class TestAgentAssembly:
    def test_valid_content_assembles_the_exact_agent_explanation(self) -> None:
        content = make_content()
        explanation = assemble(content)
        assert explanation.run_id == RUN_ID
        assert explanation.source == "agent"
        assert explanation.prompt_version == "prompt-1"
        assert explanation.model_metadata_ref == "invocation-1"
        assert explanation.explanation_template_version is None
        assert explanation.summary == content.summary
        assert explanation.key_factors == content.key_factors
        assert explanation.conflicts == content.conflicts
        assert explanation.data_gaps == content.data_gaps
        assert explanation.confidence_qualifier == content.confidence_qualifier
        assert explanation.evidence_refs == content.evidence_refs

    def test_contract_carries_exactly_the_qualitative_fields(self) -> None:
        assert set(AgentQualitativeContent.model_fields) == {
            "summary",
            "key_factors",
            "conflicts",
            "data_gaps",
            "confidence_qualifier",
            "evidence_refs",
        }

    @pytest.mark.parametrize(
        "extra_field",
        [
            "selected_market_id",
            "abstained",
            "ask_price_micro",
            "probability_ppm",
            "net_edge_ppm",
            "prompt_version",
            "model_metadata_ref",
            "source",
            "token_count",
            "anything_else",
        ],
    )
    def test_unknown_fields_rejected(self, extra_field: str) -> None:
        kwargs = content_kwargs()
        kwargs[extra_field] = "x"
        with pytest.raises(ValidationError):
            AgentQualitativeContent(**kwargs)

    @pytest.mark.parametrize(
        ("location", "over"),
        [
            ("summary", {"summary": "The edge is 3 points."}),
            (
                "key_factors",
                {
                    "key_factors": (
                        KeyFactor(
                            factor="Roughly 50% either way.",
                            direction="neutral",
                            evidence_ref=EvidenceRef(kind="market", ref_id=f.MARKET_ID),
                        ),
                    )
                },
            ),
            ("conflicts", {"conflicts": ("Sources disagree by $ amounts.",)}),
            ("data_gaps", {"data_gaps": ("The ppm figure is unavailable.",)}),
        ],
    )
    def test_numeric_prose_rejected_in_every_location(
        self, location: str, over: dict[str, Any]
    ) -> None:
        with pytest.raises(ExplanationGenerationError, match=location):
            assemble(make_content(**over))

    def test_sensitive_content_rejected_without_echoing_it(self) -> None:
        secret = "password: hunter-and-friends"
        with pytest.raises(ExplanationGenerationError) as excinfo:
            assemble(make_content(summary=f"Note that {secret} was seen."))
        message = str(excinfo.value)
        assert "sensitive-content scan" in message
        assert "hunter" not in message

    def test_unresolved_top_level_ref_rejected(self) -> None:
        content = make_content(
            evidence_refs=(EvidenceRef(kind="market", ref_id="mkt-unknown"),)
        )
        with pytest.raises(ExplanationGenerationError, match="market:mkt-unknown"):
            assemble(content)

    def test_unresolved_key_factor_ref_rejected(self) -> None:
        content = make_content(
            key_factors=(
                KeyFactor(
                    factor="A factor citing an unknown match.",
                    direction="neutral",
                    evidence_ref=EvidenceRef(kind="match", ref_id="match-unknown"),
                ),
            )
        )
        with pytest.raises(ExplanationGenerationError, match="match:match-unknown"):
            assemble(content)

    def test_input_not_mutated(self) -> None:
        content = make_content()
        before = content.model_dump()
        assemble(content)
        assert content.model_dump() == before

    def test_repeatable(self) -> None:
        content = make_content()
        assert assemble(content) == assemble(content)
