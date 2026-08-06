"""Unit tests for the three DecisionRecord terminal shapes (§6.2.10)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kalakal.domain import (
    SYNTHETIC_MARKET_LINK_PREFIX,
    Abstention,
    CandidateEligibility,
    CompletedProceedRecord,
    EvidenceRef,
    MarketSelection,
    PolicyNoBetRecord,
    PreSelectionAbstentionRecord,
    StateTransition,
    validate_decision_record,
)
from tests.unit import factories as f


class TestValidTerminalShapes:
    def test_shape_a_agent_variant(self) -> None:
        record = PreSelectionAbstentionRecord(**f.record_a_agent_kwargs())
        assert record.outcome == "abstained"
        assert record.abstention_source == "agent"
        assert record.model_invocation.invocation_status == "invoked"

    def test_shape_a_orchestrator_variant(self) -> None:
        record = PreSelectionAbstentionRecord(**f.record_a_orch_kwargs())
        assert record.abstention_source == "orchestrator"
        assert record.model_invocation.invocation_status == "not_invoked"
        assert record.selection.abstain_reason_code == "NO_VALID_CANDIDATES"
        assert record.explanation.explanation_template_version == "template-1"

    def test_shape_a_deterministic_stub_variant(self) -> None:
        record = PreSelectionAbstentionRecord(**f.record_a_stub_kwargs())
        assert record.abstention_source == "deterministic_stub"
        assert record.model_invocation.invocation_status == "not_invoked"
        assert record.selection.abstain_reason_code == "CONFLICTING_EVIDENCE"
        assert any(c.eligible for c in record.candidates_considered)
        assert record.explanation.source == "orchestrator"
        assert record.explanation.explanation_template_version == "template-1"
        assert record.deterministic_selector is not None
        assert record.deterministic_selector.test_only is True

    def test_shape_b_policy_no_bet(self) -> None:
        record = PolicyNoBetRecord(**f.record_b_kwargs())
        assert record.outcome == "abstained"
        assert record.selection_source == "agent"
        assert record.policy_decision.decision == "no_bet"

    def test_shape_b_deterministic_stub_variant(self) -> None:
        record = PolicyNoBetRecord(**f.record_b_stub_kwargs())
        assert record.selection_source == "deterministic_stub"
        assert record.model_invocation.invocation_status == "not_invoked"
        assert record.explanation.source == "orchestrator"
        assert record.explanation.explanation_template_version == "template-1"
        assert record.deterministic_selector is not None

    def test_shape_c_completed_proceed(self) -> None:
        record = CompletedProceedRecord(**f.record_c_kwargs())
        assert record.outcome == "completed"
        assert record.selection_source == "agent"
        assert record.draft.is_simulation is True

    def test_shape_c_deterministic_stub_variant(self) -> None:
        record = CompletedProceedRecord(**f.record_c_stub_kwargs())
        assert record.selection_source == "deterministic_stub"
        assert record.model_invocation.invocation_status == "not_invoked"
        assert record.explanation.source == "orchestrator"
        assert record.deterministic_selector is not None
        assert record.draft.is_simulation is True

    @pytest.mark.parametrize(
        "kwargs_fn",
        [
            f.record_a_agent_kwargs,
            f.record_a_orch_kwargs,
            f.record_a_stub_kwargs,
            f.record_b_kwargs,
            f.record_b_stub_kwargs,
            f.record_c_kwargs,
            f.record_c_stub_kwargs,
        ],
        ids=["a-agent", "a-orch", "a-stub", "b", "b-stub", "c", "c-stub"],
    )
    def test_union_entry_point_accepts_each_shape(self, kwargs_fn: object) -> None:
        record = validate_decision_record(kwargs_fn())  # type: ignore[operator]
        assert record.run_id == f.RUN_ID

    @pytest.mark.parametrize(
        "kwargs_fn",
        [f.record_c_kwargs, f.record_c_stub_kwargs],
        ids=["agent", "stub"],
    )
    def test_json_round_trip_is_bit_stable(self, kwargs_fn: object) -> None:
        record = CompletedProceedRecord(**kwargs_fn())  # type: ignore[operator]
        dumped = record.model_dump_json()
        assert CompletedProceedRecord.model_validate_json(dumped) == record
        assert (
            CompletedProceedRecord.model_validate_json(dumped).model_dump_json()
            == dumped
        )


class TestShapeAInvariants:
    def test_agent_variant_with_not_invoked_rejected(self) -> None:
        with pytest.raises(ValidationError, match="requires invocation_status"):
            PreSelectionAbstentionRecord(
                **f.record_a_agent_kwargs(model_invocation=f.make_not_invoked())
            )

    def test_agent_variant_without_model_metadata_rejected(self) -> None:
        kwargs = f.invoked_kwargs()
        del kwargs["model_id"]
        with pytest.raises(ValidationError):
            PreSelectionAbstentionRecord(
                **f.record_a_agent_kwargs(model_invocation=kwargs)
            )

    def test_agent_variant_with_orchestrator_explanation_rejected(self) -> None:
        with pytest.raises(ValidationError, match="agent-sourced explanation"):
            PreSelectionAbstentionRecord(
                **f.record_a_agent_kwargs(
                    explanation=f.make_explanation("orchestrator")
                )
            )

    def test_agent_variant_with_no_valid_candidates_reason_rejected(self) -> None:
        with pytest.raises(ValidationError, match="reserved for the orchestrator"):
            PreSelectionAbstentionRecord(
                **f.record_a_agent_kwargs(
                    selection=Abstention(
                        abstained=True,
                        abstain_reason_code="NO_VALID_CANDIDATES",
                    )
                )
            )

    def test_agent_variant_without_eligible_candidates_rejected(self) -> None:
        with pytest.raises(ValidationError, match="eligible candidate"):
            PreSelectionAbstentionRecord(
                **f.record_a_agent_kwargs(
                    candidates_considered=(
                        CandidateEligibility(
                            market=f.make_candidate_market(),
                            eligible=False,
                            ineligibility_reasons=("ESTIMATOR_INPUT_MISSING",),
                        ),
                    )
                )
            )

    def test_orchestrator_variant_with_invoked_metadata_rejected(self) -> None:
        with pytest.raises(ValidationError, match="not_invoked"):
            PreSelectionAbstentionRecord(
                **f.record_a_orch_kwargs(model_invocation=f.make_invoked())
            )

    @pytest.mark.parametrize(
        "extra",
        [
            {"model_id": "gemini-3.6-flash"},
            {"prompt_version": "prompt-1"},
            {"response_ids": ("resp-1",)},
            {"usage": ()},
            {"tool_calls": ()},
        ],
    )
    def test_orchestrator_variant_with_model_fields_rejected(
        self, extra: dict[str, object]
    ) -> None:
        payload = {"invocation_status": "not_invoked", **extra}
        with pytest.raises(ValidationError):
            PreSelectionAbstentionRecord(
                **f.record_a_orch_kwargs(model_invocation=payload)
            )

    def test_orchestrator_variant_with_agent_explanation_rejected(self) -> None:
        with pytest.raises(ValidationError, match="orchestrator-sourced"):
            PreSelectionAbstentionRecord(
                **f.record_a_orch_kwargs(explanation=f.make_explanation("agent"))
            )

    @pytest.mark.parametrize(
        "reason",
        ["CONFLICTING_EVIDENCE", "INSUFFICIENT_EVIDENCE", "NO_ATTRACTIVE_CANDIDATE"],
    )
    def test_orchestrator_variant_with_other_reason_rejected(self, reason: str) -> None:
        with pytest.raises(ValidationError, match="NO_VALID_CANDIDATES"):
            PreSelectionAbstentionRecord(
                **f.record_a_orch_kwargs(
                    selection=Abstention(
                        abstained=True,
                        abstain_reason_code=reason,  # type: ignore[arg-type]
                    )
                )
            )

    def test_orchestrator_variant_with_eligible_candidate_rejected(self) -> None:
        with pytest.raises(ValidationError, match="zero eligible"):
            PreSelectionAbstentionRecord(
                **f.record_a_orch_kwargs(
                    candidates_considered=(
                        CandidateEligibility(
                            market=f.make_candidate_market(),
                            eligible=True,
                            ineligibility_reasons=(),
                        ),
                    )
                )
            )

    def test_selection_output_naming_market_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PreSelectionAbstentionRecord(
                **f.record_a_agent_kwargs(
                    selection=MarketSelection(
                        abstained=False,
                        selected_market_id=f.MARKET_ID,
                        selected_side="yes",
                    )
                )
            )

    @pytest.mark.parametrize(
        "artifact_field",
        [
            "match_context",
            "market_snapshot",
            "probability_estimate",
            "edge_assessment",
            "policy_decision",
            "draft",
        ],
    )
    @pytest.mark.parametrize(
        "base_kwargs_fn",
        [f.record_a_agent_kwargs, f.record_a_orch_kwargs, f.record_a_stub_kwargs],
        ids=["agent", "orchestrator", "stub"],
    )
    def test_post_selection_artifacts_absent_on_shape_a(
        self, artifact_field: str, base_kwargs_fn: object
    ) -> None:
        artifacts: dict[str, object] = {
            "match_context": f.make_match_context(),
            "market_snapshot": f.make_market_snapshot(),
            "probability_estimate": f.make_estimate(),
            "edge_assessment": f.make_edge_assessment(),
            "policy_decision": f.make_policy_decision("no_bet"),
            "draft": f.make_draft(),
        }
        kwargs = base_kwargs_fn()  # type: ignore[operator]
        kwargs[artifact_field] = artifacts[artifact_field]
        with pytest.raises(ValidationError):
            PreSelectionAbstentionRecord(**kwargs)


class TestDeterministicStubSourceInvariants:
    """Source/metadata truth table for the deterministic-stub variants."""

    @pytest.mark.parametrize(
        ("record_cls", "kwargs_fn"),
        [
            (PreSelectionAbstentionRecord, f.record_a_stub_kwargs),
            (PolicyNoBetRecord, f.record_b_stub_kwargs),
            (CompletedProceedRecord, f.record_c_stub_kwargs),
        ],
        ids=["a-stub", "b-stub", "c-stub"],
    )
    def test_stub_without_selector_metadata_rejected(
        self, record_cls: type, kwargs_fn: object
    ) -> None:
        kwargs = kwargs_fn()  # type: ignore[operator]
        kwargs["deterministic_selector"] = None
        with pytest.raises(ValidationError, match="deterministic-selector metadata"):
            record_cls(**kwargs)

    @pytest.mark.parametrize(
        ("record_cls", "kwargs_fn"),
        [
            (PreSelectionAbstentionRecord, f.record_a_agent_kwargs),
            (PolicyNoBetRecord, f.record_b_kwargs),
            (CompletedProceedRecord, f.record_c_kwargs),
        ],
        ids=["a-agent", "b-agent", "c-agent"],
    )
    def test_agent_source_with_selector_metadata_rejected(
        self, record_cls: type, kwargs_fn: object
    ) -> None:
        kwargs = kwargs_fn()  # type: ignore[operator]
        kwargs["deterministic_selector"] = f.make_selector_metadata()
        with pytest.raises(
            ValidationError, match="must not carry deterministic-selector"
        ):
            record_cls(**kwargs)

    def test_orchestrator_variant_with_selector_metadata_rejected(self) -> None:
        with pytest.raises(
            ValidationError, match="must not carry\\s+deterministic-selector"
        ):
            PreSelectionAbstentionRecord(
                **f.record_a_orch_kwargs(
                    deterministic_selector=f.make_selector_metadata()
                )
            )

    @pytest.mark.parametrize(
        ("record_cls", "kwargs_fn"),
        [
            (PreSelectionAbstentionRecord, f.record_a_stub_kwargs),
            (PolicyNoBetRecord, f.record_b_stub_kwargs),
            (CompletedProceedRecord, f.record_c_stub_kwargs),
        ],
        ids=["a-stub", "b-stub", "c-stub"],
    )
    def test_stub_with_invoked_metadata_rejected(
        self, record_cls: type, kwargs_fn: object
    ) -> None:
        kwargs = kwargs_fn()  # type: ignore[operator]
        kwargs["model_invocation"] = f.make_invoked()
        with pytest.raises(ValidationError, match="not_invoked"):
            record_cls(**kwargs)

    @pytest.mark.parametrize(
        ("record_cls", "kwargs_fn"),
        [
            (PreSelectionAbstentionRecord, f.record_a_stub_kwargs),
            (PolicyNoBetRecord, f.record_b_stub_kwargs),
            (CompletedProceedRecord, f.record_c_stub_kwargs),
        ],
        ids=["a-stub", "b-stub", "c-stub"],
    )
    @pytest.mark.parametrize(
        "extra",
        [
            {"model_id": "gemini-3.6-flash"},
            {"prompt_version": "prompt-1"},
            {"response_ids": ("resp-1",)},
            {"usage": ()},
            {"fallback_used": False},
            {"tool_calls": ()},
        ],
    )
    def test_stub_cannot_fabricate_model_metadata(
        self, record_cls: type, kwargs_fn: object, extra: dict[str, object]
    ) -> None:
        kwargs = kwargs_fn()  # type: ignore[operator]
        kwargs["model_invocation"] = {"invocation_status": "not_invoked", **extra}
        with pytest.raises(ValidationError):
            record_cls(**kwargs)

    @pytest.mark.parametrize(
        ("record_cls", "kwargs_fn"),
        [
            (PreSelectionAbstentionRecord, f.record_a_stub_kwargs),
            (PolicyNoBetRecord, f.record_b_stub_kwargs),
            (CompletedProceedRecord, f.record_c_stub_kwargs),
        ],
        ids=["a-stub", "b-stub", "c-stub"],
    )
    def test_stub_with_agent_explanation_rejected(
        self, record_cls: type, kwargs_fn: object
    ) -> None:
        kwargs = kwargs_fn()  # type: ignore[operator]
        kwargs["explanation"] = f.make_explanation("agent")
        with pytest.raises(ValidationError, match="orchestrator-sourced"):
            record_cls(**kwargs)

    def test_stub_abstention_with_no_valid_candidates_reason_rejected(self) -> None:
        with pytest.raises(ValidationError, match="reserved for the orchestrator"):
            PreSelectionAbstentionRecord(
                **f.record_a_stub_kwargs(
                    selection=Abstention(
                        abstained=True,
                        abstain_reason_code="NO_VALID_CANDIDATES",
                    )
                )
            )

    def test_stub_abstention_without_eligible_candidates_rejected(self) -> None:
        with pytest.raises(ValidationError, match="eligible candidate"):
            PreSelectionAbstentionRecord(
                **f.record_a_stub_kwargs(
                    candidates_considered=(
                        CandidateEligibility(
                            market=f.make_candidate_market(),
                            eligible=False,
                            ineligibility_reasons=("ESTIMATOR_INPUT_MISSING",),
                        ),
                    )
                )
            )

    def test_unknown_selection_source_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PolicyNoBetRecord(**f.record_b_kwargs(selection_source="model"))

    def test_selection_source_is_required(self) -> None:
        kwargs = f.record_b_kwargs()
        del kwargs["selection_source"]
        with pytest.raises(ValidationError):
            PolicyNoBetRecord(**kwargs)


class TestShapeBCInvariants:
    def test_draft_on_no_bet_record_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PolicyNoBetRecord(**f.record_b_kwargs(draft=f.make_draft()))

    def test_no_bet_record_with_proceed_decision_rejected(self) -> None:
        with pytest.raises(ValidationError, match="requires decision 'no_bet'"):
            PolicyNoBetRecord(
                **f.record_b_kwargs(policy_decision=f.make_policy_decision("proceed"))
            )

    def test_completed_without_draft_rejected(self) -> None:
        kwargs = f.record_c_kwargs()
        del kwargs["draft"]
        with pytest.raises(ValidationError):
            CompletedProceedRecord(**kwargs)

    def test_completed_with_no_bet_decision_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CompletedProceedRecord(
                **f.record_c_kwargs(policy_decision=f.make_policy_decision("no_bet"))
            )

    @pytest.mark.parametrize(
        "field",
        [
            "match_context",
            "market_snapshot",
            "probability_estimate",
            "edge_assessment",
            "policy_decision",
            "selection",
            "model_invocation",
        ],
    )
    def test_post_selection_fields_required_on_shape_b(self, field: str) -> None:
        kwargs = f.record_b_kwargs()
        del kwargs[field]
        with pytest.raises(ValidationError):
            PolicyNoBetRecord(**kwargs)

    @pytest.mark.parametrize(
        ("record_cls", "kwargs_fn"),
        [
            (PolicyNoBetRecord, f.record_b_kwargs),
            (CompletedProceedRecord, f.record_c_kwargs),
        ],
        ids=["b", "c"],
    )
    def test_not_invoked_rejected_on_shapes_b_and_c(
        self, record_cls: type, kwargs_fn: object
    ) -> None:
        kwargs = kwargs_fn()  # type: ignore[operator]
        kwargs["model_invocation"] = f.make_not_invoked()
        with pytest.raises(ValidationError):
            record_cls(**kwargs)

    @pytest.mark.parametrize(
        ("record_cls", "kwargs_fn"),
        [
            (PolicyNoBetRecord, f.record_b_kwargs),
            (CompletedProceedRecord, f.record_c_kwargs),
        ],
        ids=["b", "c"],
    )
    def test_orchestrator_explanation_rejected_on_shapes_b_and_c(
        self, record_cls: type, kwargs_fn: object
    ) -> None:
        kwargs = kwargs_fn()  # type: ignore[operator]
        kwargs["explanation"] = f.make_explanation("orchestrator")
        with pytest.raises(ValidationError, match="agent-sourced explanation"):
            record_cls(**kwargs)

    def test_selected_market_not_in_candidates_rejected(self) -> None:
        with pytest.raises(ValidationError, match="not among candidates"):
            PolicyNoBetRecord(
                **f.record_b_kwargs(
                    selection=MarketSelection(
                        abstained=False,
                        selected_market_id="mkt-unknown",
                        selected_side="yes",
                    )
                )
            )

    def test_selected_market_ineligible_rejected(self) -> None:
        with pytest.raises(ValidationError, match="not an eligible candidate"):
            PolicyNoBetRecord(
                **f.record_b_kwargs(
                    candidates_considered=(
                        CandidateEligibility(
                            market=f.make_candidate_market(),
                            eligible=False,
                            ineligibility_reasons=("ESTIMATOR_INPUT_MISSING",),
                        ),
                    )
                )
            )

    def test_snapshot_side_mismatch_rejected(self) -> None:
        estimate = f.make_estimate(side="no")
        snapshot = f.make_market_snapshot(side="no")
        edge = f.make_edge_assessment(estimate, snapshot)
        with pytest.raises(ValidationError, match="selected side"):
            PolicyNoBetRecord(
                **f.record_b_kwargs(
                    market_snapshot=snapshot,
                    probability_estimate=estimate,
                    edge_assessment=edge,
                )
            )

    def test_match_context_market_mismatch_rejected(self) -> None:
        other_market = f.make_candidate_market(
            market_id="mkt-2",
            market_link=SYNTHETIC_MARKET_LINK_PREFIX + "mkt-2",
        )
        candidates = (
            CandidateEligibility(
                market=f.make_candidate_market(),
                eligible=True,
                ineligibility_reasons=(),
            ),
            CandidateEligibility(
                market=other_market, eligible=True, ineligibility_reasons=()
            ),
        )
        with pytest.raises(ValidationError, match="match_context.market_id"):
            PolicyNoBetRecord(
                **f.record_b_kwargs(
                    candidates_considered=candidates,
                    selection=MarketSelection(
                        abstained=False,
                        selected_market_id="mkt-2",
                        selected_side="yes",
                    ),
                )
            )

    def test_edge_probability_mismatch_rejected(self) -> None:
        estimate = f.make_estimate(side="no")
        with pytest.raises(ValidationError):
            PolicyNoBetRecord(**f.record_b_kwargs(probability_estimate=estimate))

    def test_edge_ask_mismatch_rejected(self) -> None:
        snapshot = f.make_market_snapshot(ask_price_micro=610_000)
        with pytest.raises(ValidationError):
            PolicyNoBetRecord(**f.record_b_kwargs(market_snapshot=snapshot))

    def test_basis_mismatch_with_match_context_rejected(self) -> None:
        tampered_match = f.make_match_context(yes_team_form=51)
        with pytest.raises(ValidationError, match="estimate basis"):
            PolicyNoBetRecord(**f.record_b_kwargs(match_context=tampered_match))

    def test_side_inverted_match_context_rejected(self) -> None:
        # A context whose side-named inputs were swapped cannot pair with an
        # estimate recorded from the correct mapping.
        inverted = f.make_match_context(
            yes_team_rating=f.NO_TEAM_RATING,
            yes_team_form=f.NO_TEAM_FORM,
            no_team_rating=f.YES_TEAM_RATING,
            no_team_form=f.YES_TEAM_FORM,
        )
        with pytest.raises(ValidationError, match="estimate basis"):
            PolicyNoBetRecord(**f.record_b_kwargs(match_context=inverted))


def _draft_with_fragment(field: str, value: str) -> object:
    """Build a draft whose text stays internally consistent with ``value``."""
    kwargs = f.draft_kwargs()
    kwargs["draft_text"] = str(kwargs["draft_text"]).replace(str(kwargs[field]), value)
    kwargs[field] = value
    from kalakal.domain import SimulatedDiscordDraft

    return SimulatedDiscordDraft(**kwargs)


class TestDraftConsistencyOnShapeC:
    @pytest.mark.parametrize(
        ("override", "message"),
        [
            ({"run_id": "run-2"}, "draft.run_id"),
            ({"probability_ppm": 650_001}, "draft probability"),
            ({"net_edge_ppm": 44_001}, "draft net edge"),
            ({"ask_price_micro": 610_000}, "draft ask price"),
        ],
    )
    def test_draft_value_mismatches_rejected(
        self, override: dict[str, object], message: str
    ) -> None:
        with pytest.raises(ValidationError, match=message):
            CompletedProceedRecord(**f.record_c_kwargs(draft=f.make_draft(**override)))

    @pytest.mark.parametrize(
        ("field", "value", "message"),
        [
            ("event_name", "Other Synthetic Cup", "draft event_name"),
            ("side_meaning", "SYN-B wins the series", "side_meaning"),
            (
                "market_link",
                SYNTHETIC_MARKET_LINK_PREFIX + "mkt-2",
                "draft market_link",
            ),
        ],
    )
    def test_draft_fragment_mismatches_rejected(
        self, field: str, value: str, message: str
    ) -> None:
        draft = _draft_with_fragment(field, value)
        with pytest.raises(ValidationError, match=message):
            CompletedProceedRecord(**f.record_c_kwargs(draft=draft))

    def test_draft_side_mismatch_rejected(self) -> None:
        draft = f.make_draft(side="no")
        with pytest.raises(ValidationError, match="draft.side"):
            CompletedProceedRecord(**f.record_c_kwargs(draft=draft))


class TestCommonRecordInvariants:
    def test_request_run_id_mismatch_rejected(self) -> None:
        with pytest.raises(ValidationError, match="request.run_id"):
            PreSelectionAbstentionRecord(
                **f.record_a_agent_kwargs(request=f.make_run_request(run_id="run-2"))
            )

    def test_explanation_run_id_mismatch_rejected(self) -> None:
        with pytest.raises(ValidationError, match="explanation.run_id"):
            PreSelectionAbstentionRecord(
                **f.record_a_agent_kwargs(
                    explanation=f.make_explanation("agent", run_id="run-2")
                )
            )

    def test_explanation_metadata_ref_mismatch_rejected(self) -> None:
        with pytest.raises(ValidationError, match="model_metadata_ref"):
            PreSelectionAbstentionRecord(
                **f.record_a_agent_kwargs(
                    explanation=f.make_explanation(
                        "agent", model_metadata_ref="invocation-2"
                    )
                )
            )

    def test_explanation_prompt_version_mismatch_rejected(self) -> None:
        with pytest.raises(ValidationError, match="prompt_version"):
            PreSelectionAbstentionRecord(
                **f.record_a_agent_kwargs(
                    explanation=f.make_explanation("agent", prompt_version="prompt-9")
                )
            )

    def test_duplicate_candidate_market_ids_rejected(self) -> None:
        duplicate = CandidateEligibility(
            market=f.make_candidate_market(),
            eligible=True,
            ineligibility_reasons=(),
        )
        with pytest.raises(ValidationError, match="unique market_ids"):
            PreSelectionAbstentionRecord(
                **f.record_a_agent_kwargs(candidates_considered=(duplicate, duplicate))
            )

    def test_candidate_fixture_set_mismatch_rejected(self) -> None:
        foreign = f.make_candidate_market(
            provenance=f.make_provenance(fixture_set_id="fixture-set-9")
        )
        with pytest.raises(ValidationError, match="different fixture set"):
            PreSelectionAbstentionRecord(
                **f.record_a_agent_kwargs(
                    candidates_considered=(
                        CandidateEligibility(
                            market=foreign, eligible=True, ineligibility_reasons=()
                        ),
                    )
                )
            )

    def test_unresolvable_evidence_ref_rejected(self) -> None:
        with pytest.raises(ValidationError, match="does not resolve"):
            PreSelectionAbstentionRecord(
                **f.record_a_agent_kwargs(
                    explanation=f.make_explanation(
                        "agent",
                        evidence_refs=(
                            EvidenceRef(kind="market", ref_id="mkt-unknown"),
                        ),
                    )
                )
            )

    def test_match_kind_ref_unresolvable_on_shape_a(self) -> None:
        with pytest.raises(ValidationError, match="does not resolve"):
            PreSelectionAbstentionRecord(
                **f.record_a_agent_kwargs(
                    explanation=f.make_explanation(
                        "agent",
                        evidence_refs=(EvidenceRef(kind="match", ref_id=f.MATCH_ID),),
                    )
                )
            )

    def test_match_kind_ref_resolves_on_shape_b(self) -> None:
        record = PolicyNoBetRecord(
            **f.record_b_kwargs(
                explanation=f.make_explanation(
                    "agent",
                    evidence_refs=(EvidenceRef(kind="match", ref_id=f.MATCH_ID),),
                )
            )
        )
        assert record.explanation.evidence_refs[0].kind == "match"

    def test_conflict_evidence_refs_resolved_in_aggregate(self) -> None:
        from kalakal.domain import DataQuality

        quality = DataQuality(
            is_complete=False,
            missing_fields=(),
            conflicts=(
                f.make_conflict(
                    "series_description",
                    ref=EvidenceRef(kind="market", ref_id="mkt-unknown"),
                ),
            ),
        )
        candidate = f.make_candidate_market(data_quality=quality)
        with pytest.raises(ValidationError, match="does not resolve"):
            PreSelectionAbstentionRecord(
                **f.record_a_agent_kwargs(
                    candidates_considered=(
                        CandidateEligibility(
                            market=candidate,
                            eligible=True,
                            ineligibility_reasons=(),
                        ),
                    )
                )
            )


class TestTransitionHistory:
    def test_wrong_terminal_state_rejected(self) -> None:
        with pytest.raises(ValidationError, match="must end at"):
            PolicyNoBetRecord(
                **f.record_b_kwargs(transitions=f.make_transitions(f.C_PATH))
            )

    def test_first_state_must_be_created(self) -> None:
        path = f.make_transitions(f.A_AGENT_PATH)[1:]
        with pytest.raises(ValidationError, match="start at 'created'"):
            PreSelectionAbstentionRecord(**f.record_a_agent_kwargs(transitions=path))

    def test_non_monotonic_timestamps_rejected(self) -> None:
        transitions = f.make_transitions(f.A_AGENT_PATH)
        shuffled = (
            transitions[0],
            StateTransition(state=transitions[1].state, at=f.ts(-5)),
            *transitions[2:],
        )
        with pytest.raises(ValidationError, match="non-decreasing"):
            PreSelectionAbstentionRecord(
                **f.record_a_agent_kwargs(transitions=shuffled)
            )

    def test_intermediate_terminal_state_rejected(self) -> None:
        path = f.make_transitions(
            ("created", "abstained", "explaining", "persisting", "abstained")
        )
        with pytest.raises(ValidationError, match="final transition"):
            PreSelectionAbstentionRecord(**f.record_a_agent_kwargs(transitions=path))


class TestCandidateEligibilityEntry:
    def test_eligible_with_reasons_rejected(self) -> None:
        with pytest.raises(ValidationError, match="must not carry reasons"):
            CandidateEligibility(
                market=f.make_candidate_market(),
                eligible=True,
                ineligibility_reasons=("ESTIMATOR_INPUT_MISSING",),
            )

    def test_ineligible_without_reasons_rejected(self) -> None:
        with pytest.raises(ValidationError, match="requires at least one reason"):
            CandidateEligibility(
                market=f.make_candidate_market(),
                eligible=False,
                ineligibility_reasons=(),
            )

    def test_duplicate_reasons_rejected(self) -> None:
        with pytest.raises(ValidationError, match="duplicates"):
            CandidateEligibility(
                market=f.make_candidate_market(),
                eligible=False,
                ineligibility_reasons=(
                    "ESTIMATOR_INPUT_MISSING",
                    "ESTIMATOR_INPUT_MISSING",
                ),
            )

    @pytest.mark.parametrize("reason", ["BAD_VIBES", "STALE"])
    def test_unknown_reason_rejected(self, reason: str) -> None:
        # STALE is deliberately not an eligibility reason: staleness is a
        # post-selection policy concern (POLICY_STALE_DATA), §5.6/§7.7.
        with pytest.raises(ValidationError):
            CandidateEligibility(
                market=f.make_candidate_market(),
                eligible=False,
                ineligibility_reasons=(reason,),  # type: ignore[arg-type]
            )


class TestEligibilityStatusMatrix:
    def test_open_and_eligible_valid(self) -> None:
        entry = CandidateEligibility(
            market=f.make_candidate_market(status="open"),
            eligible=True,
            ineligibility_reasons=(),
        )
        assert entry.eligible is True

    def test_open_and_ineligible_valid_without_not_open(self) -> None:
        entry = CandidateEligibility(
            market=f.make_candidate_market(status="open"),
            eligible=False,
            ineligibility_reasons=("ESTIMATOR_INPUT_CONFLICTED",),
        )
        assert entry.eligible is False

    def test_open_market_must_not_carry_not_open(self) -> None:
        with pytest.raises(ValidationError, match="must not carry NOT_OPEN"):
            CandidateEligibility(
                market=f.make_candidate_market(status="open"),
                eligible=False,
                ineligibility_reasons=("NOT_OPEN",),
            )

    def test_closed_market_cannot_be_eligible(self) -> None:
        with pytest.raises(ValidationError, match="cannot be eligible"):
            CandidateEligibility(
                market=f.make_candidate_market(status="closed"),
                eligible=True,
                ineligibility_reasons=(),
            )

    def test_closed_and_ineligible_with_not_open_valid(self) -> None:
        entry = CandidateEligibility(
            market=f.make_candidate_market(status="closed"),
            eligible=False,
            ineligibility_reasons=("NOT_OPEN", "ESTIMATOR_INPUT_MISSING"),
        )
        assert "NOT_OPEN" in entry.ineligibility_reasons

    def test_closed_and_ineligible_without_not_open_rejected(self) -> None:
        with pytest.raises(ValidationError, match="must carry NOT_OPEN"):
            CandidateEligibility(
                market=f.make_candidate_market(status="closed"),
                eligible=False,
                ineligibility_reasons=("ESTIMATOR_INPUT_MISSING",),
            )


class TestUnionEntryPoint:
    def test_payload_matching_no_shape_rejected(self) -> None:
        kwargs = f.record_c_kwargs()
        del kwargs["draft"]  # completed without a draft fits no shape
        with pytest.raises(ValidationError):
            validate_decision_record(kwargs)

    def test_draft_with_abstained_outcome_fits_no_shape(self) -> None:
        kwargs = f.record_b_kwargs(draft=f.make_draft())
        with pytest.raises(ValidationError):
            validate_decision_record(kwargs)

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate_decision_record(f.record_c_kwargs(wallet_address="synthetic"))
