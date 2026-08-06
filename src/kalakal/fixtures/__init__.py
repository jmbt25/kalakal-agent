"""Read-only synthetic fixture repository and repository-level models."""

from kalakal.fixtures.digest import canonical_fixture_json, fixture_entity_digest
from kalakal.fixtures.errors import (
    MAX_ERROR_MESSAGE_LENGTH,
    FixtureInvalidError,
    FixtureRepositoryError,
    ScenarioUnknownError,
)
from kalakal.fixtures.models import (
    ExpectedOutcomeClass,
    FixtureManifest,
    FixtureScenario,
    ManifestEntry,
    ScenarioCandidateBundle,
)
from kalakal.fixtures.repository import (
    MANIFEST_FILENAME,
    MAX_FIXTURE_FILE_BYTES,
    FixtureRepository,
)

__all__ = [
    "MANIFEST_FILENAME",
    "MAX_ERROR_MESSAGE_LENGTH",
    "MAX_FIXTURE_FILE_BYTES",
    "ExpectedOutcomeClass",
    "FixtureInvalidError",
    "FixtureManifest",
    "FixtureRepository",
    "FixtureRepositoryError",
    "FixtureScenario",
    "ManifestEntry",
    "ScenarioCandidateBundle",
    "ScenarioUnknownError",
    "canonical_fixture_json",
    "fixture_entity_digest",
]
