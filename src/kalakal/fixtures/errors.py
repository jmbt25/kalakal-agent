"""Typed, bounded fixture-repository failures.

The repository knows no run ID, so it never fabricates a ``RunFailure``
(§6.2.11); the pipeline translates these typed errors later. Messages are
bounded and redaction-safe: they may name manifest-validated scenario IDs,
filenames, and check descriptions, never raw file contents or arbitrary
caller input. As defense in depth, every message is scanned with
:func:`find_sensitive_content` before it is stored; a sensitive-shaped
detail is replaced entirely with a generic redacted message.
"""

from __future__ import annotations

from typing import ClassVar, Final

from kalakal.domain.primitives import FailureClassification, FailureReasonCode
from kalakal.domain.sensitive import find_sensitive_content

MAX_ERROR_MESSAGE_LENGTH = 500

REDACTED_ERROR_MESSAGE: Final = (
    "fixture repository error detail redacted: sensitive-shaped content"
)


class FixtureRepositoryError(Exception):
    """Base typed repository failure carrying reason code and classification."""

    reason_code: ClassVar[FailureReasonCode]
    classification: ClassVar[FailureClassification]

    def __init__(self, message: str) -> None:
        if find_sensitive_content(message) is not None:
            message = REDACTED_ERROR_MESSAGE
        if len(message) > MAX_ERROR_MESSAGE_LENGTH:
            message = message[: MAX_ERROR_MESSAGE_LENGTH - 12] + " [truncated]"
        super().__init__(message)
        self.message = message


class ScenarioUnknownError(FixtureRepositoryError):
    """The requested scenario ID does not exist in the fixture set."""

    reason_code: ClassVar[FailureReasonCode] = "SCENARIO_UNKNOWN"
    classification: ClassVar[FailureClassification] = "permanent"


class FixtureInvalidError(FixtureRepositoryError):
    """A fixture file is malformed, tampered with, or internally inconsistent."""

    reason_code: ClassVar[FailureReasonCode] = "FIXTURE_INVALID"
    classification: ClassVar[FailureClassification] = "permanent"
