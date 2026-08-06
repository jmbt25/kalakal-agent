"""Slice 5 tests: deterministic simulated Discord-draft generation (§6.2.9).

Covers exact integer formatting, mandatory content, expiry semantics,
cross-contract rejection, policy no-bet absence, stale refusal,
idempotence, and the shipped fixture scenarios through the real estimator,
edge calculator, and policy engine.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, NamedTuple

import pytest
from pydantic import ValidationError

from kalakal.domain import (
    CandidateEligibility,
    EdgeAssessment,
    MarketSelection,
    PolicyDecision,
    ProbabilityEstimate,
    SimulatedDiscordDraft,
    estimate_inputs_digest,
)
from kalakal.domain.primitives import SYNTHETIC_MARKET_LINK_PREFIX
from kalakal.draft import (
    FIXTURE_DRAFT_CONFIG,
    DraftGenerationError,
    DraftSkippedNoBet,
    DraftStaleAtGeneration,
    SimulatedDraftConfig,
    draft_identity_key,
    format_micro_as_cents,
    format_ppm_as_percent,
    format_ppm_as_signed_points,
    format_utc_timestamp,
    generate_simulated_draft,
)
from kalakal.edge.calculator import calculate_edge
from kalakal.estimator.demo import DemoEstimator
from kalakal.fixtures import FixtureRepository
from kalakal.policy import FIXTURE_POLICY_CONFIG, evaluate_policy
from tests.unit import factories as f
from tests.unit.fixture_helpers import consideration_from_bundle, shipped_version_dir

RUN_ID = "run-draft-1"

UTC = timezone.utc


class Chain(NamedTuple):
    """One consistent deterministic input chain for the draft generator."""

    consideration: CandidateEligibility
    selection: MarketSelection
    estimate: ProbabilityEstimate
    edge: EdgeAssessment
    policy: PolicyDecision


def build_chain(
    consideration: CandidateEligibility | None = None,
    *,
    evaluated_at: datetime | None = None,
) -> Chain:
    consideration = (
        consideration if consideration is not None else f.make_consideration()
    )
    estimate = f.make_estimate(
        consideration.match_context, consideration.evaluation_side
    )
    edge = calculate_edge(
        estimate=estimate,
        snapshot=consideration.market_snapshot,
        fee_rate_ppm=10_000,
        fee_model_version=f.FEE_MODEL_VERSION,
        computed_at=f.ts(2),
    )
    policy = evaluate_policy(
        candidate=consideration.market,
        match_context=consideration.match_context,
        snapshot=consideration.market_snapshot,
        edge=edge,
        evaluated_at=evaluated_at if evaluated_at is not None else f.ts(3),
        config=FIXTURE_POLICY_CONFIG,
        is_duplicate_run=False,
    )
    selection = MarketSelection(
        abstained=False,
        selected_market_id=consideration.market.market_id,
        selected_side=consideration.evaluation_side,
    )
    return Chain(consideration, selection, estimate, edge, policy)


def generate(chain: Chain, **over: Any) -> object:
    kwargs: dict[str, Any] = {
        "run_id": RUN_ID,
        "consideration": chain.consideration,
        "selection": chain.selection,
        "estimate": chain.estimate,
        "edge": chain.edge,
        "policy_decision": chain.policy,
        "generated_at": f.ts(4),
    }
    kwargs.update(over)
    return generate_simulated_draft(**kwargs)


def proceed_draft(chain: Chain | None = None, **over: Any) -> SimulatedDiscordDraft:
    result = generate(chain if chain is not None else build_chain(), **over)
    assert isinstance(result, SimulatedDiscordDraft)
    return result


def assert_no_floats(value: object) -> None:
    assert not isinstance(value, float)
    if isinstance(value, dict):
        for item in value.values():
            assert_no_floats(item)
    elif isinstance(value, list | tuple):
        for item in value:
            assert_no_floats(item)


class TestFormatMicroAsCents:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (600_000, "60.0000¢"),
            (0, "0.0000¢"),
            (1, "0.0001¢"),
            (10_000, "1.0000¢"),
            (999_999, "99.9999¢"),
            (1_000_000, "100.0000¢"),
        ],
    )
    def test_exact_rendering(self, value: int, expected: str) -> None:
        assert format_micro_as_cents(value) == expected

    @pytest.mark.parametrize("value", [-1, 1_000_001])
    def test_out_of_range_rejected(self, value: int) -> None:
        with pytest.raises(DraftGenerationError):
            format_micro_as_cents(value)

    @pytest.mark.parametrize("value", [600_000.0, True])
    def test_non_int_rejected(self, value: Any) -> None:
        with pytest.raises(DraftGenerationError):
            format_micro_as_cents(value)


class TestFormatPpmAsPercent:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (650_000, "65.0000%"),
            (0, "0.0000%"),
            (1, "0.0001%"),
            (555_000, "55.5000%"),
            (1_000_000, "100.0000%"),
        ],
    )
    def test_exact_rendering(self, value: int, expected: str) -> None:
        assert format_ppm_as_percent(value) == expected

    @pytest.mark.parametrize("value", [-1, 1_000_001])
    def test_out_of_range_rejected(self, value: int) -> None:
        with pytest.raises(DraftGenerationError):
            format_ppm_as_percent(value)

    @pytest.mark.parametrize("value", [650_000.0, False])
    def test_non_int_rejected(self, value: Any) -> None:
        with pytest.raises(DraftGenerationError):
            format_ppm_as_percent(value)


class TestFormatPpmAsSignedPoints:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (44_000, "+4.4000 percentage points"),
            (1_520, "+0.1520 percentage points"),
            (0, "+0.0000 percentage points"),
            (-1, "-0.0001 percentage points"),
            (-8_480, "-0.8480 percentage points"),
            (-1_999_999, "-199.9999 percentage points"),
        ],
    )
    def test_exact_rendering_with_retained_sign(
        self, value: int, expected: str
    ) -> None:
        assert format_ppm_as_signed_points(value) == expected

    @pytest.mark.parametrize("value", [2_000_001, -2_000_001])
    def test_out_of_range_rejected(self, value: int) -> None:
        with pytest.raises(DraftGenerationError):
            format_ppm_as_signed_points(value)

    @pytest.mark.parametrize("value", [44_000.0, True])
    def test_non_int_rejected(self, value: Any) -> None:
        with pytest.raises(DraftGenerationError):
            format_ppm_as_signed_points(value)


class TestFormatUtcTimestamp:
    def test_canonical_z_rendering(self) -> None:
        assert format_utc_timestamp(f.ts()) == "2026-08-05T12:00:00Z"

    def test_microseconds_preserved(self) -> None:
        value = datetime(2026, 8, 5, 12, 0, 0, 123456, tzinfo=UTC)
        assert format_utc_timestamp(value) == "2026-08-05T12:00:00.123456Z"

    def test_naive_timestamp_rejected(self) -> None:
        with pytest.raises(DraftGenerationError):
            format_utc_timestamp(datetime(2026, 8, 5, 12, 0, 0))

    def test_non_utc_offset_rejected(self) -> None:
        value = datetime(2026, 8, 5, 12, 0, 0, tzinfo=timezone(timedelta(hours=1)))
        with pytest.raises(DraftGenerationError):
            format_utc_timestamp(value)


class TestDraftConfig:
    def test_fixture_config_values(self) -> None:
        assert FIXTURE_DRAFT_CONFIG.renderer_version == "fixture-draft-1"
        assert FIXTURE_DRAFT_CONFIG.max_draft_lifetime_seconds == 1_800

    def test_config_is_immutable(self) -> None:
        with pytest.raises(ValidationError):
            FIXTURE_DRAFT_CONFIG.max_draft_lifetime_seconds = 60

    @pytest.mark.parametrize("seconds", [0, 86_401])
    def test_out_of_range_lifetime_rejected(self, seconds: int) -> None:
        with pytest.raises(ValidationError):
            SimulatedDraftConfig(
                renderer_version="test-draft-1",
                max_draft_lifetime_seconds=seconds,
                stale_regeneration_warning="Regenerate the simulation.",
            )


class TestProceedDraft:
    def test_complete_draft_contains_every_mandatory_fragment(self) -> None:
        draft = proceed_draft()
        text = draft.draft_text
        assert text.startswith("SIMULATION — DO NOT POST")
        assert f"Event: {f.EVENT_NAME}" in text
        assert "Side: yes — " in text
        assert f.YES_MEANS in text
        assert f.MARKET_LINK in text
        assert "Ask: 60.0000¢" in text
        assert "Estimate: 65.0000% (DEMO ESTIMATOR — NOT PREDICTIVE)" in text
        assert "Estimated net edge: +4.4000 percentage points" in text
        assert "#nfa" in text
        assert "Generated: 2026-08-05T12:04:00Z" in text
        assert "Expires: 2026-08-05T12:34:00Z" in text
        assert FIXTURE_DRAFT_CONFIG.stale_regeneration_warning in text

    def test_structured_fields_match_the_recorded_contracts(self) -> None:
        chain = build_chain()
        draft = proceed_draft(chain)
        assert draft.run_id == RUN_ID
        assert draft.market_id == chain.consideration.market.market_id
        assert draft.side == chain.selection.selected_side
        assert draft.is_simulation is True
        assert draft.renderer_version == FIXTURE_DRAFT_CONFIG.renderer_version
        assert draft.event_name == chain.consideration.market.event_name
        assert draft.side_meaning == chain.consideration.market.yes_means
        assert draft.market_link == chain.consideration.market.market_link
        assert (
            draft.ask_price_micro == chain.consideration.market_snapshot.ask_price_micro
        )
        assert draft.probability_ppm == chain.estimate.probability_ppm
        assert draft.net_edge_ppm == chain.edge.net_edge_ppm
        assert draft.generated_at == f.ts(4)
        assert draft.expires_at == f.ts(34)

    def test_structured_and_rendered_values_agree_exactly(self) -> None:
        draft = proceed_draft()
        text = draft.draft_text
        assert f"Event: {draft.event_name}" in text
        assert f"Side: {draft.side} — {draft.side_meaning}" in text
        assert f"Synthetic market link: {draft.market_link}" in text
        assert f"Ask: {format_micro_as_cents(draft.ask_price_micro)}" in text
        assert format_ppm_as_percent(draft.probability_ppm) in text
        assert format_ppm_as_signed_points(draft.net_edge_ppm) in text
        assert f"Generated: {format_utc_timestamp(draft.generated_at)}" in text
        assert f"Expires: {format_utc_timestamp(draft.expires_at)}" in text
        assert draft.stale_regeneration_warning in text

    def test_expiry_capped_by_configured_ttl(self) -> None:
        config = SimulatedDraftConfig(
            renderer_version="test-draft-1",
            max_draft_lifetime_seconds=60,
            stale_regeneration_warning="Regenerate the simulation after expiry.",
        )
        draft = proceed_draft(config=config)
        assert draft.expires_at == f.ts(5)

    def test_expiry_capped_by_snapshot_validity(self) -> None:
        config = SimulatedDraftConfig(
            renderer_version="test-draft-1",
            max_draft_lifetime_seconds=86_400,
            stale_regeneration_warning="Regenerate the simulation after expiry.",
        )
        draft = proceed_draft(config=config)
        assert (
            draft.expires_at == build_chain().consideration.market_snapshot.valid_until
        )

    def test_exact_expiry_boundary(self) -> None:
        chain = build_chain()
        valid_until = chain.consideration.market_snapshot.valid_until
        just_before = valid_until - timedelta(seconds=1)
        draft = proceed_draft(chain, generated_at=just_before)
        assert draft.expires_at == valid_until
        boundary = generate(chain, generated_at=valid_until)
        assert isinstance(boundary, DraftStaleAtGeneration)

    def test_only_synthetic_invalid_links(self) -> None:
        text = proceed_draft().draft_text
        index = text.find("http")
        assert index != -1
        while index != -1:
            assert text.startswith(SYNTHETIC_MARKET_LINK_PREFIX, index)
            index = text.find("http", index + 1)
        assert "jup.ag" not in text

    def test_no_action_capable_or_real_market_content(self) -> None:
        text = proceed_draft().draft_text.lower()
        for forbidden in (
            "jup.ag",
            "discord",
            "channel",
            "<#",
            "@",
            "wallet",
            "sign",
            "transaction",
            "bet now",
            "buy",
            "order",
        ):
            assert forbidden not in text
        # The only occurrence of "post" is the DO-NOT-POST label itself.
        assert text.count("post") == 1
        assert "do not post" in text

    def test_estimate_never_claims_to_be_predictive(self) -> None:
        draft = proceed_draft()
        assert draft.estimator_display_label == "DEMO ESTIMATOR — NOT PREDICTIVE"
        assert "NOT PREDICTIVE" in draft.draft_text
        assert "predict" not in draft.draft_text.lower().replace("not predictive", "")

    def test_deterministic_repeatability(self) -> None:
        chain = build_chain()
        first = proceed_draft(chain)
        second = proceed_draft(chain)
        assert first == second
        assert first.draft_text.encode("utf-8") == second.draft_text.encode("utf-8")

    def test_stable_identity_key(self) -> None:
        draft = proceed_draft()
        key = draft_identity_key(
            run_id=draft.run_id, market_id=draft.market_id, side=draft.side
        )
        assert key == (RUN_ID, f.MARKET_ID, "yes")
        assert key == draft_identity_key(
            run_id=draft.run_id, market_id=draft.market_id, side=draft.side
        )

    def test_changed_rendered_input_changes_the_draft(self) -> None:
        chain = build_chain()
        base = proceed_draft(chain)
        later = proceed_draft(chain, generated_at=f.ts(5))
        assert later != base
        assert later.draft_text != base.draft_text
        assert draft_identity_key(
            run_id=later.run_id, market_id=later.market_id, side=later.side
        ) == draft_identity_key(
            run_id=base.run_id, market_id=base.market_id, side=base.side
        )

    def test_inputs_not_mutated(self) -> None:
        chain = build_chain()
        before = tuple(part.model_dump() for part in chain)
        proceed_draft(chain)
        assert tuple(part.model_dump() for part in chain) == before

    def test_no_floats_anywhere_in_output(self) -> None:
        assert_no_floats(proceed_draft().model_dump())


class TestNoBetAndStale:
    def test_policy_no_bet_produces_no_draft(self) -> None:
        chain = build_chain(evaluated_at=f.ts(120))
        assert chain.policy.decision == "no_bet"
        result = generate(chain)
        assert isinstance(result, DraftSkippedNoBet)
        assert not isinstance(result, SimulatedDiscordDraft)
        assert result.reason == "policy_no_bet"
        assert result.run_id == RUN_ID
        assert result.market_id == f.MARKET_ID
        assert result.side == "yes"

    def test_stale_at_generation_refused_with_typed_result(self) -> None:
        chain = build_chain()
        result = generate(chain, generated_at=f.ts(61))
        assert isinstance(result, DraftStaleAtGeneration)
        assert result.reason == "snapshot_expired"
        assert (
            result.snapshot_valid_until
            == chain.consideration.market_snapshot.valid_until
        )
        assert result.generated_at == f.ts(61)
        assert (
            result.regeneration_warning
            == FIXTURE_DRAFT_CONFIG.stale_regeneration_warning
        )
        # The warning is renderer-configuration content, so the producing
        # renderer version is recorded on the stale result too.
        assert result.renderer_version == FIXTURE_DRAFT_CONFIG.renderer_version


class TestCrossContractRejection:
    def test_selection_for_a_different_market_rejected(self) -> None:
        chain = build_chain()
        selection = MarketSelection(
            abstained=False, selected_market_id="mkt-2", selected_side="yes"
        )
        with pytest.raises(DraftGenerationError, match="considered market"):
            generate(chain, selection=selection)

    def test_selection_side_mismatch_rejected(self) -> None:
        chain = build_chain()
        selection = MarketSelection(
            abstained=False, selected_market_id=f.MARKET_ID, selected_side="no"
        )
        with pytest.raises(DraftGenerationError, match="evaluation side"):
            generate(chain, selection=selection)

    def test_estimate_for_the_wrong_side_rejected(self) -> None:
        chain = build_chain()
        other = f.make_estimate(chain.consideration.match_context, "no")
        with pytest.raises(DraftGenerationError, match="market and side"):
            generate(chain, estimate=other)

    def test_edge_from_a_different_snapshot_rejected(self) -> None:
        chain = build_chain()
        other_snapshot = f.make_market_snapshot(
            ask_price_micro=610_000, bid_price_micro=600_000
        )
        other_edge = calculate_edge(
            estimate=chain.estimate,
            snapshot=other_snapshot,
            fee_rate_ppm=10_000,
            fee_model_version=f.FEE_MODEL_VERSION,
            computed_at=f.ts(2),
        )
        with pytest.raises(DraftGenerationError, match="ask price"):
            generate(chain, edge=other_edge)

    def test_foreign_estimator_basis_rejected(self) -> None:
        chain = build_chain()
        # Same market, side, and probability — only the recorded basis
        # values differ from the considered match context.
        other_match = f.make_match_context(yes_team_rating=650, yes_team_form=0)
        other_estimate = f.make_estimate(other_match)
        assert other_estimate.probability_ppm == chain.estimate.probability_ppm
        with pytest.raises(DraftGenerationError, match="estimate basis"):
            generate(chain, estimate=other_estimate)

    def test_foreign_basis_rejected_even_with_fully_recomputed_chain(self) -> None:
        # The critical adversarial case: the edge and the policy decision
        # are both recomputed from the foreign estimate, so every digest,
        # displayed number, and exact policy comparison is internally
        # consistent — only the basis-to-recorded-match binding can expose
        # the mismatch.
        chain = build_chain()
        foreign_match = f.make_match_context(yes_team_rating=650, yes_team_form=0)
        foreign_estimate = f.make_estimate(foreign_match)
        assert foreign_estimate.probability_ppm == chain.estimate.probability_ppm
        foreign_edge = calculate_edge(
            estimate=foreign_estimate,
            snapshot=chain.consideration.market_snapshot,
            fee_rate_ppm=10_000,
            fee_model_version=f.FEE_MODEL_VERSION,
            computed_at=f.ts(2),
        )
        foreign_policy = evaluate_policy(
            candidate=chain.consideration.market,
            match_context=chain.consideration.match_context,
            snapshot=chain.consideration.market_snapshot,
            edge=foreign_edge,
            evaluated_at=f.ts(3),
            config=FIXTURE_POLICY_CONFIG,
            is_duplicate_run=False,
        )
        with pytest.raises(DraftGenerationError, match="estimate basis"):
            generate(
                chain,
                estimate=foreign_estimate,
                edge=foreign_edge,
                policy_decision=foreign_policy,
            )

    def test_estimate_basis_for_a_different_match_rejected(self) -> None:
        chain = build_chain()
        # Identical basis values and probability, but the basis names a
        # different match identity.
        other_match = f.make_match_context(match_id="match-2")
        other_estimate = f.make_estimate(other_match)
        with pytest.raises(DraftGenerationError, match="considered match context"):
            generate(chain, estimate=other_estimate)

    def test_estimator_version_digest_mismatch_rejected(self) -> None:
        chain = build_chain()
        # Basis and probability equal the recorded evidence; only the
        # estimator version (and therefore the digest) differs, so the
        # edge-to-estimate digest binding must expose it.
        basis = chain.estimate.basis
        other_estimate = ProbabilityEstimate(
            **f.probability_estimate_kwargs(
                estimator_version="1.1.0",
                inputs_digest=estimate_inputs_digest(
                    estimator_id="demo",
                    estimator_version="1.1.0",
                    market_id=f.MARKET_ID,
                    side="yes",
                    basis=basis,
                ),
            )
        )
        with pytest.raises(DraftGenerationError, match="estimate digest"):
            generate(chain, estimate=other_estimate)

    def test_fee_model_version_mismatch_rejected(self) -> None:
        chain = build_chain()
        other_snapshot = f.make_market_snapshot(fee_model_version="synthetic-fee-2")
        other_edge = calculate_edge(
            estimate=chain.estimate,
            snapshot=other_snapshot,
            fee_rate_ppm=10_000,
            fee_model_version="synthetic-fee-2",
            computed_at=f.ts(2),
        )
        with pytest.raises(DraftGenerationError, match="fee-model version"):
            generate(chain, edge=other_edge)

    def test_policy_decision_from_a_different_chain_rejected(self) -> None:
        chain = build_chain()
        other_snapshot = f.make_market_snapshot(
            ask_price_micro=610_000, bid_price_micro=600_000
        )
        other_edge = calculate_edge(
            estimate=chain.estimate,
            snapshot=other_snapshot,
            fee_rate_ppm=10_000,
            fee_model_version=f.FEE_MODEL_VERSION,
            computed_at=f.ts(2),
        )
        other_policy = evaluate_policy(
            candidate=chain.consideration.market,
            match_context=chain.consideration.match_context,
            snapshot=other_snapshot,
            edge=other_edge,
            evaluated_at=f.ts(3),
            config=FIXTURE_POLICY_CONFIG,
            is_duplicate_run=False,
        )
        with pytest.raises(DraftGenerationError, match="recomputed"):
            generate(chain, policy_decision=other_policy)

    def test_factory_built_decision_with_different_checks_rejected(self) -> None:
        # A hand-built decision whose check series differs from the exact
        # recomputed engine result must never be narrated or rendered.
        chain = build_chain()
        with pytest.raises(DraftGenerationError, match="recomputed"):
            generate(chain, policy_decision=f.make_policy_decision("proceed"))

    def test_ineligible_consideration_rejected(self) -> None:
        chain = build_chain()
        with pytest.raises(DraftGenerationError, match="eligible"):
            generate(chain, consideration=f.make_ineligible_consideration())


class TestExactPolicyVerification:
    """Adversarial proof that supplied policy decisions are recomputed and
    compared exactly, never trusted by shape, digest, or displayed values."""

    def test_forged_well_shaped_inputs_digest_rejected(self) -> None:
        chain = build_chain()
        forged = f.rebuild_policy_decision(
            chain.policy, inputs_digest=f.sha_hex("forged-policy-digest")
        )
        with pytest.raises(DraftGenerationError, match="recomputed"):
            generate(chain, policy_decision=forged)

    def test_forged_policy_version_rejected(self) -> None:
        chain = build_chain()
        forged = f.rebuild_policy_decision(
            chain.policy, policy_version="forged-policy-9"
        )
        with pytest.raises(DraftGenerationError, match="recomputed"):
            generate(chain, policy_decision=forged)

    def test_forged_evaluation_time_rejected(self) -> None:
        chain = build_chain()
        forged = f.rebuild_policy_decision(chain.policy, evaluated_at=f.ts(5))
        with pytest.raises(DraftGenerationError, match="recomputed"):
            generate(chain, policy_decision=forged)

    def test_reordered_reason_codes_rejected(self) -> None:
        outside_band = f.make_consideration(
            market_snapshot=f.make_market_snapshot(
                ask_price_micro=950_000, bid_price_micro=940_000
            )
        )
        chain = build_chain(outside_band)
        assert len(chain.policy.reason_codes) == 2
        forged = f.rebuild_policy_decision(
            chain.policy, reason_codes=tuple(reversed(chain.policy.reason_codes))
        )
        with pytest.raises(DraftGenerationError, match="recomputed"):
            generate(chain, policy_decision=forged)

    def test_decision_from_other_policy_configuration_rejected(self) -> None:
        chain = build_chain()
        alt_config = f.alt_policy_config()
        alt_policy = evaluate_policy(
            candidate=chain.consideration.market,
            match_context=chain.consideration.match_context,
            snapshot=chain.consideration.market_snapshot,
            edge=chain.edge,
            evaluated_at=f.ts(3),
            config=alt_config,
            is_duplicate_run=False,
        )
        # Same outcome, same observations — only version, threshold, and
        # provenance differ from the fixture-configuration recomputation.
        assert alt_policy.decision == chain.policy.decision == "proceed"
        with pytest.raises(DraftGenerationError, match="recomputed"):
            generate(chain, policy_decision=alt_policy)

    def test_explicitly_supplied_policy_configuration_is_honored(self) -> None:
        chain = build_chain()
        alt_config = f.alt_policy_config()
        alt_policy = evaluate_policy(
            candidate=chain.consideration.market,
            match_context=chain.consideration.match_context,
            snapshot=chain.consideration.market_snapshot,
            edge=chain.edge,
            evaluated_at=f.ts(3),
            config=alt_config,
            is_duplicate_run=False,
        )
        result = generate(chain, policy_decision=alt_policy, policy_config=alt_config)
        assert isinstance(result, SimulatedDiscordDraft)

    def test_decision_for_a_different_duplicate_run_status_rejected(self) -> None:
        chain = build_chain()
        dup_policy = evaluate_policy(
            candidate=chain.consideration.market,
            match_context=chain.consideration.match_context,
            snapshot=chain.consideration.market_snapshot,
            edge=chain.edge,
            evaluated_at=f.ts(3),
            config=FIXTURE_POLICY_CONFIG,
            is_duplicate_run=True,
        )
        with pytest.raises(DraftGenerationError, match="recomputed"):
            generate(chain, policy_decision=dup_policy)

    def test_explicit_duplicate_run_status_yields_the_policy_no_bet(self) -> None:
        chain = build_chain()
        dup_policy = evaluate_policy(
            candidate=chain.consideration.market,
            match_context=chain.consideration.match_context,
            snapshot=chain.consideration.market_snapshot,
            edge=chain.edge,
            evaluated_at=f.ts(3),
            config=FIXTURE_POLICY_CONFIG,
            is_duplicate_run=True,
        )
        result = generate(chain, policy_decision=dup_policy, is_duplicate_run=True)
        assert isinstance(result, DraftSkippedNoBet)

    def test_decision_for_a_different_candidate_with_matching_observations(
        self,
    ) -> None:
        chain = build_chain()
        other_candidate = f.make_candidate_market(
            provenance=f.make_provenance(content_digest=f.sha_hex("other-candidate"))
        )
        other_policy = evaluate_policy(
            candidate=other_candidate,
            match_context=chain.consideration.match_context,
            snapshot=chain.consideration.market_snapshot,
            edge=chain.edge,
            evaluated_at=f.ts(3),
            config=FIXTURE_POLICY_CONFIG,
            is_duplicate_run=False,
        )
        # Every displayed observation matches; only the recomputed inputs
        # digest can expose the foreign candidate evidence.
        assert other_policy.checks == chain.policy.checks
        with pytest.raises(DraftGenerationError, match="recomputed"):
            generate(chain, policy_decision=other_policy)

    def test_decision_for_a_different_match_context_with_matching_observations(
        self,
    ) -> None:
        chain = build_chain()
        other_match = f.make_match_context(
            provenance=f.make_provenance(content_digest=f.sha_hex("other-match"))
        )
        other_policy = evaluate_policy(
            candidate=chain.consideration.market,
            match_context=other_match,
            snapshot=chain.consideration.market_snapshot,
            edge=chain.edge,
            evaluated_at=f.ts(3),
            config=FIXTURE_POLICY_CONFIG,
            is_duplicate_run=False,
        )
        assert other_policy.checks == chain.policy.checks
        with pytest.raises(DraftGenerationError, match="recomputed"):
            generate(chain, policy_decision=other_policy)

    def test_decision_for_a_different_snapshot_with_matching_observations(
        self,
    ) -> None:
        chain = build_chain()
        other_snapshot = f.make_market_snapshot(
            provenance=f.make_provenance(content_digest=f.sha_hex("other-snapshot"))
        )
        other_edge = calculate_edge(
            estimate=chain.estimate,
            snapshot=other_snapshot,
            fee_rate_ppm=10_000,
            fee_model_version=f.FEE_MODEL_VERSION,
            computed_at=f.ts(2),
        )
        other_policy = evaluate_policy(
            candidate=chain.consideration.market,
            match_context=chain.consideration.match_context,
            snapshot=other_snapshot,
            edge=other_edge,
            evaluated_at=f.ts(3),
            config=FIXTURE_POLICY_CONFIG,
            is_duplicate_run=False,
        )
        assert other_policy.checks == chain.policy.checks
        with pytest.raises(DraftGenerationError, match="recomputed"):
            generate(chain, policy_decision=other_policy)


class TestStageTimeOrdering:
    """Each stage-time inversion is rejected independently; a shared
    effective evaluation timestamp remains allowed (§7.7)."""

    def chain_with_times(
        self,
        *,
        estimate_at: datetime,
        edge_at: datetime,
        policy_at: datetime,
    ) -> Chain:
        consideration = f.make_consideration()
        estimate = DemoEstimator().estimate(
            consideration.match_context, "yes", computed_at=estimate_at
        )
        assert isinstance(estimate, ProbabilityEstimate)
        edge = calculate_edge(
            estimate=estimate,
            snapshot=consideration.market_snapshot,
            fee_rate_ppm=10_000,
            fee_model_version=f.FEE_MODEL_VERSION,
            computed_at=edge_at,
        )
        policy = evaluate_policy(
            candidate=consideration.market,
            match_context=consideration.match_context,
            snapshot=consideration.market_snapshot,
            edge=edge,
            evaluated_at=policy_at,
            config=FIXTURE_POLICY_CONFIG,
            is_duplicate_run=False,
        )
        selection = MarketSelection(
            abstained=False,
            selected_market_id=consideration.market.market_id,
            selected_side="yes",
        )
        return Chain(consideration, selection, estimate, edge, policy)

    def test_edge_computed_before_estimate_rejected(self) -> None:
        chain = self.chain_with_times(
            estimate_at=f.ts(3), edge_at=f.ts(2), policy_at=f.ts(3)
        )
        with pytest.raises(DraftGenerationError, match="computed before"):
            generate(chain)

    def test_policy_evaluated_before_edge_rejected(self) -> None:
        chain = self.chain_with_times(
            estimate_at=f.ts(1), edge_at=f.ts(5), policy_at=f.ts(3)
        )
        with pytest.raises(DraftGenerationError, match="evaluated before"):
            generate(chain)

    def test_generation_before_policy_evaluation_rejected(self) -> None:
        chain = build_chain()
        with pytest.raises(DraftGenerationError, match="precede the policy"):
            generate(chain, generated_at=f.ts(2))

    def test_shared_effective_evaluation_timestamp_allowed(self) -> None:
        chain = self.chain_with_times(
            estimate_at=f.ts(3), edge_at=f.ts(3), policy_at=f.ts(3)
        )
        result = generate(chain, generated_at=f.ts(3))
        assert isinstance(result, SimulatedDiscordDraft)


class TestRendererVersion:
    def test_renderer_version_only_change_visible_in_structured_output(
        self,
    ) -> None:
        chain = build_chain()
        base = proceed_draft(chain)
        rebranded = SimulatedDraftConfig(
            renderer_version="fixture-draft-2",
            max_draft_lifetime_seconds=(
                FIXTURE_DRAFT_CONFIG.max_draft_lifetime_seconds
            ),
            stale_regeneration_warning=(
                FIXTURE_DRAFT_CONFIG.stale_regeneration_warning
            ),
        )
        changed = proceed_draft(chain, config=rebranded)
        assert base.renderer_version == "fixture-draft-1"
        assert changed.renderer_version == "fixture-draft-2"
        # The rendered text may be unchanged, but the structured draft and
        # its serialized audit form must differ.
        assert changed.draft_text == base.draft_text
        assert changed != base
        assert base.model_dump_json() != changed.model_dump_json()
        serialized = json.loads(changed.model_dump_json())
        assert serialized["renderer_version"] == "fixture-draft-2"

    def test_stale_result_records_the_configured_renderer_version(self) -> None:
        chain = build_chain()
        custom = SimulatedDraftConfig(
            renderer_version="fixture-draft-2",
            max_draft_lifetime_seconds=1_800,
            stale_regeneration_warning="Regenerate the simulation after expiry.",
        )
        result = generate(chain, generated_at=f.ts(61), config=custom)
        assert isinstance(result, DraftStaleAtGeneration)
        assert result.renderer_version == "fixture-draft-2"
        assert result.regeneration_warning == custom.stale_regeneration_warning


@pytest.fixture(scope="module")
def repo() -> FixtureRepository:
    return FixtureRepository(shipped_version_dir())


def run_shipped_scenario(repo: FixtureRepository, scenario_id: str) -> object:
    """Run one shipped scenario through the real estimator, edge
    calculator, and policy engine, then attempt draft generation."""
    scenario = repo.load_scenario(scenario_id)
    bundle = scenario.candidates[0]
    consideration = consideration_from_bundle(bundle)
    assert consideration.eligible
    estimate = DemoEstimator().estimate(
        bundle.match_context,
        bundle.evaluation_side,
        computed_at=scenario.evaluation_time,
    )
    assert isinstance(estimate, ProbabilityEstimate)
    edge = calculate_edge(
        estimate=estimate,
        snapshot=bundle.market_snapshot,
        fee_rate_ppm=scenario.fee_rate_ppm,
        fee_model_version=scenario.fee_model_version,
        computed_at=scenario.evaluation_time,
    )
    policy = evaluate_policy(
        candidate=bundle.candidate_market,
        match_context=bundle.match_context,
        snapshot=bundle.market_snapshot,
        edge=edge,
        evaluated_at=scenario.evaluation_time,
        config=FIXTURE_POLICY_CONFIG,
        is_duplicate_run=False,
    )
    selection = MarketSelection(
        abstained=False,
        selected_market_id=bundle.candidate_market.market_id,
        selected_side=bundle.evaluation_side,
    )
    return generate_simulated_draft(
        run_id="run-shipped-1",
        consideration=consideration,
        selection=selection,
        estimate=estimate,
        edge=edge,
        policy_decision=policy,
        generated_at=scenario.evaluation_time,
    )


class TestShippedScenarios:
    def test_clear_edge_produces_the_canonical_proceed_draft(
        self, repo: FixtureRepository
    ) -> None:
        result = run_shipped_scenario(repo, "clear-edge")
        assert isinstance(result, SimulatedDiscordDraft)
        text = result.draft_text
        assert text.startswith("SIMULATION — DO NOT POST")
        assert "Event: Synthetica Masters 2026 - Grand Final" in text
        assert "Cerulean Wyverns win the series" in text
        assert "https://markets.kalakal.invalid/syn-mkt-clear-edge-01" in text
        assert "Ask: 60.0000¢" in text
        assert "Estimate: 65.0000% (DEMO ESTIMATOR — NOT PREDICTIVE)" in text
        assert "Estimated net edge: +4.4000 percentage points" in text
        assert "#nfa" in text
        assert "Generated: 2026-08-06T10:00:00Z" in text
        assert "Expires: 2026-08-06T10:30:00Z" in text
        assert result.expires_at == datetime(2026, 8, 6, 10, 30, tzinfo=UTC)

    @pytest.mark.parametrize(
        "scenario_id", ["thin-edge", "stale-data", "outside-entry-band"]
    )
    def test_policy_no_bet_scenarios_produce_no_draft(
        self, repo: FixtureRepository, scenario_id: str
    ) -> None:
        result = run_shipped_scenario(repo, scenario_id)
        assert isinstance(result, DraftSkippedNoBet)
        assert result.reason == "policy_no_bet"
