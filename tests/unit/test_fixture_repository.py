"""Slice 3 tests: fixture-repository behavior, typed errors, tamper defense.

All tamper and error-path tests operate on temporary copies produced by
``fixture_helpers``; the shipped fixture set is never modified.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from kalakal.domain import find_sensitive_content
from kalakal.fixtures import (
    MAX_ERROR_MESSAGE_LENGTH,
    MAX_FIXTURE_FILE_BYTES,
    FixtureInvalidError,
    FixtureRepository,
    FixtureRepositoryError,
    ScenarioUnknownError,
)
from tests.unit.fixture_helpers import (
    REQUIRED_SCENARIO_IDS,
    SHIPPED_FIXTURE_SET_VERSION,
    copy_fixture_set,
    scenario_path,
    shipped_version_dir,
    tamper_manifest,
    tamper_scenario,
    write_json,
    write_scenario_bytes,
)


def _dir_digest(version_dir: Path) -> dict[str, str]:
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(version_dir.glob("*.json"))
    }


class TestReadPaths:
    def test_listing_is_deterministic_and_sorted(self, tmp_path: Path) -> None:
        repo = FixtureRepository(copy_fixture_set(tmp_path))
        listing = repo.list_scenarios()
        assert listing == tuple(sorted(REQUIRED_SCENARIO_IDS))
        assert repo.list_scenarios() == listing

    @pytest.mark.parametrize("scenario_id", REQUIRED_SCENARIO_IDS)
    def test_load_by_id_succeeds(self, tmp_path: Path, scenario_id: str) -> None:
        repo = FixtureRepository(copy_fixture_set(tmp_path))
        scenario = repo.load_scenario(scenario_id)
        assert scenario.scenario_id == scenario_id

    def test_repeated_loads_are_equal_and_frozen(self, tmp_path: Path) -> None:
        repo = FixtureRepository(copy_fixture_set(tmp_path))
        first = repo.load_scenario("clear-edge")
        second = repo.load_scenario("clear-edge")
        assert first == second
        assert first is not second
        with pytest.raises(ValidationError):
            first.scenario_id = "tampered"
        with pytest.raises(ValidationError):
            first.candidates[0].candidate_market.status = "closed"

    def test_loading_never_mutates_the_fixture_files(self, tmp_path: Path) -> None:
        version_dir = copy_fixture_set(tmp_path)
        before = _dir_digest(version_dir)
        repo = FixtureRepository(version_dir)
        for scenario_id in repo.list_scenarios():
            repo.load_scenario(scenario_id)
        assert _dir_digest(version_dir) == before

    def test_unknown_scenario_is_a_typed_permanent_error(self, tmp_path: Path) -> None:
        repo = FixtureRepository(copy_fixture_set(tmp_path))
        with pytest.raises(ScenarioUnknownError) as excinfo:
            repo.load_scenario("does-not-exist")
        error = excinfo.value
        assert isinstance(error, FixtureRepositoryError)
        assert error.reason_code == "SCENARIO_UNKNOWN"
        assert error.classification == "permanent"
        # The arbitrary caller-supplied ID is never echoed back.
        assert error.message == "unknown scenario ID"
        assert "does-not-exist" not in error.message
        assert str(error) == error.message


class TestManifestFailures:
    def test_missing_version_directory(self, tmp_path: Path) -> None:
        with pytest.raises(FixtureInvalidError):
            FixtureRepository(tmp_path / "no-such-version")

    def test_missing_manifest_file(self, tmp_path: Path) -> None:
        version_dir = copy_fixture_set(tmp_path)
        (version_dir / "manifest.json").unlink()
        with pytest.raises(FixtureInvalidError):
            FixtureRepository(version_dir)

    def test_malformed_manifest_json(self, tmp_path: Path) -> None:
        version_dir = copy_fixture_set(tmp_path)
        (version_dir / "manifest.json").write_bytes(b'{"broken": \n')
        with pytest.raises(FixtureInvalidError):
            FixtureRepository(version_dir)

    def test_schema_invalid_manifest(self, tmp_path: Path) -> None:
        version_dir = copy_fixture_set(tmp_path)

        def drop_id(manifest: dict[str, Any]) -> None:
            del manifest["fixture_set_id"]

        tamper_manifest(version_dir, drop_id)
        with pytest.raises(FixtureInvalidError) as excinfo:
            FixtureRepository(version_dir)
        assert excinfo.value.reason_code == "FIXTURE_INVALID"

    @pytest.mark.parametrize(
        "filename",
        ["../escape.json", "..\\escape.json", "/abs/escape.json", "C:/escape.json"],
    )
    def test_traversal_and_absolute_manifest_paths_rejected(
        self, tmp_path: Path, filename: str
    ) -> None:
        version_dir = copy_fixture_set(tmp_path)

        def set_filename(manifest: dict[str, Any]) -> None:
            manifest["scenarios"]["clear-edge"]["filename"] = filename

        tamper_manifest(version_dir, set_filename)
        with pytest.raises(FixtureInvalidError):
            FixtureRepository(version_dir)

    def test_version_directory_name_must_match_manifest_version(
        self, tmp_path: Path
    ) -> None:
        version_dir = copy_fixture_set(tmp_path, version="9999.01.01.9")
        with pytest.raises(FixtureInvalidError) as excinfo:
            FixtureRepository(version_dir)
        assert "version" in excinfo.value.message


class TestScenarioFileFailures:
    def test_missing_scenario_file(self, tmp_path: Path) -> None:
        version_dir = copy_fixture_set(tmp_path)
        scenario_path(version_dir, "thin-edge").unlink()
        repo = FixtureRepository(version_dir)
        with pytest.raises(FixtureInvalidError):
            repo.load_scenario("thin-edge")

    def test_raw_file_digest_mismatch(self, tmp_path: Path) -> None:
        version_dir = copy_fixture_set(tmp_path)
        path = scenario_path(version_dir, "clear-edge")
        path.write_bytes(path.read_bytes().replace(b'"best_of": 3', b'"best_of": 5'))
        repo = FixtureRepository(version_dir)
        with pytest.raises(FixtureInvalidError) as excinfo:
            repo.load_scenario("clear-edge")
        assert "sha256" in excinfo.value.message

    def test_entity_digest_mismatch_after_tamper(self, tmp_path: Path) -> None:
        version_dir = copy_fixture_set(tmp_path)

        def change_event(scenario: dict[str, Any]) -> None:
            market = scenario["candidates"][0]["candidate_market"]
            market["event_name"] = "Tampered Synthetic Event"

        # reseal=False keeps the stale digests; the manifest sha256 is
        # refreshed so the entity-digest layer is what must catch it.
        tamper_scenario(version_dir, "clear-edge", change_event, reseal=False)
        repo = FixtureRepository(version_dir)
        with pytest.raises(FixtureInvalidError) as excinfo:
            repo.load_scenario("clear-edge")
        assert "digest mismatch" in excinfo.value.message

    def test_duplicate_json_key_rejected(self, tmp_path: Path) -> None:
        version_dir = copy_fixture_set(tmp_path)
        write_scenario_bytes(
            version_dir,
            "clear-edge",
            b'{"schema_version": "1", "schema_version": "1"}\n',
        )
        repo = FixtureRepository(version_dir)
        with pytest.raises(FixtureInvalidError) as excinfo:
            repo.load_scenario("clear-edge")
        assert "duplicate" in excinfo.value.message

    def test_malformed_json_rejected(self, tmp_path: Path) -> None:
        version_dir = copy_fixture_set(tmp_path)
        write_scenario_bytes(version_dir, "clear-edge", b'{"scenario_id": \n')
        repo = FixtureRepository(version_dir)
        with pytest.raises(FixtureInvalidError):
            repo.load_scenario("clear-edge")

    def test_non_object_json_rejected(self, tmp_path: Path) -> None:
        version_dir = copy_fixture_set(tmp_path)
        write_scenario_bytes(version_dir, "clear-edge", b'["not", "an", "object"]\n')
        repo = FixtureRepository(version_dir)
        with pytest.raises(FixtureInvalidError):
            repo.load_scenario("clear-edge")

    def test_invalid_utf8_rejected(self, tmp_path: Path) -> None:
        version_dir = copy_fixture_set(tmp_path)
        write_scenario_bytes(version_dir, "clear-edge", b'{"a": "\xff\xfe"}\n')
        repo = FixtureRepository(version_dir)
        with pytest.raises(FixtureInvalidError) as excinfo:
            repo.load_scenario("clear-edge")
        assert "UTF-8" in excinfo.value.message

    def test_oversize_file_rejected(self, tmp_path: Path) -> None:
        version_dir = copy_fixture_set(tmp_path)
        write_scenario_bytes(
            version_dir, "clear-edge", b"x" * (MAX_FIXTURE_FILE_BYTES + 1)
        )
        repo = FixtureRepository(version_dir)
        with pytest.raises(FixtureInvalidError) as excinfo:
            repo.load_scenario("clear-edge")
        assert "limit" in excinfo.value.message

    def test_schema_invalid_scenario_rejected(self, tmp_path: Path) -> None:
        version_dir = copy_fixture_set(tmp_path)

        def break_status(scenario: dict[str, Any]) -> None:
            scenario["candidates"][0]["candidate_market"]["status"] = "paused"

        tamper_scenario(version_dir, "clear-edge", break_status)
        repo = FixtureRepository(version_dir)
        with pytest.raises(FixtureInvalidError) as excinfo:
            repo.load_scenario("clear-edge")
        assert "schema validation" in excinfo.value.message


class TestConsistencyFailures:
    def test_fixture_set_version_mismatch_between_manifest_and_scenario(
        self, tmp_path: Path
    ) -> None:
        # A consistent manifest + directory using a different version than
        # the scenario provenance blocks must be rejected at load time.
        version_dir = copy_fixture_set(tmp_path, version="2026.09.01.1")

        def bump_version(manifest: dict[str, Any]) -> None:
            manifest["fixture_set_version"] = "2026.09.01.1"

        tamper_manifest(version_dir, bump_version)
        repo = FixtureRepository(version_dir)
        with pytest.raises(FixtureInvalidError) as excinfo:
            repo.load_scenario("clear-edge")
        assert "provenance" in excinfo.value.message

    def test_fixture_set_id_mismatch_between_manifest_and_scenario(
        self, tmp_path: Path
    ) -> None:
        version_dir = copy_fixture_set(tmp_path)

        def change_id(manifest: dict[str, Any]) -> None:
            manifest["fixture_set_id"] = "some-other-fixture-set"

        tamper_manifest(version_dir, change_id)
        repo = FixtureRepository(version_dir)
        with pytest.raises(FixtureInvalidError):
            repo.load_scenario("clear-edge")

    def test_scenario_id_mismatch_with_manifest_key(self, tmp_path: Path) -> None:
        version_dir = copy_fixture_set(tmp_path)

        def rename(scenario: dict[str, Any]) -> None:
            scenario["scenario_id"] = "thin-edge"

        tamper_scenario(version_dir, "clear-edge", rename)
        repo = FixtureRepository(version_dir)
        with pytest.raises(FixtureInvalidError) as excinfo:
            repo.load_scenario("clear-edge")
        assert "declares scenario ID" in excinfo.value.message

    def test_cross_entity_side_mismatch(self, tmp_path: Path) -> None:
        version_dir = copy_fixture_set(tmp_path)

        def flip_side(scenario: dict[str, Any]) -> None:
            scenario["candidates"][0]["market_snapshot"]["side"] = "no"

        tamper_scenario(version_dir, "clear-edge", flip_side)
        repo = FixtureRepository(version_dir)
        with pytest.raises(FixtureInvalidError):
            repo.load_scenario("clear-edge")

    def test_cross_entity_market_id_mismatch(self, tmp_path: Path) -> None:
        version_dir = copy_fixture_set(tmp_path)

        def change_market_ref(scenario: dict[str, Any]) -> None:
            scenario["candidates"][0]["match_context"]["market_id"] = "syn-mkt-other"

        tamper_scenario(version_dir, "clear-edge", change_market_ref)
        repo = FixtureRepository(version_dir)
        with pytest.raises(FixtureInvalidError):
            repo.load_scenario("clear-edge")

    def test_fee_model_reference_mismatch(self, tmp_path: Path) -> None:
        version_dir = copy_fixture_set(tmp_path)

        def change_fee_model(scenario: dict[str, Any]) -> None:
            scenario["fee_model_version"] = "synthetic-fee-2"

        tamper_scenario(version_dir, "clear-edge", change_fee_model)
        repo = FixtureRepository(version_dir)
        with pytest.raises(FixtureInvalidError):
            repo.load_scenario("clear-edge")

    def test_duplicate_market_ids_rejected(self, tmp_path: Path) -> None:
        version_dir = copy_fixture_set(tmp_path)

        def duplicate_market(scenario: dict[str, Any]) -> None:
            first = scenario["candidates"][0]["candidate_market"]["market_id"]
            second = scenario["candidates"][1]
            second["candidate_market"]["market_id"] = first
            second["match_context"]["market_id"] = first
            second["market_snapshot"]["market_id"] = first

        tamper_scenario(version_dir, "no-valid-candidates", duplicate_market)
        repo = FixtureRepository(version_dir)
        with pytest.raises(FixtureInvalidError):
            repo.load_scenario("no-valid-candidates")

    def test_entity_provenance_version_mismatch_within_scenario(
        self, tmp_path: Path
    ) -> None:
        version_dir = copy_fixture_set(tmp_path)

        def change_entity_version(scenario: dict[str, Any]) -> None:
            provenance = scenario["candidates"][0]["match_context"]["provenance"]
            provenance["fixture_set_version"] = "2026.08.06.2"

        tamper_scenario(version_dir, "clear-edge", change_entity_version)
        repo = FixtureRepository(version_dir)
        with pytest.raises(FixtureInvalidError):
            repo.load_scenario("clear-edge")


class TestErrorRedaction:
    """No error path may expose raw file content or arbitrary caller input.

    Sensitive-looking inputs are assembled from harmless fragments at
    runtime so no complete token-shaped literal exists in the source.
    """

    @staticmethod
    def _token() -> str:
        return "sk-" + "abcd1234" * 3

    def test_duplicate_credential_shaped_key_rejected_without_echo(
        self, tmp_path: Path
    ) -> None:
        version_dir = copy_fixture_set(tmp_path)
        key = self._token()
        value = "hunter" + "2" * 10
        payload = f'{{"{key}": "{value}", "{key}": "x"}}\n'.encode()
        write_scenario_bytes(version_dir, "clear-edge", payload)
        repo = FixtureRepository(version_dir)
        with pytest.raises(FixtureInvalidError) as excinfo:
            repo.load_scenario("clear-edge")
        error = excinfo.value
        assert error.reason_code == "FIXTURE_INVALID"
        assert "duplicate" in error.message
        assert key not in error.message
        assert value not in error.message
        assert key not in str(error)
        assert value not in str(error)
        assert find_sensitive_content(error.message) is None
        assert len(error.message) <= MAX_ERROR_MESSAGE_LENGTH

    def test_unknown_scenario_id_with_sensitive_shape_is_not_echoed(
        self, tmp_path: Path
    ) -> None:
        repo = FixtureRepository(copy_fixture_set(tmp_path))
        email_shaped = "agent" + "@" + "synthetic-host.example"
        for bad_id in (self._token(), email_shaped):
            with pytest.raises(ScenarioUnknownError) as excinfo:
                repo.load_scenario(bad_id)
            error = excinfo.value
            assert error.message == "unknown scenario ID"
            assert bad_id not in str(error)
            assert find_sensitive_content(error.message) is None

    def test_direct_construction_redacts_sensitive_shaped_detail(self) -> None:
        token = self._token()
        for error in (
            FixtureInvalidError("tampered file mentions " + token),
            ScenarioUnknownError("lookup failed for " + token),
        ):
            assert token not in error.message
            assert token not in str(error)
            assert "redacted" in error.message
            assert str(error) == error.message
            assert find_sensitive_content(error.message) is None
            assert len(error.message) <= MAX_ERROR_MESSAGE_LENGTH
        assert FixtureInvalidError("x").reason_code == "FIXTURE_INVALID"
        assert FixtureInvalidError("x").classification == "permanent"
        assert ScenarioUnknownError("x").reason_code == "SCENARIO_UNKNOWN"
        assert ScenarioUnknownError("x").classification == "permanent"

    def test_ordinary_safe_errors_remain_descriptive(self) -> None:
        detail = "scenario file 'clear-edge.json' is not valid UTF-8"
        error = FixtureInvalidError(detail)
        assert error.message == detail
        assert str(error) == detail

    def test_messages_are_bounded_after_sanitization(self) -> None:
        error = FixtureInvalidError("safe detail. " * 200)
        assert len(error.message) <= MAX_ERROR_MESSAGE_LENGTH
        assert error.message.endswith("[truncated]")
        assert str(error) == error.message

    def test_long_uniform_runs_are_redacted_not_truncated(self) -> None:
        # A 2000-char base58-shaped run trips the fail-closed scanner and
        # is replaced outright rather than merely shortened.
        error = FixtureInvalidError("x" * 2000)
        assert "redacted" in error.message
        assert len(error.message) <= MAX_ERROR_MESSAGE_LENGTH


class TestConstructorBoundaryRedaction:
    """Constructor-path errors never echo the caller-supplied path or the
    manifest version value, even when the leak would look innocuous."""

    @staticmethod
    def _assert_safe_invalid(error: FixtureInvalidError, expected: str) -> None:
        assert error.reason_code == "FIXTURE_INVALID"
        assert error.classification == "permanent"
        assert error.message == expected
        assert str(error) == error.message
        assert find_sensitive_content(error.message) is None
        assert len(error.message) <= MAX_ERROR_MESSAGE_LENGTH

    def test_missing_version_directory_does_not_echo_basename(
        self, tmp_path: Path
    ) -> None:
        private = "private-project-123"
        with pytest.raises(FixtureInvalidError) as excinfo:
            FixtureRepository(tmp_path / private)
        self._assert_safe_invalid(
            excinfo.value, "fixture version directory does not exist"
        )
        assert private not in str(excinfo.value)

    def test_non_directory_path_does_not_echo_basename(self, tmp_path: Path) -> None:
        private = "private-client-list"
        file_path = tmp_path / private
        file_path.write_bytes(b"{}\n")
        with pytest.raises(FixtureInvalidError) as excinfo:
            FixtureRepository(file_path)
        self._assert_safe_invalid(
            excinfo.value, "fixture version path is not a directory"
        )
        assert private not in str(excinfo.value)

    def test_version_mismatch_echoes_neither_version_string(
        self, tmp_path: Path
    ) -> None:
        private = "private-build-77"
        version_dir = copy_fixture_set(tmp_path, version=private)
        with pytest.raises(FixtureInvalidError) as excinfo:
            FixtureRepository(version_dir)
        self._assert_safe_invalid(
            excinfo.value,
            "manifest fixture_set_version does not match the version directory",
        )
        assert private not in str(excinfo.value)
        assert SHIPPED_FIXTURE_SET_VERSION not in str(excinfo.value)

    def test_unknown_json_field_name_is_not_echoed_in_schema_errors(
        self, tmp_path: Path
    ) -> None:
        version_dir = copy_fixture_set(tmp_path)
        private = "private_internal_note"

        def add_unknown_field(scenario: dict[str, Any]) -> None:
            scenario[private] = "should never be echoed"

        tamper_scenario(version_dir, "clear-edge", add_unknown_field)
        repo = FixtureRepository(version_dir)
        with pytest.raises(FixtureInvalidError) as excinfo:
            repo.load_scenario("clear-edge")
        error = excinfo.value
        assert "schema validation" in error.message
        assert private not in str(error)
        assert "should never be echoed" not in str(error)
        assert "<unknown-field>" in error.message

    def test_invalid_manifest_mapping_key_is_not_echoed(self, tmp_path: Path) -> None:
        version_dir = copy_fixture_set(tmp_path)
        private = "Private Client 7"

        def add_invalid_key(manifest: dict[str, Any]) -> None:
            manifest["scenarios"][private] = {
                "filename": "extra.json",
                "sha256": "0" * 64,
            }

        tamper_manifest(version_dir, add_invalid_key)
        with pytest.raises(FixtureInvalidError) as excinfo:
            FixtureRepository(version_dir)
        error = excinfo.value
        assert "schema validation" in error.message
        assert private not in str(error)
        assert "<invalid-key>" in error.message


def test_shipped_set_loads_via_an_explicit_path_only() -> None:
    # The constructor takes the explicit version directory; nothing depends
    # on the process working directory.
    repo = FixtureRepository(shipped_version_dir())
    assert shipped_version_dir().name == SHIPPED_FIXTURE_SET_VERSION
    assert len(repo.list_scenarios()) == len(REQUIRED_SCENARIO_IDS)


def test_write_json_helper_round_trips(tmp_path: Path) -> None:
    # Guard the tamper helper itself: LF-terminated UTF-8 with a trailing
    # newline, matching the shipped file conventions.
    target = tmp_path / "sample.json"
    write_json(target, {"a": 1})
    data = target.read_bytes()
    assert data == b'{\n  "a": 1\n}\n'
