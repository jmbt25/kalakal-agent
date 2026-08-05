"""Unit tests for RunRequest (§6.2.1)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from kalakal.domain import RunRequest
from tests.unit import factories as f


class TestRunRequest:
    def test_valid(self) -> None:
        request = f.make_run_request()
        assert request.mode == "fixture"

    @pytest.mark.parametrize("mode", ["live", "paper", "shadow", "", "FIXTURE"])
    def test_non_fixture_mode_rejected(self, mode: str) -> None:
        with pytest.raises(ValidationError):
            RunRequest(**f.run_request_kwargs(mode=mode))

    @pytest.mark.parametrize(
        "field",
        [
            "schema_version",
            "run_id",
            "idempotency_key",
            "scenario_id",
            "mode",
            "requested_at",
        ],
    )
    def test_required_fields(self, field: str) -> None:
        kwargs = f.run_request_kwargs()
        del kwargs[field]
        with pytest.raises(ValidationError):
            RunRequest(**kwargs)

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RunRequest(**f.run_request_kwargs(wallet_key="x"))

    def test_naive_requested_at_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RunRequest(**f.run_request_kwargs(requested_at=datetime(2026, 8, 5, 12, 0)))

    def test_unknown_schema_version_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RunRequest(**f.run_request_kwargs(schema_version="2"))


class TestEvaluationTimeFreezing:
    def test_omitted_freezes_to_requested_at(self) -> None:
        request = f.make_run_request()
        assert request.evaluation_time == request.requested_at
        assert request.evaluation_time.utcoffset() == timedelta(0)

    def test_explicit_utc_value_kept(self) -> None:
        historical = datetime(2026, 7, 1, 9, 30, tzinfo=timezone.utc)
        request = f.make_run_request(evaluation_time=historical)
        assert request.evaluation_time == historical
        assert request.evaluation_time != request.requested_at

    def test_explicit_null_rejected(self) -> None:
        with pytest.raises(ValidationError, match="valid datetime"):
            RunRequest(**f.run_request_kwargs(evaluation_time=None))

    def test_naive_evaluation_time_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RunRequest(**f.run_request_kwargs(evaluation_time=datetime(2026, 8, 5, 12)))

    def test_non_utc_evaluation_time_rejected(self) -> None:
        offset_time = datetime(2026, 8, 5, 12, 0, tzinfo=timezone(timedelta(hours=8)))
        with pytest.raises(ValidationError):
            RunRequest(**f.run_request_kwargs(evaluation_time=offset_time))

    def test_json_omitted_freezes_to_requested_at(self) -> None:
        payload = {
            "schema_version": "1",
            "run_id": "run-1",
            "idempotency_key": "idem-1",
            "scenario_id": "clear-edge",
            "mode": "fixture",
            "requested_at": "2026-08-05T12:00:00Z",
        }
        request = RunRequest.model_validate_json(json.dumps(payload))
        assert request.evaluation_time == request.requested_at

    def test_json_null_rejected(self) -> None:
        payload = {
            "schema_version": "1",
            "run_id": "run-1",
            "idempotency_key": "idem-1",
            "scenario_id": "clear-edge",
            "mode": "fixture",
            "requested_at": "2026-08-05T12:00:00Z",
            "evaluation_time": None,
        }
        with pytest.raises(ValidationError, match="valid datetime"):
            RunRequest.model_validate_json(json.dumps(payload))


class TestJsonSchema:
    def test_evaluation_time_publishes_no_null_default(self) -> None:
        schema = RunRequest.model_json_schema()
        evaluation_time = schema["properties"]["evaluation_time"]
        assert "default" not in evaluation_time
        assert evaluation_time["type"] == "string"
        assert evaluation_time["format"] == "date-time"
        assert "requested_at" in schema["required"]
        assert "evaluation_time" not in schema["required"]
