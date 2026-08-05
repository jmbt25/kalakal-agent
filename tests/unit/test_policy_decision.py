"""Unit tests for PolicyDecision and typed checks (§6.2.7)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kalakal.domain import PolicyDecision
from tests.unit import factories as f


class TestPolicyDecision:
    def test_valid_proceed(self) -> None:
        decision = f.make_policy_decision("proceed")
        assert decision.decision == "proceed"
        assert decision.reason_codes == ()

    def test_valid_no_bet(self) -> None:
        decision = f.make_policy_decision("no_bet")
        assert decision.decision == "no_bet"
        assert decision.reason_codes == ("POLICY_INSUFFICIENT_NET_EDGE",)
        assert any(not check.passed for check in decision.checks)

    def test_stale_data_is_a_policy_no_bet_reason(self) -> None:
        # Staleness lives here (post-selection policy), not in candidate
        # eligibility (§5.6, §7.7).
        decision = f.make_policy_decision(
            "no_bet",
            reason_codes=("POLICY_STALE_DATA",),
            checks=(
                f.make_policy_check(
                    check_id="freshness",
                    passed=False,
                    observed_value=90,
                    threshold_value=60,
                    threshold_source="policy_config_freshness",
                ),
            ),
        )
        assert decision.reason_codes == ("POLICY_STALE_DATA",)

    def test_proceed_with_failed_check_rejected(self) -> None:
        with pytest.raises(ValidationError, match="every check to pass"):
            f.make_policy_decision(
                "proceed", checks=(f.make_policy_check(passed=False),)
            )

    def test_proceed_with_reason_codes_rejected(self) -> None:
        with pytest.raises(ValidationError, match="must not carry reason codes"):
            f.make_policy_decision("proceed", reason_codes=("POLICY_STALE_DATA",))

    def test_no_bet_with_all_passing_checks_rejected(self) -> None:
        with pytest.raises(ValidationError, match="at least one failed check"):
            f.make_policy_decision("no_bet", checks=(f.make_policy_check(),))

    def test_no_bet_without_reason_codes_rejected(self) -> None:
        with pytest.raises(ValidationError, match="at least one reason code"):
            f.make_policy_decision("no_bet", reason_codes=())

    def test_empty_checks_rejected(self) -> None:
        with pytest.raises(ValidationError):
            f.make_policy_decision("proceed", checks=())

    def test_duplicate_check_ids_rejected(self) -> None:
        with pytest.raises(ValidationError, match="unique check_id"):
            f.make_policy_decision(
                "proceed", checks=(f.make_policy_check(), f.make_policy_check())
            )

    def test_duplicate_reason_codes_rejected(self) -> None:
        with pytest.raises(ValidationError, match="duplicates"):
            f.make_policy_decision(
                "no_bet",
                reason_codes=("POLICY_STALE_DATA", "POLICY_STALE_DATA"),
                checks=(f.make_policy_check(passed=False),),
            )

    @pytest.mark.parametrize("code", ["STALE", "policy_stale_data", ""])
    def test_unknown_reason_code_rejected(self, code: str) -> None:
        with pytest.raises(ValidationError):
            f.make_policy_decision(
                "no_bet",
                reason_codes=(code,),
                checks=(f.make_policy_check(passed=False),),
            )

    @pytest.mark.parametrize("decision", ["approve", "PROCEED", ""])
    def test_unknown_decision_rejected(self, decision: str) -> None:
        kwargs = f.policy_decision_kwargs("proceed")
        kwargs["decision"] = decision
        with pytest.raises(ValidationError):
            PolicyDecision(**kwargs)

    @pytest.mark.parametrize(
        "field",
        [
            "schema_version",
            "decision",
            "reason_codes",
            "checks",
            "policy_version",
            "evaluated_at",
            "inputs_digest",
        ],
    )
    def test_required_fields(self, field: str) -> None:
        kwargs = f.policy_decision_kwargs("proceed")
        del kwargs[field]
        with pytest.raises(ValidationError):
            PolicyDecision(**kwargs)

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            f.make_policy_decision("proceed", override_flag=True)


class TestPolicyCheck:
    def test_valid_records_threshold_provenance(self) -> None:
        check = f.make_policy_check()
        assert check.threshold_source == "jup_callers_season1_config"

    @pytest.mark.parametrize("value", [44_000.0, True, "44000"])
    def test_non_int_observed_value_rejected(self, value: object) -> None:
        with pytest.raises(ValidationError):
            f.make_policy_check(observed_value=value)

    @pytest.mark.parametrize("value", [1, 0, "yes", None])
    def test_passed_requires_bool(self, value: object) -> None:
        with pytest.raises(ValidationError):
            f.make_policy_check(passed=value)
