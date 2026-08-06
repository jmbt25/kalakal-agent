"""Read-only synthetic fixture repository (architecture.md §4.2).

Loads versioned synthetic scenario files shipped with the application and
exposes them read-only after full validation. Trusted storage of
untrusted-shaped data: every byte still passes the same defensive pipeline
live data would (§5.5) — size cap, raw-digest check, strict UTF-8,
duplicate-key-rejecting JSON parse, strict schema validation, entity-digest
verification, and cross-entity consistency checks. Tampered or inconsistent
content raises :class:`FixtureInvalidError`; it is never normalized,
re-digested, or partially returned.

No network, download, or generation path exists here by design.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from kalakal.fixtures.digest import fixture_entity_digest
from kalakal.fixtures.errors import FixtureInvalidError, ScenarioUnknownError
from kalakal.fixtures.models import FixtureManifest, FixtureScenario

MANIFEST_FILENAME: Final = "manifest.json"
MAX_FIXTURE_FILE_BYTES: Final = 1_048_576  # 1 MiB; far above any valid scenario.

_BUNDLE_ENTITY_KEYS: Final = ("candidate_market", "match_context", "market_snapshot")


class FixtureRepository:
    """Read-only access to one versioned synthetic fixture set.

    The constructor takes the explicit version directory (the directory
    containing ``manifest.json``); nothing depends on the process working
    directory. Every ``load_scenario`` call re-reads and re-validates from
    disk and returns a frozen model.
    """

    def __init__(self, version_dir: Path) -> None:
        # The supplied path is arbitrary caller input and is never echoed.
        try:
            self._version_dir = version_dir.resolve(strict=True)
        except OSError:
            raise FixtureInvalidError(
                "fixture version directory does not exist"
            ) from None
        if not self._version_dir.is_dir():
            raise FixtureInvalidError("fixture version path is not a directory")
        self._manifest = self._load_manifest()

    def list_scenarios(self) -> tuple[str, ...]:
        """Deterministic sorted tuple of the fixture set's scenario IDs."""
        return tuple(sorted(self._manifest.scenarios))

    def load_scenario(self, scenario_id: str) -> FixtureScenario:
        """Load, fully validate, and return one scenario by manifest ID."""
        entry = self._manifest.scenarios.get(scenario_id)
        if entry is None:
            # The supplied ID is arbitrary caller input and is never echoed.
            raise ScenarioUnknownError("unknown scenario ID")
        path = self._resolve_inside_version_dir(entry.filename)
        data = self._read_limited(path, entry.filename)
        raw_sha = hashlib.sha256(data).hexdigest()
        if raw_sha != entry.sha256:
            raise FixtureInvalidError(
                f"scenario file {entry.filename!r} does not match its "
                "manifest sha256 digest"
            )
        raw_object, text = self._decode_json_object(data, entry.filename)
        try:
            scenario = FixtureScenario.model_validate_json(text)
        except ValidationError as exc:
            raise FixtureInvalidError(
                f"scenario file {entry.filename!r} failed schema validation: "
                + _summarize_validation_error(exc)
            ) from None
        self._verify_entity_digests(raw_object, entry.filename)
        if scenario.scenario_id != scenario_id:
            raise FixtureInvalidError(
                f"scenario file {entry.filename!r} declares scenario ID "
                f"{scenario.scenario_id!r}, expected {_bounded(scenario_id)!r}"
            )
        if (
            scenario.provenance.fixture_set_id != self._manifest.fixture_set_id
            or scenario.provenance.fixture_set_version
            != self._manifest.fixture_set_version
        ):
            raise FixtureInvalidError(
                f"scenario file {entry.filename!r} provenance does not match "
                "the manifest fixture-set ID and version"
            )
        return scenario

    def _load_manifest(self) -> FixtureManifest:
        path = self._resolve_inside_version_dir(MANIFEST_FILENAME)
        data = self._read_limited(path, MANIFEST_FILENAME)
        _, text = self._decode_json_object(data, MANIFEST_FILENAME)
        try:
            manifest = FixtureManifest.model_validate_json(text)
        except ValidationError as exc:
            raise FixtureInvalidError(
                "manifest failed schema validation: " + _summarize_validation_error(exc)
            ) from None
        if manifest.fixture_set_version != self._version_dir.name:
            # Neither the manifest value nor the caller-supplied directory
            # name is echoed.
            raise FixtureInvalidError(
                "manifest fixture_set_version does not match the version directory"
            )
        return manifest

    def _resolve_inside_version_dir(self, filename: str) -> Path:
        # Filenames come only from the validated manifest pattern (no path
        # separators, no dots beyond the .json suffix); this containment
        # check is defense in depth and also rejects escaping symlinks.
        try:
            resolved = (self._version_dir / filename).resolve(strict=True)
        except OSError:
            raise FixtureInvalidError(
                f"fixture file is missing: {_bounded(filename)!r}"
            ) from None
        if resolved.parent != self._version_dir:
            raise FixtureInvalidError(
                f"fixture file {_bounded(filename)!r} escapes the version directory"
            )
        return resolved

    def _read_limited(self, path: Path, filename: str) -> bytes:
        try:
            with path.open("rb") as handle:
                data = handle.read(MAX_FIXTURE_FILE_BYTES + 1)
        except OSError:
            raise FixtureInvalidError(
                f"fixture file could not be read: {filename!r}"
            ) from None
        if len(data) > MAX_FIXTURE_FILE_BYTES:
            raise FixtureInvalidError(
                f"fixture file {filename!r} exceeds the "
                f"{MAX_FIXTURE_FILE_BYTES}-byte limit"
            )
        return data

    def _decode_json_object(
        self, data: bytes, filename: str
    ) -> tuple[dict[str, object], str]:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            raise FixtureInvalidError(
                f"fixture file {filename!r} is not valid UTF-8"
            ) from None
        try:
            raw = json.loads(
                text,
                object_pairs_hook=_reject_duplicate_keys,
                parse_float=_reject_float,
                parse_constant=_reject_constant,
            )
        except ValueError as exc:  # includes JSONDecodeError
            raise FixtureInvalidError(
                f"fixture file {filename!r} is not valid JSON: {_bounded(str(exc))}"
            ) from None
        if not isinstance(raw, dict):
            raise FixtureInvalidError(
                f"fixture file {filename!r} must contain a JSON object"
            )
        return raw, text

    def _verify_entity_digests(
        self, raw_object: dict[str, object], filename: str
    ) -> None:
        # Digests are verified over the raw parsed JSON, against the declared
        # values; nothing is ever silently re-digested. Shape errors cannot
        # normally occur after schema validation and are treated as tampering.
        structure_error = FixtureInvalidError(
            f"fixture file {filename!r} has an invalid entity-digest structure"
        )
        entities: list[tuple[str, dict[str, object]]] = [("scenario", raw_object)]
        candidates = raw_object.get("candidates")
        if not isinstance(candidates, list):
            raise structure_error
        for index, bundle in enumerate(candidates):
            if not isinstance(bundle, dict):
                raise structure_error
            for key in _BUNDLE_ENTITY_KEYS:
                entity = bundle.get(key)
                if not isinstance(entity, dict):
                    raise structure_error
                entities.append((f"candidates[{index}].{key}", entity))
        for label, entity in entities:
            provenance = entity.get("provenance")
            if not isinstance(provenance, dict):
                raise structure_error
            declared = provenance.get("content_digest")
            try:
                recomputed = fixture_entity_digest(entity)
            except ValueError:
                raise structure_error from None
            if recomputed != declared:
                raise FixtureInvalidError(
                    f"content digest mismatch for {label} in {filename!r}"
                )


def _reject_duplicate_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            # The key itself is raw file content and is never echoed.
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_float(value: str) -> object:
    raise ValueError("float values are not permitted in fixture content")


def _reject_constant(value: str) -> object:
    raise ValueError("non-finite JSON constants are not permitted")


def _summarize_validation_error(exc: ValidationError) -> str:
    # Error locations and types only — never echoed input values. Two loc
    # shapes carry raw input keys rather than schema names and are masked:
    # the unknown field of an extra_forbidden error, and the invalid mapping
    # key preceding pydantic's "[key]" marker.
    parts = []
    for error in exc.errors()[:3]:
        components = [
            str(item) if isinstance(item, int) else item for item in error["loc"]
        ]
        if error["type"] == "extra_forbidden" and components:
            components[-1] = "<unknown-field>"
        for index in range(len(components) - 1):
            if components[index + 1] == "[key]":
                components[index] = "<invalid-key>"
        parts.append(".".join(components) + ": " + error["type"])
    summary = f"{exc.error_count()} error(s): " + "; ".join(parts)
    return _bounded(summary)


def _bounded(text: str, limit: int = 200) -> str:
    return text if len(text) <= limit else text[:limit] + "…"
