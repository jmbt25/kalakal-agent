"""PolicyDecision contract (architecture.md §6.2.7).

Only the contract shapes live here; policy-engine behavior is plan slice 4.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from kalakal.domain.primitives import (
    Identifier,
    PolicyOutcome,
    PolicyReasonCode,
    Sha256Hex,
    ShortText,
    StrictModel,
    UtcDatetime,
    VersionStr,
)

ObservedValue = Annotated[int, Field(ge=-2_000_000, le=2_000_000)]


class PolicyCheck(StrictModel):
    """One deterministic policy check with its observed value and threshold."""

    check_id: Identifier
    passed: bool
    observed_value: ObservedValue
    threshold_value: ObservedValue
    threshold_source: ShortText


class PolicyDecision(StrictModel):
    """The policy engine's binding outcome; ``no_bet`` is success, not error."""

    schema_version: Literal["1"]
    decision: PolicyOutcome
    reason_codes: Annotated[tuple[PolicyReasonCode, ...], Field(max_length=8)]
    checks: Annotated[tuple[PolicyCheck, ...], Field(min_length=1, max_length=32)]
    policy_version: VersionStr
    evaluated_at: UtcDatetime
    inputs_digest: Sha256Hex

    @model_validator(mode="after")
    def _check_consistency(self) -> PolicyDecision:
        check_ids = [check.check_id for check in self.checks]
        if len(set(check_ids)) != len(check_ids):
            raise ValueError("checks must have unique check_id values")
        if len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("reason_codes must not contain duplicates")
        any_failed = any(not check.passed for check in self.checks)
        if self.decision == "proceed":
            if any_failed:
                raise ValueError("proceed requires every check to pass")
            if self.reason_codes:
                raise ValueError("proceed must not carry reason codes")
        else:
            if not any_failed:
                raise ValueError("no_bet requires at least one failed check")
            if not self.reason_codes:
                raise ValueError("no_bet requires at least one reason code")
        return self
