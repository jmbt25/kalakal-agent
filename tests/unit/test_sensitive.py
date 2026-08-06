"""Unit tests for the obvious-credential scanner (§6.1) and its wiring."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kalakal.domain import (
    CompletedProceedRecord,
    PolicyNoBetRecord,
    PreSelectionAbstentionRecord,
    find_sensitive_content,
)
from kalakal.domain.sensitive import (
    _MAX_STRINGS,
    SCAN_BUDGET_EXCEEDED,
    SCAN_DEPTH_EXCEEDED,
)
from tests.unit import factories as f

# 88 base58 characters — the shape of a Solana secret key.
_BASE58_KEY = "5Kb8kLf9zgWQnogidDA76MzPL6TsZZY36hWXMssSzNydYXYB9KF" + "a" * 37


class TestScannerPositive:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            (
                "-----BEGIN PRIVATE KEY-----\nMIIEvQ...",
                "PEM private-key header",
            ),
            (
                "-----BEGIN EC PRIVATE KEY-----",
                "PEM private-key header",
            ),
            (
                "use sk-abcdefghijklmnopqrstuvwx to authenticate",
                "credential token prefix",
            ),
            ("key sk_live_abcdefghijklmnop", "credential token prefix"),
            ("aws AKIAIOSFODNN7EXAMPLE", "credential token prefix"),
            (
                "ghp_abcdefghijklmnopqrstuvwxyz012345",
                "credential token prefix",
            ),
            (
                "xoxb-1234567890-abcdefghijklmnop",
                "credential token prefix",
            ),
            (
                "AIzaSyA1bC2dE3fG4hI5jK6lM7nO8pQ9rS0tUvW",
                "credential token prefix",
            ),
            ("api_key=abc123def456", "credential assignment"),
            ("password: hunter2000", "credential assignment"),
            ("private_key = 0xdeadbeefcafe", "credential assignment"),
            ("seed_phrase: correcthorsebattery", "credential assignment"),
            ("client secret: 9f8e7d6c5b", "credential assignment"),
            ("contact synthetic@example.com now", "email address"),
            (_BASE58_KEY, "base58 private-key-like payload"),
        ],
    )
    def test_strong_indicators_detected(self, text: str, expected: str) -> None:
        assert find_sensitive_content(text) == expected


class TestScannerNegative:
    @pytest.mark.parametrize(
        "text",
        [
            "The synthetic market resolves after the grand final.",
            "The team rotated its private key policy last season.",
            "No API key is required for fixture runs.",
            "Rotate the auth token before the final.",
            "The word password appears in this harmless sentence.",
            "seed phrase discussions are out of scope",
            "Ask 0.600000 | net edge 0.044000 #nfa",
            "https://markets.kalakal.invalid/mkt-1",
            f.sha_hex("any-content-digest"),  # 64-hex digest stays allowed
            "SIMULATION — DO NOT POST",
            "token bucket rate limiting is enabled",
        ],
    )
    def test_safe_prose_allowed(self, text: str) -> None:
        assert find_sensitive_content(text) is None

    def test_non_string_scalars_ignored(self) -> None:
        assert find_sensitive_content(650_000) is None
        assert find_sensitive_content(None) is None

    def test_nested_model_scanned(self) -> None:
        draft = f.make_draft()
        assert find_sensitive_content(draft) is None


class TestRecordWiring:
    def test_credential_summary_rejected_on_shape_a(self) -> None:
        with pytest.raises(ValidationError, match="sensitive-content scan"):
            PreSelectionAbstentionRecord(
                **f.record_a_agent_kwargs(
                    explanation=f.make_explanation(
                        "agent", summary="Use api_key=abc123def456 for access."
                    )
                )
            )

    def test_credential_data_gap_rejected_on_shape_b(self) -> None:
        with pytest.raises(ValidationError, match="sensitive-content scan"):
            PolicyNoBetRecord(
                **f.record_b_kwargs(
                    explanation=f.make_explanation(
                        "agent",
                        data_gaps=("-----BEGIN PRIVATE KEY----- leaked",),
                    )
                )
            )

    def test_email_in_conflict_note_rejected_on_shape_c(self) -> None:
        with pytest.raises(ValidationError, match="sensitive-content scan"):
            CompletedProceedRecord(
                **f.record_c_kwargs(
                    explanation=f.make_explanation(
                        "agent",
                        conflicts=("Analyst synthetic@example.com disagrees.",),
                    )
                )
            )

    def test_clean_records_still_validate(self) -> None:
        assert PreSelectionAbstentionRecord(**f.record_a_agent_kwargs())
        assert PolicyNoBetRecord(**f.record_b_kwargs())
        assert CompletedProceedRecord(**f.record_c_kwargs())


class TestFailClosed:
    def test_over_budget_all_safe_payload_fails_closed(self) -> None:
        payload = tuple(f"safe synthetic string {i}" for i in range(_MAX_STRINGS + 1))
        assert find_sensitive_content(payload) == SCAN_BUDGET_EXCEEDED

    def test_credential_cannot_hide_after_budget_exhaustion(self) -> None:
        safe = tuple(f"safe synthetic string {i}" for i in range(_MAX_STRINGS + 1))
        assert find_sensitive_content(safe + ("api_key=abc123def456",)) is not None

    def test_credential_cannot_hide_before_budget_exhaustion(self) -> None:
        safe = tuple(f"safe synthetic string {i}" for i in range(_MAX_STRINGS + 1))
        assert find_sensitive_content(("api_key=abc123def456",) + safe) is not None

    def test_exactly_at_budget_all_safe_accepted(self) -> None:
        payload = tuple(f"safe synthetic string {i}" for i in range(_MAX_STRINGS))
        assert find_sensitive_content(payload) is None

    def test_depth_exhaustion_fails_closed(self) -> None:
        nested: object = ("leaf synthetic string",)
        for _ in range(20):
            nested = (nested,)
        assert find_sensitive_content(nested) == SCAN_DEPTH_EXCEEDED

    def test_valid_record_depth_stays_inside_budget(self) -> None:
        # The deepest valid structure: record -> candidates -> eligibility ->
        # market -> data_quality -> conflicts -> conflict -> refs -> ref -> str.
        from kalakal.domain import DataQuality

        quality = DataQuality(
            is_complete=False,
            missing_fields=(),
            conflicts=(f.make_conflict("series_description"),),
        )
        record = PreSelectionAbstentionRecord(
            **f.record_a_agent_kwargs(
                candidates_considered=(
                    f.make_consideration(
                        market=f.make_candidate_market(data_quality=quality)
                    ),
                )
            )
        )
        assert find_sensitive_content(record) is None


class TestFailureWiring:
    def test_credential_message_rejected(self) -> None:
        with pytest.raises(ValidationError, match="sensitive-content scan"):
            f.make_run_failure(message="Retry with password: hunter2000 later.")

    def test_credential_rejected_output_rejected(self) -> None:
        with pytest.raises(ValidationError, match="sensitive-content scan"):
            f.make_run_failure(
                state_at_failure="selecting",
                classification="safety",
                reason_code="MODEL_OUTPUT_REJECTED",
                model_invocation=f.make_invoked(),
                rejected_output_truncated=f"key is {_BASE58_KEY}",
            )

    def test_clean_failure_still_validates(self) -> None:
        assert f.make_run_failure()
