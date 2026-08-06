"""Slice 3 tests: each shipped scenario proves its downstream preconditions.

Uses the real Slice 2 demo estimator and edge calculator only. The policy
engine and agent do not exist yet; these tests prove the deterministic
preconditions each scenario needs and record its exact expected values.
"""

from __future__ import annotations

import pytest

from kalakal.domain import (
    MATCH_ESTIMATOR_FIELDS,
    EdgeAssessment,
    EstimatorRejection,
    ProbabilityEstimate,
)
from kalakal.edge.calculator import calculate_edge
from kalakal.estimator.demo import DemoEstimator
from kalakal.fixtures import FixtureRepository, FixtureScenario, ScenarioCandidateBundle
from tests.unit.fixture_helpers import shipped_version_dir

# Jup Callers Season 1 counted entry band (CLAUDE.md §8) — externally
# sourced configured rule, recorded here as test expectations only; the
# policy engine that enforces it arrives in Slice 4.
ENTRY_BAND_MIN_MICRO = 100_000
ENTRY_BAND_MAX_MICRO = 900_000

# The §6.2.6 reference net edge produced by clear-edge; thin-edge must sit
# strictly below it so a future minimum-edge threshold can separate them.
CLEAR_EDGE_NET_EDGE_PPM = 44_000


@pytest.fixture(scope="module")
def repo() -> FixtureRepository:
    return FixtureRepository(shipped_version_dir())


def estimate_bundle(
    scenario: FixtureScenario, bundle: ScenarioCandidateBundle
) -> ProbabilityEstimate | EstimatorRejection:
    return DemoEstimator().estimate(
        bundle.match_context,
        bundle.evaluation_side,
        computed_at=scenario.evaluation_time,
    )


def edge_for_bundle(
    scenario: FixtureScenario,
    bundle: ScenarioCandidateBundle,
    estimate: ProbabilityEstimate,
) -> EdgeAssessment:
    return calculate_edge(
        estimate=estimate,
        snapshot=bundle.market_snapshot,
        fee_rate_ppm=scenario.fee_rate_ppm,
        fee_model_version=scenario.fee_model_version,
        computed_at=scenario.evaluation_time,
    )


def sole_bundle(scenario: FixtureScenario) -> ScenarioCandidateBundle:
    assert len(scenario.candidates) == 1
    return scenario.candidates[0]


def assert_estimator_fields_clean(bundle: ScenarioCandidateBundle) -> None:
    """§5.6 eligibility: no estimator-consumed field missing or conflicted."""
    quality = bundle.match_context.data_quality
    assert not set(quality.missing_fields) & set(MATCH_ESTIMATOR_FIELDS)
    conflicted = {conflict.field_path for conflict in quality.conflicts}
    assert not conflicted & set(MATCH_ESTIMATOR_FIELDS)


class TestClearEdge:
    def test_reference_arithmetic_reproduced_exactly(
        self, repo: FixtureRepository
    ) -> None:
        scenario = repo.load_scenario("clear-edge")
        bundle = sole_bundle(scenario)
        estimate = estimate_bundle(scenario, bundle)
        assert isinstance(estimate, ProbabilityEstimate)
        assert estimate.probability_ppm == 650_000
        edge = edge_for_bundle(scenario, bundle, estimate)
        assert edge.ask_price_micro == 600_000
        assert edge.fee_rate_ppm == 10_000
        assert edge.fee_estimate_micro == 6_000
        assert edge.gross_edge_ppm == 50_000
        assert edge.net_edge_ppm == CLEAR_EDGE_NET_EDGE_PPM

    def test_evidence_complete_fresh_and_inside_entry_band(
        self, repo: FixtureRepository
    ) -> None:
        scenario = repo.load_scenario("clear-edge")
        bundle = sole_bundle(scenario)
        assert bundle.candidate_market.data_quality.is_complete
        assert bundle.match_context.data_quality.is_complete
        assert bundle.market_snapshot.data_quality.is_complete
        assert bundle.candidate_market.valid_until >= scenario.evaluation_time
        assert bundle.match_context.valid_until >= scenario.evaluation_time
        assert bundle.market_snapshot.valid_until >= scenario.evaluation_time
        ask = bundle.market_snapshot.ask_price_micro
        assert ENTRY_BAND_MIN_MICRO <= ask <= ENTRY_BAND_MAX_MICRO


class TestThinEdge:
    def test_exact_intentionally_insufficient_edge(
        self, repo: FixtureRepository
    ) -> None:
        scenario = repo.load_scenario("thin-edge")
        bundle = sole_bundle(scenario)
        estimate = estimate_bundle(scenario, bundle)
        assert isinstance(estimate, ProbabilityEstimate)
        assert estimate.probability_ppm == 555_000
        edge = edge_for_bundle(scenario, bundle, estimate)
        assert edge.ask_price_micro == 548_000
        assert edge.fee_estimate_micro == 5_480
        assert edge.gross_edge_ppm == 7_000
        assert edge.net_edge_ppm == 1_520
        # Positive but strictly below the clear-edge reference, so any
        # future minimum-edge threshold between them separates the two.
        assert 0 < edge.net_edge_ppm < CLEAR_EDGE_NET_EDGE_PPM

    def test_complete_fresh_and_inside_entry_band(
        self, repo: FixtureRepository
    ) -> None:
        scenario = repo.load_scenario("thin-edge")
        bundle = sole_bundle(scenario)
        assert bundle.match_context.data_quality.is_complete
        assert bundle.market_snapshot.valid_until >= scenario.evaluation_time
        ask = bundle.market_snapshot.ask_price_micro
        assert ENTRY_BAND_MIN_MICRO <= ask <= ENTRY_BAND_MAX_MICRO


class TestConflictingEvidence:
    def test_non_estimator_conflict_declared_and_reference_resolves(
        self, repo: FixtureRepository
    ) -> None:
        scenario = repo.load_scenario("conflicting-evidence")
        bundle = sole_bundle(scenario)
        quality = bundle.match_context.data_quality
        assert not quality.is_complete
        assert quality.missing_fields == ()
        assert len(quality.conflicts) == 1
        conflict = quality.conflicts[0]
        assert conflict.field_path == "patch_label"
        assert conflict.field_path not in MATCH_ESTIMATOR_FIELDS
        # The repository's load-time checks already prove resolution; assert
        # the refs point at this scenario's own entities and source.
        ref_ids = {ref.ref_id for ref in conflict.evidence_refs}
        assert bundle.match_context.match_id in ref_ids
        assert scenario.provenance.fixture_set_id in ref_ids

    def test_candidate_stays_eligible_and_estimation_succeeds(
        self, repo: FixtureRepository
    ) -> None:
        scenario = repo.load_scenario("conflicting-evidence")
        bundle = sole_bundle(scenario)
        assert bundle.candidate_market.status == "open"
        assert_estimator_fields_clean(bundle)
        estimate = estimate_bundle(scenario, bundle)
        assert isinstance(estimate, ProbabilityEstimate)
        assert estimate.probability_ppm == 720_000
        edge = edge_for_bundle(scenario, bundle, estimate)
        assert edge.net_edge_ppm == 73_600


class TestStaleData:
    def test_internally_ordered_but_stale_at_evaluation_time(
        self, repo: FixtureRepository
    ) -> None:
        scenario = repo.load_scenario("stale-data")
        bundle = sole_bundle(scenario)
        snapshot = bundle.market_snapshot
        # Internally ordered and structurally valid...
        assert snapshot.captured_at <= snapshot.valid_until
        assert bundle.candidate_market.as_of <= bundle.candidate_market.valid_until
        # ...but the selected evidence is stale at the evaluation clock,
        # while the candidate and match context themselves stay fresh.
        assert snapshot.valid_until < scenario.evaluation_time
        assert bundle.candidate_market.valid_until >= scenario.evaluation_time
        assert bundle.match_context.valid_until >= scenario.evaluation_time

    def test_staleness_does_not_affect_pre_agent_eligibility(
        self, repo: FixtureRepository
    ) -> None:
        scenario = repo.load_scenario("stale-data")
        bundle = sole_bundle(scenario)
        assert bundle.candidate_market.status == "open"
        assert bundle.match_context.data_quality.is_complete
        assert_estimator_fields_clean(bundle)
        estimate = estimate_bundle(scenario, bundle)
        assert isinstance(estimate, ProbabilityEstimate)
        assert bundle.evaluation_side == "no"
        assert estimate.probability_ppm == 600_000
        edge = edge_for_bundle(scenario, bundle, estimate)
        assert edge.net_edge_ppm == 95_000


class TestOutsideEntryBand:
    def test_ask_valid_in_domain_but_outside_the_configured_band(
        self, repo: FixtureRepository
    ) -> None:
        scenario = repo.load_scenario("outside-entry-band")
        bundle = sole_bundle(scenario)
        ask = bundle.market_snapshot.ask_price_micro
        assert 0 < ask < 1_000_000
        assert ask == 950_000
        assert not ENTRY_BAND_MIN_MICRO <= ask <= ENTRY_BAND_MAX_MICRO

    def test_estimation_succeeds_with_positive_net_edge(
        self, repo: FixtureRepository
    ) -> None:
        # The band must be the only expected blocker: evidence is complete,
        # fresh, and the deterministic net edge is positive.
        scenario = repo.load_scenario("outside-entry-band")
        bundle = sole_bundle(scenario)
        assert bundle.match_context.data_quality.is_complete
        assert bundle.market_snapshot.valid_until >= scenario.evaluation_time
        estimate = estimate_bundle(scenario, bundle)
        assert isinstance(estimate, ProbabilityEstimate)
        assert estimate.probability_ppm == 980_000
        edge = edge_for_bundle(scenario, bundle, estimate)
        assert edge.fee_estimate_micro == 9_500
        assert edge.gross_edge_ppm == 30_000
        assert edge.net_edge_ppm == 20_500


class TestNoValidCandidates:
    def test_both_exclusion_paths_covered_and_no_candidate_is_eligible(
        self, repo: FixtureRepository
    ) -> None:
        scenario = repo.load_scenario("no-valid-candidates")
        assert len(scenario.candidates) == 2
        assert all(b.candidate_market.status == "open" for b in scenario.candidates)
        results = [estimate_bundle(scenario, b) for b in scenario.candidates]
        assert all(isinstance(result, EstimatorRejection) for result in results)
        missing, conflicted = results
        assert isinstance(missing, EstimatorRejection)
        assert isinstance(conflicted, EstimatorRejection)
        assert missing.missing_fields == ("yes_team_rating",)
        assert missing.conflicted_fields == ()
        assert conflicted.missing_fields == ()
        assert conflicted.conflicted_fields == ("no_team_form",)

    def test_declarations_match_null_fields_exactly(
        self, repo: FixtureRepository
    ) -> None:
        scenario = repo.load_scenario("no-valid-candidates")
        missing_bundle, conflicted_bundle = scenario.candidates
        match = missing_bundle.match_context
        assert match.yes_team_rating is None
        assert match.data_quality.missing_fields == ("yes_team_rating",)
        assert match.data_quality.conflicts == ()
        assert not match.data_quality.is_complete
        match = conflicted_bundle.match_context
        assert match.no_team_form is not None
        assert match.data_quality.missing_fields == ()
        assert [c.field_path for c in match.data_quality.conflicts] == ["no_team_form"]
        assert not match.data_quality.is_complete

    def test_rejections_are_typed_with_no_invented_defaults(
        self, repo: FixtureRepository
    ) -> None:
        scenario = repo.load_scenario("no-valid-candidates")
        for bundle in scenario.candidates:
            result = estimate_bundle(scenario, bundle)
            assert isinstance(result, EstimatorRejection)
            assert not hasattr(result, "probability_ppm")
            assert not hasattr(result, "basis")


class TestEstimatorBoundaryOverFixtures:
    def test_non_estimator_conflicts_do_not_reject_estimation(
        self, repo: FixtureRepository
    ) -> None:
        scenario = repo.load_scenario("conflicting-evidence")
        result = estimate_bundle(scenario, sole_bundle(scenario))
        assert isinstance(result, ProbabilityEstimate)

    def test_estimator_field_gaps_and_conflicts_do_reject_estimation(
        self, repo: FixtureRepository
    ) -> None:
        scenario = repo.load_scenario("no-valid-candidates")
        for bundle in scenario.candidates:
            result = estimate_bundle(scenario, bundle)
            assert isinstance(result, EstimatorRejection)
