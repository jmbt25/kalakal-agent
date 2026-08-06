"""Slice 4 tests: deterministic policy and abstention engine (§6.2.7).

Covers the versioned configuration, every rule passing and failing,
inclusive boundary semantics, reason-code priority, input-digest
repeatability and sensitivity, cross-contract rejection, purity, and the
shipped fixture scenarios evaluated through the real Slice 2 estimator and
edge calculator.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, cast

import pytest
from pydantic import ValidationError

from kalakal.domain import (
    DEMO_ESTIMATOR_DISPLAY_LABEL,
    CandidateMarket,
    DataQuality,
    EdgeAssessment,
    EstimatorBasis,
    MarketSnapshot,
    MatchContext,
    PolicyDecision,
    ProbabilityEstimate,
    estimate_inputs_digest,
)
from kalakal.edge.calculator import calculate_edge
from kalakal.estimator.demo import DemoEstimator
from kalakal.fixtures import FixtureRepository, FixtureScenario, ScenarioCandidateBundle
from kalakal.policy import (
    FIXTURE_POLICY_CONFIG,
    POLICY_CHECK_ORDER,
    POLICY_REASON_PRIORITY,
    PolicyConfig,
    PolicyInputError,
    evaluate_policy,
    policy_config_digest,
    policy_inputs_digest,
)
from kalakal.policy.engine import (
    CHECK_CANDIDATE_COMPLETENESS,
    CHECK_CANDIDATE_FRESHNESS,
    CHECK_DUPLICATE_RUN,
    CHECK_ENTRY_PRICE_MAX,
    CHECK_ENTRY_PRICE_MIN,
    CHECK_MATCH_COMPLETENESS,
    CHECK_MATCH_FRESHNESS,
    CHECK_MIN_NET_EDGE,
    CHECK_SNAPSHOT_COMPLETENESS,
    CHECK_SNAPSHOT_FRESHNESS,
    COMPLETENESS_RULE_SOURCE,
    DUPLICATE_RULE_SOURCE,
    FRESHNESS_RULE_SOURCE,
)
from tests.unit import factories as f
from tests.unit.fixture_helpers import shipped_version_dir

COMPLETENESS_CHECK_IDS = (
    CHECK_CANDIDATE_COMPLETENESS,
    CHECK_MATCH_COMPLETENESS,
    CHECK_SNAPSHOT_COMPLETENESS,
)
FRESHNESS_CHECK_IDS = (
    CHECK_CANDIDATE_FRESHNESS,
    CHECK_MATCH_FRESHNESS,
    CHECK_SNAPSHOT_FRESHNESS,
)


def evaluate(
    *,
    candidate: CandidateMarket | None = None,
    match_context: MatchContext | None = None,
    snapshot: MarketSnapshot | None = None,
    edge: EdgeAssessment | None = None,
    evaluated_at: datetime | None = None,
    config: PolicyConfig | None = None,
    is_duplicate_run: bool = False,
) -> PolicyDecision:
    """Evaluate factory-built inputs, overriding any subset of them."""
    match = match_context if match_context is not None else f.make_match_context()
    snap = snapshot if snapshot is not None else f.make_market_snapshot()
    if edge is None:
        edge = f.make_edge_assessment(f.make_estimate(match), snap)
    return evaluate_policy(
        candidate=candidate if candidate is not None else f.make_candidate_market(),
        match_context=match,
        snapshot=snap,
        edge=edge,
        evaluated_at=evaluated_at if evaluated_at is not None else f.ts(3),
        config=config if config is not None else FIXTURE_POLICY_CONFIG,
        is_duplicate_run=is_duplicate_run,
    )


def check_by_id(decision: PolicyDecision, check_id: str) -> Any:
    matches = [check for check in decision.checks if check.check_id == check_id]
    assert len(matches) == 1
    return matches[0]


def failed_check_ids(decision: PolicyDecision) -> tuple[str, ...]:
    return tuple(check.check_id for check in decision.checks if not check.passed)


def fixture_config_kwargs(**over: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "policy_version": FIXTURE_POLICY_CONFIG.policy_version,
        "min_entry_price_micro": FIXTURE_POLICY_CONFIG.min_entry_price_micro,
        "max_entry_price_micro": FIXTURE_POLICY_CONFIG.max_entry_price_micro,
        "min_net_edge_ppm": FIXTURE_POLICY_CONFIG.min_net_edge_ppm,
        "entry_band_source": FIXTURE_POLICY_CONFIG.entry_band_source,
        "min_net_edge_source": FIXTURE_POLICY_CONFIG.min_net_edge_source,
    }
    kwargs.update(over)
    return kwargs


def incomplete_candidate(**over: Any) -> CandidateMarket:
    quality = DataQuality(
        is_complete=False, missing_fields=(), conflicts=(f.make_conflict("status"),)
    )
    return f.make_candidate_market(data_quality=quality, **over)


def incomplete_match_context(**over: Any) -> MatchContext:
    # A typed conflict on a non-estimator field keeps the demo estimator
    # willing to estimate while the evidence is declared incomplete.
    quality = DataQuality(
        is_complete=False,
        missing_fields=(),
        conflicts=(f.make_conflict("patch_label"),),
    )
    return f.make_match_context(data_quality=quality, **over)


def incomplete_snapshot(**over: Any) -> MarketSnapshot:
    quality = DataQuality(
        is_complete=False, missing_fields=("bid_price_micro",), conflicts=()
    )
    return f.make_market_snapshot(bid_price_micro=None, data_quality=quality, **over)


def strong_yes_match() -> MatchContext:
    # score_yes 9590, score_no 210 -> probability 978_571 ppm, so a
    # near-upper-band ask still leaves a passing net edge.
    return f.make_match_context(
        yes_team_rating=9_500,
        yes_team_form=90,
        no_team_rating=200,
        no_team_form=10,
    )


class TestPolicyConfig:
    def test_fixture_config_values(self) -> None:
        assert FIXTURE_POLICY_CONFIG.policy_version == "fixture-policy-1"
        assert FIXTURE_POLICY_CONFIG.min_entry_price_micro == 100_000
        assert FIXTURE_POLICY_CONFIG.max_entry_price_micro == 900_000
        assert FIXTURE_POLICY_CONFIG.min_net_edge_ppm == 20_000

    def test_fixture_config_provenance_is_truthful(self) -> None:
        band = FIXTURE_POLICY_CONFIG.entry_band_source
        assert "Jup Callers" in band
        assert "CLAUDE.md §8" in band
        edge = FIXTURE_POLICY_CONFIG.min_net_edge_source
        assert "fixture-MVP" in edge
        assert "not a Jupiter or Jup Callers rule" in edge

    def test_kwargs_round_trip_equals_fixture_config(self) -> None:
        assert PolicyConfig(**fixture_config_kwargs()) == FIXTURE_POLICY_CONFIG

    def test_config_is_frozen(self) -> None:
        with pytest.raises(ValidationError):
            FIXTURE_POLICY_CONFIG.min_net_edge_ppm = 1

    @pytest.mark.parametrize("max_entry", [100_000, 99_999])
    def test_min_entry_must_be_strictly_below_max(self, max_entry: int) -> None:
        with pytest.raises(ValidationError, match="strictly below"):
            PolicyConfig(**fixture_config_kwargs(max_entry_price_micro=max_entry))

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("min_entry_price_micro", 0),
            ("min_entry_price_micro", -1),
            ("max_entry_price_micro", 1_000_000),
            ("min_net_edge_ppm", 0),
            ("min_net_edge_ppm", -1),
            ("min_net_edge_ppm", 1_000_001),
        ],
    )
    def test_out_of_range_thresholds_rejected(self, field: str, value: int) -> None:
        with pytest.raises(ValidationError):
            PolicyConfig(**fixture_config_kwargs(**{field: value}))

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("min_entry_price_micro", 100_000.0),
            ("min_net_edge_ppm", 20_000.0),
            ("min_net_edge_ppm", True),
            ("policy_version", 1),
        ],
    )
    def test_wrong_value_types_rejected(self, field: str, value: object) -> None:
        with pytest.raises(ValidationError):
            PolicyConfig(**fixture_config_kwargs(**{field: value}))

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("policy_version", ""),
            ("entry_band_source", ""),
            ("min_net_edge_source", ""),
            ("entry_band_source", "x" * 201),
            ("min_net_edge_source", "x" * 201),
        ],
    )
    def test_version_and_source_bounds_enforced(self, field: str, value: str) -> None:
        with pytest.raises(ValidationError):
            PolicyConfig(**fixture_config_kwargs(**{field: value}))

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PolicyConfig(**fixture_config_kwargs(freshness_seconds=60))

    @pytest.mark.parametrize(
        "field",
        [
            "policy_version",
            "min_entry_price_micro",
            "max_entry_price_micro",
            "min_net_edge_ppm",
            "entry_band_source",
            "min_net_edge_source",
        ],
    )
    def test_required_fields(self, field: str) -> None:
        kwargs = fixture_config_kwargs()
        del kwargs[field]
        with pytest.raises(ValidationError):
            PolicyConfig(**kwargs)

    def test_config_digest_repeatable(self) -> None:
        first = policy_config_digest(FIXTURE_POLICY_CONFIG)
        second = policy_config_digest(PolicyConfig(**fixture_config_kwargs()))
        assert first == second

    def test_config_digest_sensitive_to_every_field(self) -> None:
        baseline = policy_config_digest(FIXTURE_POLICY_CONFIG)
        overrides: list[dict[str, Any]] = [
            {"policy_version": "fixture-policy-2"},
            {"min_entry_price_micro": 100_001},
            {"max_entry_price_micro": 899_999},
            {"min_net_edge_ppm": 20_001},
            {"entry_band_source": "Changed entry-band provenance."},
            {"min_net_edge_source": "Changed net-edge provenance."},
        ]
        digests = {
            policy_config_digest(PolicyConfig(**fixture_config_kwargs(**over)))
            for over in overrides
        }
        assert len(digests) == len(overrides)
        assert baseline not in digests


class TestProceedDecision:
    def test_all_checks_pass_proceed(self) -> None:
        decision = evaluate()
        assert decision.decision == "proceed"
        assert decision.reason_codes == ()
        assert len(decision.checks) == 10
        assert all(check.passed for check in decision.checks)

    def test_check_order_and_unique_ids(self) -> None:
        decision = evaluate()
        check_ids = tuple(check.check_id for check in decision.checks)
        assert check_ids == POLICY_CHECK_ORDER
        assert len(set(check_ids)) == len(check_ids)

    def test_evaluated_at_and_policy_version_echoed(self) -> None:
        evaluated_at = f.ts(7)
        decision = evaluate(evaluated_at=evaluated_at)
        assert decision.evaluated_at == evaluated_at
        assert decision.policy_version == FIXTURE_POLICY_CONFIG.policy_version
        assert decision.schema_version == "1"

    def test_custom_config_version_echoed(self) -> None:
        config = PolicyConfig(
            **fixture_config_kwargs(policy_version="fixture-policy-2")
        )
        decision = evaluate(config=config)
        assert decision.policy_version == "fixture-policy-2"

    def test_check_observations_truthful(self) -> None:
        decision = evaluate()
        for check_id in COMPLETENESS_CHECK_IDS:
            check = check_by_id(decision, check_id)
            assert check.observed_value == 1
            assert check.threshold_value == 1
            assert check.threshold_source == COMPLETENESS_RULE_SOURCE
        for check_id in FRESHNESS_CHECK_IDS:
            check = check_by_id(decision, check_id)
            # valid_until ts(60) minus evaluated_at ts(3) = 57 minutes.
            assert check.observed_value == 3_420
            assert check.threshold_value == 0
            assert check.threshold_source == FRESHNESS_RULE_SOURCE
        entry_min = check_by_id(decision, CHECK_ENTRY_PRICE_MIN)
        assert entry_min.observed_value == 600_000
        assert entry_min.threshold_value == 100_000
        assert entry_min.threshold_source == FIXTURE_POLICY_CONFIG.entry_band_source
        entry_max = check_by_id(decision, CHECK_ENTRY_PRICE_MAX)
        assert entry_max.observed_value == 600_000
        assert entry_max.threshold_value == 900_000
        assert entry_max.threshold_source == FIXTURE_POLICY_CONFIG.entry_band_source
        net_edge = check_by_id(decision, CHECK_MIN_NET_EDGE)
        assert net_edge.observed_value == 44_000
        assert net_edge.threshold_value == 20_000
        assert net_edge.threshold_source == FIXTURE_POLICY_CONFIG.min_net_edge_source
        duplicate = check_by_id(decision, CHECK_DUPLICATE_RUN)
        assert duplicate.observed_value == 0
        assert duplicate.threshold_value == 0
        assert duplicate.threshold_source == DUPLICATE_RULE_SOURCE

    def test_deterministic_repeatability(self) -> None:
        first = evaluate()
        second = evaluate()
        assert first == second
        assert first.model_dump_json() == second.model_dump_json()
        assert first.inputs_digest == second.inputs_digest


class TestSingleRuleFailures:
    def test_incomplete_candidate(self) -> None:
        decision = evaluate(candidate=incomplete_candidate())
        assert decision.decision == "no_bet"
        assert decision.reason_codes == ("POLICY_INCOMPLETE_DATA",)
        assert failed_check_ids(decision) == (CHECK_CANDIDATE_COMPLETENESS,)
        assert check_by_id(decision, CHECK_CANDIDATE_COMPLETENESS).observed_value == 0

    def test_incomplete_match_context(self) -> None:
        decision = evaluate(match_context=incomplete_match_context())
        assert decision.decision == "no_bet"
        assert decision.reason_codes == ("POLICY_INCOMPLETE_DATA",)
        assert failed_check_ids(decision) == (CHECK_MATCH_COMPLETENESS,)

    def test_incomplete_snapshot(self) -> None:
        decision = evaluate(snapshot=incomplete_snapshot())
        assert decision.decision == "no_bet"
        assert decision.reason_codes == ("POLICY_INCOMPLETE_DATA",)
        assert failed_check_ids(decision) == (CHECK_SNAPSHOT_COMPLETENESS,)

    def test_typed_conflict_alone_fails_completeness(self) -> None:
        # All fields present; a typed conflict still makes evidence
        # incomplete for policy purposes (§6.2.12).
        match = incomplete_match_context()
        assert match.patch_label is not None
        decision = evaluate(match_context=match)
        assert decision.reason_codes == ("POLICY_INCOMPLETE_DATA",)

    def test_stale_candidate(self) -> None:
        decision = evaluate(candidate=f.make_candidate_market(valid_until=f.ts(2)))
        assert decision.decision == "no_bet"
        assert decision.reason_codes == ("POLICY_STALE_DATA",)
        assert failed_check_ids(decision) == (CHECK_CANDIDATE_FRESHNESS,)

    def test_stale_match_context(self) -> None:
        decision = evaluate(match_context=f.make_match_context(valid_until=f.ts(2)))
        assert decision.decision == "no_bet"
        assert decision.reason_codes == ("POLICY_STALE_DATA",)
        assert failed_check_ids(decision) == (CHECK_MATCH_FRESHNESS,)

    def test_stale_snapshot(self) -> None:
        decision = evaluate(snapshot=f.make_market_snapshot(valid_until=f.ts(2)))
        assert decision.decision == "no_bet"
        assert decision.reason_codes == ("POLICY_STALE_DATA",)
        assert failed_check_ids(decision) == (CHECK_SNAPSHOT_FRESHNESS,)

    def test_ask_immediately_below_band(self) -> None:
        decision = evaluate(snapshot=f.make_market_snapshot(ask_price_micro=99_999))
        assert decision.decision == "no_bet"
        assert decision.reason_codes == ("POLICY_OUTSIDE_ENTRY_BAND",)
        assert failed_check_ids(decision) == (CHECK_ENTRY_PRICE_MIN,)
        assert check_by_id(decision, CHECK_MIN_NET_EDGE).passed

    def test_ask_immediately_above_band(self) -> None:
        decision = evaluate(
            match_context=strong_yes_match(),
            snapshot=f.make_market_snapshot(ask_price_micro=900_001),
        )
        assert decision.decision == "no_bet"
        assert decision.reason_codes == ("POLICY_OUTSIDE_ENTRY_BAND",)
        assert failed_check_ids(decision) == (CHECK_ENTRY_PRICE_MAX,)
        assert check_by_id(decision, CHECK_MIN_NET_EDGE).passed

    def test_net_edge_one_below_minimum(self) -> None:
        # The factory net edge is exactly 44_000; a 44_001 threshold is one
        # unit above it, so the inclusive rule fails by exactly one ppm.
        config = PolicyConfig(**fixture_config_kwargs(min_net_edge_ppm=44_001))
        decision = evaluate(config=config)
        assert decision.decision == "no_bet"
        assert decision.reason_codes == ("POLICY_INSUFFICIENT_NET_EDGE",)
        assert failed_check_ids(decision) == (CHECK_MIN_NET_EDGE,)

    def test_duplicate_run(self) -> None:
        decision = evaluate(is_duplicate_run=True)
        assert decision.decision == "no_bet"
        assert decision.reason_codes == ("POLICY_DUPLICATE_RUN",)
        assert failed_check_ids(decision) == (CHECK_DUPLICATE_RUN,)
        duplicate = check_by_id(decision, CHECK_DUPLICATE_RUN)
        assert duplicate.observed_value == 1
        assert duplicate.threshold_value == 0

    def test_no_bet_is_a_normal_policy_decision(self) -> None:
        decision = evaluate(is_duplicate_run=True)
        assert isinstance(decision, PolicyDecision)
        assert decision.decision == "no_bet"


class TestBoundarySemantics:
    def test_ask_at_inclusive_lower_bound_passes(self) -> None:
        decision = evaluate(snapshot=f.make_market_snapshot(ask_price_micro=100_000))
        assert decision.decision == "proceed"
        entry_min = check_by_id(decision, CHECK_ENTRY_PRICE_MIN)
        assert entry_min.observed_value == entry_min.threshold_value == 100_000

    def test_ask_at_inclusive_upper_bound_passes(self) -> None:
        decision = evaluate(
            match_context=strong_yes_match(),
            snapshot=f.make_market_snapshot(ask_price_micro=900_000),
        )
        assert decision.decision == "proceed"
        entry_max = check_by_id(decision, CHECK_ENTRY_PRICE_MAX)
        assert entry_max.observed_value == entry_max.threshold_value == 900_000

    def test_net_edge_at_inclusive_minimum_passes(self) -> None:
        config = PolicyConfig(**fixture_config_kwargs(min_net_edge_ppm=44_000))
        decision = evaluate(config=config)
        assert decision.decision == "proceed"
        net_edge = check_by_id(decision, CHECK_MIN_NET_EDGE)
        assert net_edge.observed_value == net_edge.threshold_value == 44_000

    def test_valid_until_equal_to_evaluated_at_is_fresh(self) -> None:
        # Every factory entity expires at ts(60); exactly then is fresh.
        decision = evaluate(evaluated_at=f.ts(60))
        assert decision.decision == "proceed"
        for check_id in FRESHNESS_CHECK_IDS:
            check = check_by_id(decision, check_id)
            assert check.passed
            assert check.observed_value == 0

    def test_one_microsecond_after_expiry_is_stale(self) -> None:
        decision = evaluate(evaluated_at=f.ts(60) + timedelta(microseconds=1))
        assert decision.decision == "no_bet"
        assert decision.reason_codes == ("POLICY_STALE_DATA",)
        for check_id in FRESHNESS_CHECK_IDS:
            check = check_by_id(decision, check_id)
            assert not check.passed
            assert check.observed_value == -1

    def test_freshness_observation_saturates_without_flipping(self) -> None:
        # The reported seconds saturate at ±2_000_000 (the PolicyCheck
        # observed-value bound); pass/fail still follows the exact rule.
        far_future = f.ts(0) + timedelta(days=365)
        fresh = evaluate(candidate=f.make_candidate_market(valid_until=far_future))
        fresh_check = check_by_id(fresh, CHECK_CANDIDATE_FRESHNESS)
        assert fresh_check.passed
        assert fresh_check.observed_value == 2_000_000
        stale = evaluate(evaluated_at=f.ts(60) + timedelta(days=365))
        stale_check = check_by_id(stale, CHECK_CANDIDATE_FRESHNESS)
        assert not stale_check.passed
        assert stale_check.observed_value == -2_000_000


class TestMultipleFailures:
    def all_failing_decision(self) -> PolicyDecision:
        match = incomplete_match_context(valid_until=f.ts(2))
        snapshot = f.make_market_snapshot(ask_price_micro=950_000, valid_until=f.ts(2))
        return evaluate(
            candidate=incomplete_candidate(valid_until=f.ts(2)),
            match_context=match,
            snapshot=snapshot,
            edge=f.make_edge_assessment(f.make_estimate(match), snapshot),
            is_duplicate_run=True,
        )

    def test_every_reason_retained_in_priority_order(self) -> None:
        decision = self.all_failing_decision()
        assert decision.decision == "no_bet"
        assert decision.reason_codes == POLICY_REASON_PRIORITY

    def test_all_checks_evaluated_without_short_circuit(self) -> None:
        decision = self.all_failing_decision()
        assert tuple(check.check_id for check in decision.checks) == POLICY_CHECK_ORDER
        expected_passed = {
            CHECK_CANDIDATE_COMPLETENESS: False,
            CHECK_MATCH_COMPLETENESS: False,
            CHECK_SNAPSHOT_COMPLETENESS: True,
            CHECK_CANDIDATE_FRESHNESS: False,
            CHECK_MATCH_FRESHNESS: False,
            CHECK_SNAPSHOT_FRESHNESS: False,
            CHECK_ENTRY_PRICE_MIN: True,
            CHECK_ENTRY_PRICE_MAX: False,
            CHECK_MIN_NET_EDGE: False,
            CHECK_DUPLICATE_RUN: False,
        }
        observed = {check.check_id: check.passed for check in decision.checks}
        assert observed == expected_passed

    def test_reason_order_is_priority_not_collection_order(self) -> None:
        stale_and_duplicate = evaluate(
            snapshot=f.make_market_snapshot(valid_until=f.ts(2)),
            is_duplicate_run=True,
        )
        assert stale_and_duplicate.reason_codes == (
            "POLICY_STALE_DATA",
            "POLICY_DUPLICATE_RUN",
        )
        incomplete_and_outside = evaluate(
            candidate=incomplete_candidate(),
            snapshot=f.make_market_snapshot(ask_price_micro=99_999),
        )
        assert incomplete_and_outside.reason_codes == (
            "POLICY_INCOMPLETE_DATA",
            "POLICY_OUTSIDE_ENTRY_BAND",
        )

    def test_incomplete_reason_deduplicated_across_entities(self) -> None:
        match = incomplete_match_context()
        snapshot = incomplete_snapshot()
        decision = evaluate(
            candidate=incomplete_candidate(),
            match_context=match,
            snapshot=snapshot,
            edge=f.make_edge_assessment(f.make_estimate(match), snapshot),
        )
        assert decision.reason_codes == ("POLICY_INCOMPLETE_DATA",)
        assert failed_check_ids(decision) == COMPLETENESS_CHECK_IDS

    def test_stale_reason_deduplicated_across_entities(self) -> None:
        decision = evaluate(evaluated_at=f.ts(61))
        assert decision.reason_codes == ("POLICY_STALE_DATA",)
        assert failed_check_ids(decision) == FRESHNESS_CHECK_IDS


class TestInputsDigest:
    def test_digest_matches_standalone_function(self) -> None:
        match = f.make_match_context()
        snapshot = f.make_market_snapshot()
        edge = f.make_edge_assessment(f.make_estimate(match), snapshot)
        candidate = f.make_candidate_market()
        decision = evaluate_policy(
            candidate=candidate,
            match_context=match,
            snapshot=snapshot,
            edge=edge,
            evaluated_at=f.ts(3),
            config=FIXTURE_POLICY_CONFIG,
            is_duplicate_run=False,
        )
        assert decision.inputs_digest == policy_inputs_digest(
            candidate=candidate,
            match_context=match,
            snapshot=snapshot,
            edge=edge,
            evaluated_at=f.ts(3),
            config=FIXTURE_POLICY_CONFIG,
            is_duplicate_run=False,
        )

    def test_digest_repeatable(self) -> None:
        assert evaluate().inputs_digest == evaluate().inputs_digest

    def test_digest_sensitive_to_every_decision_relevant_input(self) -> None:
        baseline = evaluate().inputs_digest
        snapshot_variant = f.make_market_snapshot(
            provenance=f.make_provenance(content_digest=f.sha_hex("snapshot-2"))
        )
        variants: list[PolicyDecision] = [
            evaluate(
                candidate=f.make_candidate_market(
                    provenance=f.make_provenance(
                        content_digest=f.sha_hex("candidate-2")
                    )
                )
            ),
            evaluate(
                match_context=f.make_match_context(
                    provenance=f.make_provenance(content_digest=f.sha_hex("match-2"))
                )
            ),
            evaluate(snapshot=snapshot_variant),
            evaluate(candidate=f.make_candidate_market(valid_until=f.ts(59))),
            evaluate(match_context=f.make_match_context(valid_until=f.ts(59))),
            evaluate(snapshot=f.make_market_snapshot(valid_until=f.ts(59))),
            evaluate(candidate=incomplete_candidate()),
            evaluate(match_context=incomplete_match_context()),
            evaluate(snapshot=incomplete_snapshot()),
            evaluate(edge=f.make_edge_assessment(fee_rate_ppm=20_000)),
            evaluate(evaluated_at=f.ts(3) + timedelta(microseconds=1)),
            evaluate(is_duplicate_run=True),
            evaluate(
                config=PolicyConfig(
                    **fixture_config_kwargs(policy_version="fixture-policy-2")
                )
            ),
            evaluate(
                config=PolicyConfig(
                    **fixture_config_kwargs(min_entry_price_micro=100_001)
                )
            ),
            evaluate(
                config=PolicyConfig(
                    **fixture_config_kwargs(max_entry_price_micro=899_999)
                )
            ),
            evaluate(
                config=PolicyConfig(**fixture_config_kwargs(min_net_edge_ppm=20_001))
            ),
            evaluate(
                config=PolicyConfig(
                    **fixture_config_kwargs(
                        entry_band_source="Changed entry-band provenance."
                    )
                )
            ),
            evaluate(
                config=PolicyConfig(
                    **fixture_config_kwargs(
                        min_net_edge_source="Changed net-edge provenance."
                    )
                )
            ),
        ]
        digests = [decision.inputs_digest for decision in variants]
        assert len(set(digests)) == len(digests)
        assert baseline not in digests


class TestDigestBindsDirectPolicyFields:
    """Regression: fields the engine reads directly must be bound.

    A Pydantic-valid entity can be constructed with changed content but an
    unchanged declared provenance digest (only the fixture repository
    verifies declared digests against raw bytes), so the policy digest
    must not rely on declared digests alone. Every test here proves the
    variant keeps the baseline's declared provenance digest while the
    policy inputs digest still changes.
    """

    def test_candidate_valid_until_bound_despite_same_provenance(self) -> None:
        baseline_entity = f.make_candidate_market()
        variant_entity = f.make_candidate_market(valid_until=f.ts(59))
        assert (
            variant_entity.provenance.content_digest
            == baseline_entity.provenance.content_digest
        )
        baseline = evaluate(candidate=baseline_entity)
        variant = evaluate(candidate=variant_entity)
        assert baseline.inputs_digest != variant.inputs_digest

    def test_match_context_valid_until_bound_despite_same_provenance(self) -> None:
        baseline_entity = f.make_match_context()
        variant_entity = f.make_match_context(valid_until=f.ts(59))
        assert (
            variant_entity.provenance.content_digest
            == baseline_entity.provenance.content_digest
        )
        baseline = evaluate(match_context=baseline_entity)
        variant = evaluate(match_context=variant_entity)
        assert baseline.inputs_digest != variant.inputs_digest

    def test_snapshot_valid_until_bound_despite_same_provenance(self) -> None:
        baseline_entity = f.make_market_snapshot()
        variant_entity = f.make_market_snapshot(valid_until=f.ts(59))
        assert (
            variant_entity.provenance.content_digest
            == baseline_entity.provenance.content_digest
        )
        # evaluate() rebuilds the validated edge from the supplied snapshot.
        baseline = evaluate(snapshot=baseline_entity)
        variant = evaluate(snapshot=variant_entity)
        assert baseline.inputs_digest != variant.inputs_digest

    def test_candidate_completeness_bound_despite_same_provenance(self) -> None:
        complete = f.make_candidate_market()
        incomplete = incomplete_candidate()
        assert (
            incomplete.provenance.content_digest == complete.provenance.content_digest
        )
        baseline = evaluate(candidate=complete)
        variant = evaluate(candidate=incomplete)
        assert baseline.decision == "proceed"
        assert variant.decision == "no_bet"
        assert baseline.inputs_digest != variant.inputs_digest

    def test_match_context_completeness_bound_despite_same_provenance(self) -> None:
        complete = f.make_match_context()
        incomplete = incomplete_match_context()
        assert (
            incomplete.provenance.content_digest == complete.provenance.content_digest
        )
        baseline = evaluate(match_context=complete)
        variant = evaluate(match_context=incomplete)
        assert baseline.decision == "proceed"
        assert variant.decision == "no_bet"
        assert baseline.inputs_digest != variant.inputs_digest

    def test_snapshot_completeness_bound_despite_same_provenance(self) -> None:
        complete = f.make_market_snapshot()
        incomplete = incomplete_snapshot()
        assert (
            incomplete.provenance.content_digest == complete.provenance.content_digest
        )
        baseline = evaluate(snapshot=complete)
        variant = evaluate(snapshot=incomplete)
        assert baseline.decision == "proceed"
        assert variant.decision == "no_bet"
        assert baseline.inputs_digest != variant.inputs_digest

    def test_proceed_and_no_bet_inputs_never_share_digest(self) -> None:
        proceed = evaluate()
        no_bet = evaluate(candidate=incomplete_candidate())
        assert proceed.decision == "proceed"
        assert no_bet.decision == "no_bet"
        assert proceed.inputs_digest != no_bet.inputs_digest

    def test_fresh_and_stale_inputs_never_share_digest(self) -> None:
        fresh = evaluate()
        stale = evaluate(candidate=f.make_candidate_market(valid_until=f.ts(2)))
        assert fresh.decision == "proceed"
        assert stale.reason_codes == ("POLICY_STALE_DATA",)
        assert fresh.inputs_digest != stale.inputs_digest


class TestCrossContractRejection:
    def test_match_context_market_mismatch(self) -> None:
        with pytest.raises(PolicyInputError, match="match_context.market_id"):
            evaluate(
                match_context=f.make_match_context(market_id="mkt-2"),
                edge=f.make_edge_assessment(),
            )

    def test_snapshot_market_mismatch(self) -> None:
        with pytest.raises(PolicyInputError, match="snapshot.market_id"):
            evaluate(
                snapshot=f.make_market_snapshot(market_id="mkt-2"),
                edge=f.make_edge_assessment(),
            )

    def test_edge_market_mismatch(self) -> None:
        other_match = f.make_match_context(market_id="mkt-2")
        other_snapshot = f.make_market_snapshot(market_id="mkt-2")
        other_edge = f.make_edge_assessment(
            f.make_estimate(other_match), other_snapshot
        )
        with pytest.raises(PolicyInputError, match="edge.market_id"):
            evaluate(edge=other_edge)

    def test_side_mismatch(self) -> None:
        with pytest.raises(PolicyInputError, match="side"):
            evaluate(
                snapshot=f.make_market_snapshot(side="no"),
                edge=f.make_edge_assessment(),
            )

    def test_ask_price_mismatch(self) -> None:
        with pytest.raises(PolicyInputError, match="ask_price_micro"):
            evaluate(
                snapshot=f.make_market_snapshot(ask_price_micro=601_000),
                edge=f.make_edge_assessment(),
            )

    def test_fee_model_version_mismatch(self) -> None:
        with pytest.raises(PolicyInputError, match="fee_model_version"):
            evaluate(
                snapshot=f.make_market_snapshot(fee_model_version="synthetic-fee-2"),
                edge=f.make_edge_assessment(),
            )

    def test_snapshot_digest_mismatch(self) -> None:
        with pytest.raises(PolicyInputError, match="snapshot_content_digest"):
            evaluate(
                snapshot=f.make_market_snapshot(
                    provenance=f.make_provenance(content_digest=f.sha_hex("other"))
                ),
                edge=f.make_edge_assessment(),
            )

    def test_naive_evaluated_at_rejected(self) -> None:
        with pytest.raises(PolicyInputError, match="timezone-aware UTC"):
            evaluate(evaluated_at=datetime(2026, 8, 5, 12, 0, 0))  # noqa: DTZ001

    def test_non_utc_evaluated_at_rejected(self) -> None:
        offset = timezone(timedelta(hours=1))
        with pytest.raises(PolicyInputError, match="timezone-aware UTC"):
            evaluate(evaluated_at=datetime(2026, 8, 5, 12, 0, 0, tzinfo=offset))

    def test_non_bool_duplicate_flag_rejected(self) -> None:
        with pytest.raises(PolicyInputError, match="bool"):
            evaluate(is_duplicate_run=cast("bool", 1))

    def test_non_model_input_rejected(self) -> None:
        with pytest.raises(PolicyInputError, match="CandidateMarket"):
            evaluate(candidate=cast("CandidateMarket", object()))

    def test_mismatch_is_an_error_not_a_no_bet(self) -> None:
        assert issubclass(PolicyInputError, ValueError)
        try:
            evaluate(
                match_context=f.make_match_context(market_id="mkt-2"),
                edge=f.make_edge_assessment(),
            )
        except PolicyInputError:
            return
        raise AssertionError("expected PolicyInputError")


class TestPurity:
    def test_inputs_not_mutated(self) -> None:
        candidate = f.make_candidate_market()
        match = f.make_match_context()
        snapshot = f.make_market_snapshot()
        edge = f.make_edge_assessment(f.make_estimate(match), snapshot)
        config = PolicyConfig(**fixture_config_kwargs())
        before = [
            candidate.model_dump(),
            match.model_dump(),
            snapshot.model_dump(),
            edge.model_dump(),
            config.model_dump(),
        ]
        evaluate_policy(
            candidate=candidate,
            match_context=match,
            snapshot=snapshot,
            edge=edge,
            evaluated_at=f.ts(3),
            config=config,
            is_duplicate_run=False,
        )
        after = [
            candidate.model_dump(),
            match.model_dump(),
            snapshot.model_dump(),
            edge.model_dump(),
            config.model_dump(),
        ]
        assert before == after

    def test_no_floats_anywhere_in_decision(self) -> None:
        def assert_no_float(value: object) -> None:
            assert not isinstance(value, float)
            if isinstance(value, dict):
                for item in value.values():
                    assert_no_float(item)
            elif isinstance(value, list | tuple):
                for item in value:
                    assert_no_float(item)

        for decision in (evaluate(), evaluate(is_duplicate_run=True)):
            assert_no_float(decision.model_dump())


@pytest.fixture(scope="module")
def repo() -> FixtureRepository:
    return FixtureRepository(shipped_version_dir())


def evaluate_bundle(
    scenario: FixtureScenario,
    bundle: ScenarioCandidateBundle,
    estimate: ProbabilityEstimate | None = None,
) -> PolicyDecision:
    if estimate is None:
        result = DemoEstimator().estimate(
            bundle.match_context,
            bundle.evaluation_side,
            computed_at=scenario.evaluation_time,
        )
        assert isinstance(result, ProbabilityEstimate)
        estimate = result
    edge = calculate_edge(
        estimate=estimate,
        snapshot=bundle.market_snapshot,
        fee_rate_ppm=scenario.fee_rate_ppm,
        fee_model_version=scenario.fee_model_version,
        computed_at=scenario.evaluation_time,
    )
    return evaluate_policy(
        candidate=bundle.candidate_market,
        match_context=bundle.match_context,
        snapshot=bundle.market_snapshot,
        edge=edge,
        evaluated_at=scenario.evaluation_time,
        config=FIXTURE_POLICY_CONFIG,
        is_duplicate_run=False,
    )


def fabricate_estimate(
    scenario: FixtureScenario, bundle: ScenarioCandidateBundle
) -> ProbabilityEstimate:
    """Test seam: a synthetic estimate for evidence the estimator refuses.

    Normal orchestration never estimates these candidates (§5.6, §10.1);
    this seam exists solely to prove the policy engine independently
    rejects incomplete evidence as defense in depth.
    """
    basis = EstimatorBasis(
        match_id=bundle.match_context.match_id,
        yes_team_rating=600,
        yes_team_form=50,
        no_team_rating=310,
        no_team_form=40,
    )
    return ProbabilityEstimate(
        schema_version="1",
        market_id=bundle.candidate_market.market_id,
        side=bundle.evaluation_side,
        probability_ppm=650_000,
        estimator_id="demo",
        estimator_version="1.0.0",
        is_predictive=False,
        display_label=DEMO_ESTIMATOR_DISPLAY_LABEL,
        basis=basis,
        inputs_digest=estimate_inputs_digest(
            estimator_id="demo",
            estimator_version="1.0.0",
            market_id=bundle.candidate_market.market_id,
            side=bundle.evaluation_side,
            basis=basis,
        ),
        computed_at=scenario.evaluation_time,
    )


class TestFixtureScenarios:
    @pytest.mark.parametrize(
        ("scenario_id", "expected_decision", "expected_reasons"),
        [
            ("clear-edge", "proceed", ()),
            ("thin-edge", "no_bet", ("POLICY_INSUFFICIENT_NET_EDGE",)),
            ("stale-data", "no_bet", ("POLICY_STALE_DATA",)),
            ("outside-entry-band", "no_bet", ("POLICY_OUTSIDE_ENTRY_BAND",)),
            ("conflicting-evidence", "no_bet", ("POLICY_INCOMPLETE_DATA",)),
        ],
    )
    def test_scenario_policy_outcome(
        self,
        repo: FixtureRepository,
        scenario_id: str,
        expected_decision: str,
        expected_reasons: tuple[str, ...],
    ) -> None:
        scenario = repo.load_scenario(scenario_id)
        assert len(scenario.candidates) == 1
        decision = evaluate_bundle(scenario, scenario.candidates[0])
        assert decision.decision == expected_decision
        assert decision.reason_codes == expected_reasons
        if scenario.expected_outcome_class == "policy_no_bet":
            assert decision.reason_codes == (scenario.expected_reason_code,)

    def test_clear_edge_check_details(self, repo: FixtureRepository) -> None:
        scenario = repo.load_scenario("clear-edge")
        decision = evaluate_bundle(scenario, scenario.candidates[0])
        assert all(check.passed for check in decision.checks)
        assert check_by_id(decision, CHECK_MIN_NET_EDGE).observed_value == 44_000

    def test_thin_edge_check_details(self, repo: FixtureRepository) -> None:
        scenario = repo.load_scenario("thin-edge")
        decision = evaluate_bundle(scenario, scenario.candidates[0])
        assert failed_check_ids(decision) == (CHECK_MIN_NET_EDGE,)
        net_edge = check_by_id(decision, CHECK_MIN_NET_EDGE)
        assert net_edge.observed_value == 1_520
        assert net_edge.threshold_value == 20_000

    def test_stale_data_check_details(self, repo: FixtureRepository) -> None:
        scenario = repo.load_scenario("stale-data")
        decision = evaluate_bundle(scenario, scenario.candidates[0])
        assert failed_check_ids(decision) == (CHECK_SNAPSHOT_FRESHNESS,)
        # Snapshot expired at 09:00Z, one hour before the 10:00Z clock.
        assert check_by_id(decision, CHECK_SNAPSHOT_FRESHNESS).observed_value == -3_600
        assert check_by_id(decision, CHECK_CANDIDATE_FRESHNESS).observed_value == 3_600
        assert check_by_id(decision, CHECK_MATCH_FRESHNESS).observed_value == 3_600

    def test_outside_entry_band_check_details(self, repo: FixtureRepository) -> None:
        scenario = repo.load_scenario("outside-entry-band")
        decision = evaluate_bundle(scenario, scenario.candidates[0])
        assert failed_check_ids(decision) == (CHECK_ENTRY_PRICE_MAX,)
        entry_max = check_by_id(decision, CHECK_ENTRY_PRICE_MAX)
        assert entry_max.observed_value == 950_000
        assert entry_max.threshold_value == 900_000
        # The 20_000 ppm threshold intentionally lets this case pass the
        # net-edge rule (20_500) so the band is the only failure.
        net_edge = check_by_id(decision, CHECK_MIN_NET_EDGE)
        assert net_edge.passed
        assert net_edge.observed_value == 20_500

    def test_conflicting_evidence_check_details(self, repo: FixtureRepository) -> None:
        scenario = repo.load_scenario("conflicting-evidence")
        # The recorded end-to-end outcome stays a selector abstention (agent
        # in the primary composition, deterministic stub in the test-only
        # composition, §5.10); policy evaluation here is the independent
        # defense-in-depth layer.
        assert scenario.expected_outcome_class == "agent_abstention"
        decision = evaluate_bundle(scenario, scenario.candidates[0])
        assert decision.decision == "no_bet"
        assert decision.reason_codes == ("POLICY_INCOMPLETE_DATA",)
        assert failed_check_ids(decision) == (CHECK_MATCH_COMPLETENESS,)

    def test_no_valid_candidates_defense_in_depth(
        self, repo: FixtureRepository
    ) -> None:
        scenario = repo.load_scenario("no-valid-candidates")
        # Normal orchestration abstains before the model runs; the recorded
        # outcome class is unchanged by this defense-in-depth evaluation.
        assert scenario.expected_outcome_class == "orchestrator_abstention"
        assert len(scenario.candidates) == 2
        for bundle in scenario.candidates:
            decision = evaluate_bundle(
                scenario, bundle, estimate=fabricate_estimate(scenario, bundle)
            )
            assert decision.decision == "no_bet"
            assert decision.reason_codes == ("POLICY_INCOMPLETE_DATA",)
            assert failed_check_ids(decision) == (CHECK_MATCH_COMPLETENESS,)

    def test_fixture_threshold_separates_shipped_cases(
        self, repo: FixtureRepository
    ) -> None:
        threshold = FIXTURE_POLICY_CONFIG.min_net_edge_ppm
        assert 1_520 < threshold  # thin-edge fails the net-edge rule
        assert threshold <= 20_500  # outside-entry-band passes it
        assert threshold <= 44_000  # clear-edge passes it
