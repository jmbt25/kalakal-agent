"""Unit tests for RunFailure and FailedModelAttempt (§6.2.11)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from kalakal.domain import FailedModelAttempt, RunFailure
from tests.unit import factories as f


class TestRunFailure:
    def test_valid_permanent_fixture_invalid(self) -> None:
        failure = f.make_run_failure()
        assert failure.classification == "permanent"
        assert failure.model_invocation is None
        assert failure.failed_model_attempts == ()

    def test_valid_model_output_rejected(self) -> None:
        failure = f.make_run_failure(
            state_at_failure="selecting",
            classification="safety",
            reason_code="MODEL_OUTPUT_REJECTED",
            model_invocation=f.make_invoked(),
            rejected_output_truncated='{"selected_market_id": "mkt-unknown"',
        )
        assert failure.classification == "safety"

    @pytest.mark.parametrize(
        ("reason", "classification"),
        [
            ("SCENARIO_UNKNOWN", "permanent"),
            ("FIXTURE_INVALID", "permanent"),
            ("REQUEST_INVALID", "permanent"),
            ("RUN_DEADLINE_EXCEEDED", "retryable"),
            ("PERSISTENCE_ERROR", "retryable"),
            ("POLICY_INVARIANT_BREACH", "safety"),
            ("TOOL_CALL_OUT_OF_BOUNDS", "safety"),
        ],
    )
    def test_pinned_classifications_valid(
        self, reason: str, classification: str
    ) -> None:
        failure = f.make_run_failure(reason_code=reason, classification=classification)
        assert failure.reason_code == reason

    @pytest.mark.parametrize(
        ("reason", "classification"),
        [
            ("SCENARIO_UNKNOWN", "retryable"),
            ("FIXTURE_INVALID", "safety"),
            ("REQUEST_INVALID", "retryable"),
            ("REQUEST_INVALID", "safety"),
            ("MODEL_UNAVAILABLE", "permanent"),
            ("MODEL_OUTPUT_REJECTED", "retryable"),
            ("MODEL_OUTPUT_REJECTED", "permanent"),
            ("RUN_DEADLINE_EXCEEDED", "permanent"),
            ("RUN_DEADLINE_EXCEEDED", "safety"),
            ("POLICY_INVARIANT_BREACH", "retryable"),
            ("POLICY_INVARIANT_BREACH", "permanent"),
            ("TOOL_CALL_OUT_OF_BOUNDS", "retryable"),
            ("PERSISTENCE_ERROR", "permanent"),
            ("PERSISTENCE_ERROR", "safety"),
        ],
    )
    def test_pinned_classification_mismatch_rejected(
        self, reason: str, classification: str
    ) -> None:
        with pytest.raises(ValidationError, match="must be classified"):
            f.make_run_failure(
                reason_code=reason,
                classification=classification,
                model_invocation=(
                    f.make_invoked() if reason == "MODEL_OUTPUT_REJECTED" else None
                ),
                rejected_output_truncated=(
                    "x" if reason == "MODEL_OUTPUT_REJECTED" else None
                ),
                failed_model_attempts=(
                    (f.make_failed_attempt(),) if reason == "MODEL_UNAVAILABLE" else ()
                ),
            )

    @pytest.mark.parametrize("classification", ["retryable", "permanent", "safety"])
    def test_internal_error_classification_unpinned(self, classification: str) -> None:
        failure = f.make_run_failure(
            reason_code="INTERNAL_ERROR", classification=classification
        )
        assert failure.classification == classification

    def test_model_output_rejected_requires_invocation(self) -> None:
        with pytest.raises(ValidationError, match="model-invocation metadata"):
            f.make_run_failure(
                classification="safety",
                reason_code="MODEL_OUTPUT_REJECTED",
                rejected_output_truncated="x",
            )

    def test_model_output_rejected_requires_truncated_output(self) -> None:
        with pytest.raises(ValidationError, match="truncated rejected output"):
            f.make_run_failure(
                classification="safety",
                reason_code="MODEL_OUTPUT_REJECTED",
                model_invocation=f.make_invoked(),
            )

    def test_rejected_output_on_other_reason_rejected(self) -> None:
        with pytest.raises(ValidationError, match="only for MODEL_OUTPUT_REJECTED"):
            f.make_run_failure(rejected_output_truncated="x")

    @pytest.mark.parametrize(
        "state", ["completed", "abstained", "failed", "timed_out", "unknown"]
    )
    def test_terminal_or_unknown_state_at_failure_rejected(self, state: str) -> None:
        with pytest.raises(ValidationError):
            f.make_run_failure(state_at_failure=state)

    def test_unbounded_message_rejected(self) -> None:
        with pytest.raises(ValidationError):
            f.make_run_failure(message="x" * 1001)

    def test_unbounded_rejected_output_rejected(self) -> None:
        with pytest.raises(ValidationError):
            f.make_run_failure(
                classification="safety",
                reason_code="MODEL_OUTPUT_REJECTED",
                model_invocation=f.make_invoked(),
                rejected_output_truncated="x" * 2001,
            )

    @pytest.mark.parametrize("code", ["OOPS", "fixture_invalid", "STALE", ""])
    def test_unknown_reason_code_rejected(self, code: str) -> None:
        with pytest.raises(ValidationError):
            f.make_run_failure(reason_code=code)

    @pytest.mark.parametrize(
        "field",
        [
            "schema_version",
            "run_id",
            "state_at_failure",
            "classification",
            "reason_code",
            "message",
            "occurred_at",
        ],
    )
    def test_required_fields(self, field: str) -> None:
        kwargs = f.run_failure_kwargs()
        del kwargs[field]
        with pytest.raises(ValidationError):
            RunFailure(**kwargs)

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            f.make_run_failure(stack_trace="...")


class TestModelUnavailableMetadata:
    def _unavailable_kwargs(self, **over: Any) -> dict[str, Any]:
        kwargs: dict[str, Any] = f.run_failure_kwargs(
            state_at_failure="selecting",
            classification="retryable",
            reason_code="MODEL_UNAVAILABLE",
            failed_model_attempts=(
                f.make_failed_attempt(),
                f.make_failed_attempt(
                    model_id="gemini-3.5-flash",
                    error_class="server_error",
                    is_fallback=True,
                ),
            ),
        )
        kwargs.update(over)
        return kwargs

    def test_valid_with_truthful_failed_attempts(self) -> None:
        failure = RunFailure(**self._unavailable_kwargs())
        assert failure.model_invocation is None
        assert len(failure.failed_model_attempts) == 2
        assert failure.failed_model_attempts[1].is_fallback is True
        assert failure.failed_model_attempts[0].response_id is None

    def test_without_failed_attempts_rejected(self) -> None:
        with pytest.raises(ValidationError, match="at least one failed model"):
            RunFailure(**self._unavailable_kwargs(failed_model_attempts=()))

    def test_with_successful_invocation_rejected(self) -> None:
        with pytest.raises(ValidationError, match="no successful invocation"):
            RunFailure(**self._unavailable_kwargs(model_invocation=f.make_invoked()))

    def test_attempt_metadata_only_when_available(self) -> None:
        failure = RunFailure(
            **self._unavailable_kwargs(
                failed_model_attempts=(
                    f.make_failed_attempt(
                        error_class="invalid_response",
                        response_id="resp-err-1",
                        input_tokens=900,
                        output_tokens=0,
                    ),
                )
            )
        )
        attempt = failure.failed_model_attempts[0]
        assert attempt.response_id == "resp-err-1"
        assert attempt.input_tokens == 900

    def test_other_reasons_may_carry_attempts(self) -> None:
        failure = f.make_run_failure(
            state_at_failure="selecting",
            classification="retryable",
            reason_code="RUN_DEADLINE_EXCEEDED",
            failed_model_attempts=(f.make_failed_attempt(),),
        )
        assert len(failure.failed_model_attempts) == 1


class TestReasonMetadataMatrix:
    """Truthful metadata combinations per failure reason (§6.2.11)."""

    @pytest.mark.parametrize(
        ("reason", "classification", "with_invocation", "with_attempts", "with_output"),
        [
            ("REQUEST_INVALID", "permanent", False, False, False),
            ("SCENARIO_UNKNOWN", "permanent", False, False, False),
            ("FIXTURE_INVALID", "permanent", False, False, False),
            ("MODEL_UNAVAILABLE", "retryable", False, True, False),
            ("MODEL_OUTPUT_REJECTED", "safety", True, False, True),
            # Deadline during model attempts: failed attempts, no invocation.
            ("RUN_DEADLINE_EXCEEDED", "retryable", False, True, False),
            # Deadline after a successful invocation.
            ("RUN_DEADLINE_EXCEEDED", "retryable", True, False, False),
            ("POLICY_INVARIANT_BREACH", "safety", True, False, False),
            ("TOOL_CALL_OUT_OF_BOUNDS", "safety", True, False, False),
            ("PERSISTENCE_ERROR", "retryable", True, False, False),
            ("PERSISTENCE_ERROR", "retryable", False, False, False),
            ("INTERNAL_ERROR", "permanent", False, False, False),
        ],
    )
    def test_valid_combinations(
        self,
        reason: str,
        classification: str,
        with_invocation: bool,
        with_attempts: bool,
        with_output: bool,
    ) -> None:
        failure = f.make_run_failure(
            state_at_failure="selecting",
            classification=classification,
            reason_code=reason,
            model_invocation=f.make_invoked() if with_invocation else None,
            failed_model_attempts=((f.make_failed_attempt(),) if with_attempts else ()),
            rejected_output_truncated="{'truncated': " if with_output else None,
        )
        assert failure.reason_code == reason

    @pytest.mark.parametrize(
        "reason", ["REQUEST_INVALID", "SCENARIO_UNKNOWN", "FIXTURE_INVALID"]
    )
    def test_pre_model_reason_with_invocation_rejected(self, reason: str) -> None:
        with pytest.raises(ValidationError, match="before any model invocation"):
            f.make_run_failure(
                classification="permanent",
                reason_code=reason,
                model_invocation=f.make_invoked(),
            )

    @pytest.mark.parametrize(
        "reason", ["REQUEST_INVALID", "SCENARIO_UNKNOWN", "FIXTURE_INVALID"]
    )
    def test_pre_model_reason_with_attempts_rejected(self, reason: str) -> None:
        with pytest.raises(ValidationError, match="recorded only for"):
            f.make_run_failure(
                classification="permanent",
                reason_code=reason,
                failed_model_attempts=(f.make_failed_attempt(),),
            )

    @pytest.mark.parametrize(
        "reason", ["REQUEST_INVALID", "SCENARIO_UNKNOWN", "FIXTURE_INVALID"]
    )
    def test_pre_model_reason_with_rejected_output_rejected(self, reason: str) -> None:
        with pytest.raises(ValidationError, match="only for MODEL_OUTPUT_REJECTED"):
            f.make_run_failure(
                classification="permanent",
                reason_code=reason,
                rejected_output_truncated="x",
            )

    def test_model_output_rejected_with_attempt_series_rejected(self) -> None:
        with pytest.raises(ValidationError, match="recorded only for"):
            f.make_run_failure(
                state_at_failure="selecting",
                classification="safety",
                reason_code="MODEL_OUTPUT_REJECTED",
                model_invocation=f.make_invoked(),
                rejected_output_truncated="x",
                failed_model_attempts=(f.make_failed_attempt(),),
            )

    @pytest.mark.parametrize(
        ("reason", "classification"),
        [
            ("POLICY_INVARIANT_BREACH", "safety"),
            ("TOOL_CALL_OUT_OF_BOUNDS", "safety"),
            ("PERSISTENCE_ERROR", "retryable"),
            ("INTERNAL_ERROR", "permanent"),
        ],
    )
    def test_attempts_on_irrelevant_reason_rejected(
        self, reason: str, classification: str
    ) -> None:
        with pytest.raises(ValidationError, match="recorded only for"):
            f.make_run_failure(
                state_at_failure="selecting",
                classification=classification,
                reason_code=reason,
                failed_model_attempts=(f.make_failed_attempt(),),
            )


class TestFailedAttemptSeriesBounds:
    def _with_attempts(self, *attempts: FailedModelAttempt) -> RunFailure:
        return RunFailure(
            **f.run_failure_kwargs(
                state_at_failure="selecting",
                classification="retryable",
                reason_code="MODEL_UNAVAILABLE",
                failed_model_attempts=tuple(attempts),
            )
        )

    def test_primary_only_one_attempt_valid(self) -> None:
        failure = self._with_attempts(f.make_failed_attempt())
        assert failure.failed_model_attempts[0].attempt_count == 1

    def test_primary_retry_two_attempts_valid(self) -> None:
        failure = self._with_attempts(f.make_failed_attempt(attempt_count=2))
        assert failure.failed_model_attempts[0].attempt_count == 2

    def test_primary_plus_fallback_two_total_valid(self) -> None:
        failure = self._with_attempts(
            f.make_failed_attempt(),
            f.make_failed_attempt(model_id="gemini-3.5-flash", is_fallback=True),
        )
        assert len(failure.failed_model_attempts) == 2

    def test_primary_retry_plus_fallback_three_total_valid(self) -> None:
        failure = self._with_attempts(
            f.make_failed_attempt(attempt_count=2),
            f.make_failed_attempt(model_id="gemini-3.5-flash", is_fallback=True),
        )
        assert sum(a.attempt_count for a in failure.failed_model_attempts) == 3

    def test_four_total_attempts_rejected(self) -> None:
        with pytest.raises(ValidationError, match="must not exceed 3"):
            self._with_attempts(
                f.make_failed_attempt(attempt_count=2),
                f.make_failed_attempt(
                    model_id="gemini-3.5-flash",
                    attempt_count=2,
                    is_fallback=True,
                ),
            )

    def test_duplicate_model_ids_rejected(self) -> None:
        with pytest.raises(ValidationError, match="unique model IDs"):
            self._with_attempts(
                f.make_failed_attempt(),
                f.make_failed_attempt(is_fallback=True),
            )

    def test_two_primary_series_rejected(self) -> None:
        with pytest.raises(ValidationError, match="one primary"):
            self._with_attempts(
                f.make_failed_attempt(),
                f.make_failed_attempt(model_id="gemini-3.5-flash"),
            )

    def test_two_fallback_series_rejected(self) -> None:
        with pytest.raises(ValidationError, match="one fallback"):
            self._with_attempts(
                f.make_failed_attempt(is_fallback=True),
                f.make_failed_attempt(model_id="gemini-3.5-flash", is_fallback=True),
            )

    def test_fallback_only_rejected(self) -> None:
        with pytest.raises(ValidationError, match="requires a primary"):
            self._with_attempts(f.make_failed_attempt(is_fallback=True))

    def test_fallback_before_primary_rejected(self) -> None:
        with pytest.raises(ValidationError, match="must come first"):
            self._with_attempts(
                f.make_failed_attempt(model_id="gemini-3.5-flash", is_fallback=True),
                f.make_failed_attempt(),
            )

    def test_three_series_rejected(self) -> None:
        with pytest.raises(ValidationError):
            self._with_attempts(
                f.make_failed_attempt(),
                f.make_failed_attempt(model_id="gemini-3.5-flash", is_fallback=True),
                f.make_failed_attempt(model_id="gemini-2.5-flash"),
            )


class TestFailedModelAttempt:
    def test_valid_minimal(self) -> None:
        attempt = f.make_failed_attempt()
        assert attempt.response_id is None
        assert attempt.input_tokens is None
        assert attempt.output_tokens is None

    @pytest.mark.parametrize("count", [0, 3, 5, -1])
    def test_attempt_count_bounds(self, count: int) -> None:
        # Per-series bound is 2: §5.3 allows at most one transient retry.
        with pytest.raises(ValidationError):
            f.make_failed_attempt(attempt_count=count)

    @pytest.mark.parametrize("count", [1, 2])
    def test_attempt_count_within_series_bound_accepted(self, count: int) -> None:
        assert f.make_failed_attempt(attempt_count=count).attempt_count == count

    @pytest.mark.parametrize("error_class", ["crashed", "TIMEOUT", ""])
    def test_unknown_error_class_rejected(self, error_class: str) -> None:
        with pytest.raises(ValidationError):
            f.make_failed_attempt(error_class=error_class)

    @pytest.mark.parametrize("value", [1, 0, "yes"])
    def test_is_fallback_requires_bool(self, value: object) -> None:
        with pytest.raises(ValidationError):
            f.make_failed_attempt(is_fallback=value)

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FailedModelAttempt(
                model_id="gemini-3.6-flash",
                attempt_count=1,
                error_class="timeout",
                is_fallback=False,
                api_key="sk-x",  # type: ignore[call-arg]
            )
