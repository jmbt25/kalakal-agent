"""RunRequest contract (architecture.md §6.2.1)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, cast

from pydantic import Field

from kalakal.domain.primitives import (
    Identifier,
    RunMode,
    StrictModel,
    UtcDatetime,
)


def _evaluation_time_default(data: dict[str, Any]) -> datetime:
    # Pydantic calls this only when evaluation_time is omitted, passing the
    # already validated preceding fields. The value is None only when
    # requested_at itself failed validation — the model is already invalid
    # then and this unvalidated placeholder is never exposed.
    return cast(datetime, data.get("requested_at"))


class RunRequest(StrictModel):
    """A validated request to execute one fixture run.

    ``evaluation_time`` is the frozen UTC evaluation clock for reproducible
    runs and is always non-null after validation. When omitted, its
    validated-data default factory freezes it to the already supplied
    ``requested_at`` (no wall clock is read inside the domain model); an
    explicit null fails the strict non-optional datetime type. Unknown
    scenario and duplicate idempotency-key handling are orchestration
    behavior (plan slice 5), not schema invariants.
    """

    schema_version: Literal["1"]
    run_id: Identifier
    idempotency_key: Identifier
    scenario_id: Identifier
    mode: RunMode
    requested_at: UtcDatetime
    evaluation_time: UtcDatetime = Field(default_factory=_evaluation_time_default)
