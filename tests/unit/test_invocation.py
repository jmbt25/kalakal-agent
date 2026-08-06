"""Unit tests for model-invocation metadata and selection output (§6.2.10, §5.2)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kalakal.domain import (
    Abstention,
    DeterministicSelectorMetadata,
    MarketSelection,
    ModelInvocationInvoked,
    ModelInvocationNotInvoked,
    ToolCallRecord,
)
from tests.unit import factories as f


class TestModelInvocationInvoked:
    def test_valid(self) -> None:
        invocation = f.make_invoked()
        assert invocation.invocation_status == "invoked"
        assert invocation.fallback_used is False

    def test_valid_with_fallback(self) -> None:
        invocation = f.make_invoked(
            fallback_used=True,
            fallback_model_id="gemini-3.5-flash",
            fallback_reason="Primary model timed out.",
            usage=(
                f.make_usage("gemini-3.6-flash"),
                f.make_usage("gemini-3.5-flash"),
            ),
        )
        assert invocation.fallback_model_id == "gemini-3.5-flash"

    @pytest.mark.parametrize(
        "field",
        [
            "invocation_id",
            "model_id",
            "prompt_version",
            "response_ids",
            "usage",
            "fallback_used",
            "tool_calls",
        ],
    )
    def test_required_model_metadata(self, field: str) -> None:
        kwargs = f.invoked_kwargs()
        del kwargs[field]
        with pytest.raises(ValidationError):
            ModelInvocationInvoked(**kwargs)

    def test_empty_response_ids_rejected(self) -> None:
        with pytest.raises(ValidationError):
            f.make_invoked(response_ids=())

    def test_empty_usage_rejected(self) -> None:
        with pytest.raises(ValidationError):
            f.make_invoked(usage=())

    def test_fallback_used_without_metadata_rejected(self) -> None:
        with pytest.raises(ValidationError, match="fallback_used requires"):
            f.make_invoked(fallback_used=True)

    @pytest.mark.parametrize(
        "over",
        [
            {"fallback_model_id": "gemini-3.5-flash"},
            {"fallback_reason": "unused"},
        ],
    )
    def test_fallback_metadata_without_use_rejected(self, over: dict[str, str]) -> None:
        with pytest.raises(ValidationError, match="must be absent"):
            f.make_invoked(**over)

    @pytest.mark.parametrize("value", [1500.0, True, "1500"])
    def test_non_int_token_counts_rejected(self, value: object) -> None:
        from kalakal.domain import ModelCallUsage

        with pytest.raises(ValidationError):
            ModelCallUsage(
                model_id="gemini-3.6-flash",
                call_count=1,
                input_tokens=value,  # type: ignore[arg-type]
                output_tokens=300,
            )


class TestUsageAndResponseConsistency:
    def test_unrelated_usage_model_rejected(self) -> None:
        with pytest.raises(ValidationError, match="unrelated"):
            f.make_invoked(
                usage=(
                    f.make_usage("gemini-3.6-flash"),
                    f.make_usage("gemini-9-experimental"),
                )
            )

    def test_duplicate_usage_entries_rejected(self) -> None:
        with pytest.raises(ValidationError, match="unique model IDs"):
            f.make_invoked(
                usage=(
                    f.make_usage("gemini-3.6-flash"),
                    f.make_usage("gemini-3.6-flash", call_count=2),
                )
            )

    def test_missing_primary_usage_rejected(self) -> None:
        with pytest.raises(ValidationError, match="primary model_id"):
            f.make_invoked(usage=(f.make_usage("gemini-3.5-flash"),))

    def test_fallback_without_fallback_usage_rejected(self) -> None:
        with pytest.raises(ValidationError, match="fallback model_id"):
            f.make_invoked(
                fallback_used=True,
                fallback_model_id="gemini-3.5-flash",
                fallback_reason="Primary model timed out.",
                usage=(f.make_usage("gemini-3.6-flash"),),
            )

    def test_identical_primary_and_fallback_rejected(self) -> None:
        with pytest.raises(ValidationError, match="must differ"):
            f.make_invoked(
                fallback_used=True,
                fallback_model_id="gemini-3.6-flash",
                fallback_reason="Primary model timed out.",
            )

    def test_unrelated_usage_with_fallback_rejected(self) -> None:
        with pytest.raises(ValidationError, match="unrelated"):
            f.make_invoked(
                fallback_used=True,
                fallback_model_id="gemini-3.5-flash",
                fallback_reason="Primary model timed out.",
                usage=(
                    f.make_usage("gemini-3.6-flash"),
                    f.make_usage("gemini-3.5-flash"),
                    f.make_usage("claude-fable-5"),
                ),
            )

    def test_duplicate_response_ids_rejected(self) -> None:
        with pytest.raises(ValidationError, match="response_ids must be unique"):
            f.make_invoked(response_ids=("resp-1", "resp-1"))

    def test_multiple_distinct_response_ids_accepted(self) -> None:
        invocation = f.make_invoked(
            usage=(f.make_usage("gemini-3.6-flash", call_count=2),),
            response_ids=("resp-1", "resp-2"),
        )
        assert len(invocation.response_ids) == 2

    def test_call_count_need_not_match_response_count(self) -> None:
        # A failed attempt has no response ID, so two calls may legitimately
        # produce a single response.
        invocation = f.make_invoked(
            usage=(f.make_usage("gemini-3.6-flash", call_count=2),),
            response_ids=("resp-1",),
        )
        assert invocation.usage[0].call_count == 2


class TestCallAttemptBounds:
    def test_per_model_call_count_bounded_at_five(self) -> None:
        invocation = f.make_invoked(
            usage=(f.make_usage("gemini-3.6-flash", call_count=5),)
        )
        assert invocation.usage[0].call_count == 5

    @pytest.mark.parametrize("count", [6, 16, 0])
    def test_per_model_call_count_out_of_bounds_rejected(self, count: int) -> None:
        with pytest.raises(ValidationError):
            f.make_invoked(usage=(f.make_usage("gemini-3.6-flash", call_count=count),))

    def test_total_six_calls_accepted(self) -> None:
        invocation = f.make_invoked(
            fallback_used=True,
            fallback_model_id="gemini-3.5-flash",
            fallback_reason="Primary model timed out.",
            usage=(
                f.make_usage("gemini-3.6-flash", call_count=4),
                f.make_usage("gemini-3.5-flash", call_count=2),
            ),
        )
        assert sum(entry.call_count for entry in invocation.usage) == 6

    def test_total_seven_calls_rejected(self) -> None:
        with pytest.raises(ValidationError, match="total model calls"):
            f.make_invoked(
                fallback_used=True,
                fallback_model_id="gemini-3.5-flash",
                fallback_reason="Primary model timed out.",
                usage=(
                    f.make_usage("gemini-3.6-flash", call_count=5),
                    f.make_usage("gemini-3.5-flash", call_count=2),
                ),
            )

    def test_response_ids_exceeding_call_count_rejected(self) -> None:
        with pytest.raises(ValidationError, match="cannot outnumber"):
            f.make_invoked(
                usage=(f.make_usage("gemini-3.6-flash", call_count=1),),
                response_ids=("resp-1", "resp-2"),
            )

    def test_response_ids_equal_to_call_count_accepted(self) -> None:
        invocation = f.make_invoked(
            usage=(f.make_usage("gemini-3.6-flash", call_count=3),),
            response_ids=("resp-1", "resp-2", "resp-3"),
        )
        assert len(invocation.response_ids) == 3


class TestModelInvocationNotInvoked:
    def test_valid_carries_only_status(self) -> None:
        invocation = f.make_not_invoked()
        assert invocation.invocation_status == "not_invoked"
        assert set(type(invocation).model_fields) == {"invocation_status"}

    @pytest.mark.parametrize(
        "extra",
        [
            {"model_id": "gemini-3.6-flash"},
            {"prompt_version": "prompt-1"},
            {"response_ids": ("resp-1",)},
            {"usage": ()},
            {"tool_calls": ()},
            {"invocation_id": "invocation-1"},
            {"fallback_used": False},
        ],
    )
    def test_model_fields_rejected_not_dummy_valued(
        self, extra: dict[str, object]
    ) -> None:
        with pytest.raises(ValidationError):
            ModelInvocationNotInvoked(invocation_status="not_invoked", **extra)

    def test_wrong_status_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ModelInvocationNotInvoked(invocation_status="invoked")  # type: ignore[arg-type]


class TestDeterministicSelectorMetadata:
    def test_valid(self) -> None:
        metadata = f.make_selector_metadata()
        assert metadata.selector_id == "deterministic-stub"
        assert metadata.test_only is True

    def test_carries_exactly_the_three_identity_fields(self) -> None:
        assert set(DeterministicSelectorMetadata.model_fields) == {
            "selector_id",
            "selector_version",
            "test_only",
        }

    @pytest.mark.parametrize("value", [False, 1, "true", None])
    def test_test_only_must_be_literal_true(self, value: object) -> None:
        with pytest.raises(ValidationError):
            f.make_selector_metadata(test_only=value)

    @pytest.mark.parametrize("field", ["selector_id", "selector_version", "test_only"])
    def test_required_fields(self, field: str) -> None:
        kwargs = f.selector_metadata_kwargs()
        del kwargs[field]
        with pytest.raises(ValidationError):
            DeterministicSelectorMetadata(**kwargs)

    @pytest.mark.parametrize(
        "extra",
        [
            {"model_id": "gemini-3.6-flash"},
            {"prompt_version": "prompt-1"},
            {"response_ids": ("resp-1",)},
            {"usage": ()},
            {"tool_calls": ()},
            {"fallback_used": False},
            {"invocation_status": "invoked"},
        ],
    )
    def test_model_shaped_fields_structurally_rejected(
        self, extra: dict[str, object]
    ) -> None:
        with pytest.raises(ValidationError):
            f.make_selector_metadata(**extra)


class TestToolCallRecord:
    def test_listing_tool_takes_no_market_id(self) -> None:
        with pytest.raises(ValidationError, match="takes no market_id"):
            ToolCallRecord(
                tool_name="list_candidate_markets",
                market_id=f.MARKET_ID,
                called_at=f.ts(1),
            )

    @pytest.mark.parametrize(
        "tool",
        [
            "get_match_context",
            "get_market_snapshot",
            "get_edge_assessment",
            "get_policy_decision",
        ],
    )
    def test_market_tools_require_market_id(self, tool: str) -> None:
        with pytest.raises(ValidationError, match="requires a market_id"):
            ToolCallRecord(tool_name=tool, called_at=f.ts(1))  # type: ignore[arg-type]

    def test_unknown_tool_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ToolCallRecord(
                tool_name="post_discord_message",  # type: ignore[arg-type]
                market_id=f.MARKET_ID,
                called_at=f.ts(1),
            )


class TestSelectionOutput:
    def test_valid_selection(self) -> None:
        selection = MarketSelection(
            abstained=False, selected_market_id=f.MARKET_ID, selected_side="yes"
        )
        assert selection.selected_market_id == f.MARKET_ID

    def test_valid_abstention(self) -> None:
        abstention = Abstention(
            abstained=True, abstain_reason_code="INSUFFICIENT_EVIDENCE"
        )
        assert abstention.selected_market_id is None

    def test_abstention_naming_market_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Abstention(
                abstained=True,
                selected_market_id=f.MARKET_ID,  # type: ignore[arg-type]
                abstain_reason_code="INSUFFICIENT_EVIDENCE",
            )

    def test_abstention_requires_reason_code(self) -> None:
        with pytest.raises(ValidationError):
            Abstention(abstained=True)  # type: ignore[call-arg]

    def test_selection_requires_side(self) -> None:
        with pytest.raises(ValidationError):
            MarketSelection(abstained=False, selected_market_id=f.MARKET_ID)  # type: ignore[call-arg]

    @pytest.mark.parametrize("value", [1, 0, "true"])
    def test_abstained_flag_requires_bool(self, value: object) -> None:
        with pytest.raises(ValidationError):
            Abstention(
                abstained=value,  # type: ignore[arg-type]
                abstain_reason_code="INSUFFICIENT_EVIDENCE",
            )

    def test_contradictory_flags_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MarketSelection(
                abstained=True,  # type: ignore[arg-type]
                selected_market_id=f.MARKET_ID,
                selected_side="yes",
            )

    def test_unknown_reason_code_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Abstention(abstained=True, abstain_reason_code="BORED")  # type: ignore[arg-type]
