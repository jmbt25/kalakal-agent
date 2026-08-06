"""Slice 3 tests: every shipped fixture file is valid, synthetic, digest-true.

These tests read the shipped ``fixtures/<version>/`` set directly and never
modify it; tamper and error paths live in ``test_fixture_repository.py``.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pytest

from kalakal.domain import SYNTHETIC_MARKET_LINK_PREFIX, find_sensitive_content
from kalakal.fixtures import FixtureRepository, FixtureScenario, fixture_entity_digest
from tests.unit.fixture_helpers import (
    BUNDLE_ENTITY_KEYS,
    REQUIRED_SCENARIO_IDS,
    SHIPPED_FEE_MODEL_VERSION,
    SHIPPED_FEE_RATE_PPM,
    SHIPPED_FIXTURE_SET_ID,
    SHIPPED_FIXTURE_SET_VERSION,
    read_json,
    scenario_path,
    shipped_version_dir,
)

UTC_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
ISO_DATE_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}T")

EXPECTED_METADATA: dict[str, tuple[str, str | None]] = {
    "clear-edge": ("completed_proceed", None),
    "thin-edge": ("policy_no_bet", "POLICY_INSUFFICIENT_NET_EDGE"),
    "conflicting-evidence": ("agent_abstention", "CONFLICTING_EVIDENCE"),
    "stale-data": ("policy_no_bet", "POLICY_STALE_DATA"),
    "outside-entry-band": ("policy_no_bet", "POLICY_OUTSIDE_ENTRY_BAND"),
    "no-valid-candidates": ("orchestrator_abstention", "NO_VALID_CANDIDATES"),
}


@pytest.fixture(scope="module")
def repo() -> FixtureRepository:
    return FixtureRepository(shipped_version_dir())


def load(repo: FixtureRepository, scenario_id: str) -> FixtureScenario:
    return repo.load_scenario(scenario_id)


def _walk_json(value: object) -> list[object]:
    found: list[object] = [value]
    if isinstance(value, dict):
        for item in value.values():
            found.extend(_walk_json(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_walk_json(item))
    return found


class TestManifestAndListing:
    def test_manifest_validates_and_lists_exactly_the_required_ids(
        self, repo: FixtureRepository
    ) -> None:
        assert repo.list_scenarios() == tuple(sorted(REQUIRED_SCENARIO_IDS))

    def test_manifest_maps_each_scenario_to_its_own_file(self) -> None:
        manifest = read_json(shipped_version_dir() / "manifest.json")
        assert manifest["fixture_set_id"] == SHIPPED_FIXTURE_SET_ID
        assert manifest["fixture_set_version"] == SHIPPED_FIXTURE_SET_VERSION
        for scenario_id, entry in manifest["scenarios"].items():
            assert entry["filename"] == f"{scenario_id}.json"

    def test_raw_file_digests_match_the_manifest(self) -> None:
        manifest = read_json(shipped_version_dir() / "manifest.json")
        for entry in manifest["scenarios"].values():
            data = (shipped_version_dir() / entry["filename"]).read_bytes()
            assert hashlib.sha256(data).hexdigest() == entry["sha256"]


class TestEveryShippedFile:
    @pytest.mark.parametrize("scenario_id", REQUIRED_SCENARIO_IDS)
    def test_scenario_parses_and_validates(
        self, repo: FixtureRepository, scenario_id: str
    ) -> None:
        scenario = load(repo, scenario_id)
        assert scenario.scenario_id == scenario_id
        assert scenario.candidates

    def test_files_end_with_newline_and_are_valid_utf8(self) -> None:
        files = sorted(shipped_version_dir().glob("*.json"))
        assert len(files) == len(REQUIRED_SCENARIO_IDS) + 1
        for path in files:
            data = path.read_bytes()
            assert data.endswith(b"\n"), path.name
            data.decode("utf-8")

    def test_files_are_lf_only(self) -> None:
        # The manifest hashes exact bytes; .gitattributes pins fixture JSON
        # to LF so checkouts on any platform reproduce these digests.
        for path in sorted(shipped_version_dir().glob("*.json")):
            assert b"\r" not in path.read_bytes(), path.name

    @pytest.mark.parametrize("scenario_id", REQUIRED_SCENARIO_IDS)
    def test_entity_digests_recompute_exactly(self, scenario_id: str) -> None:
        raw = read_json(scenario_path(shipped_version_dir(), scenario_id))
        entities: list[dict[str, Any]] = [raw]
        for bundle in raw["candidates"]:
            entities.extend(bundle[key] for key in BUNDLE_ENTITY_KEYS)
        for entity in entities:
            declared = entity["provenance"]["content_digest"]
            assert fixture_entity_digest(entity) == declared

    def test_digest_matches_independent_reimplementation(self) -> None:
        # Recompute one digest without the digest module: canonical UTF-8
        # JSON, sorted keys, compact separators, array order preserved,
        # minus only the entity's own provenance.content_digest.
        raw = read_json(scenario_path(shipped_version_dir(), "clear-edge"))
        entity = json.loads(json.dumps(raw["candidates"][0]["candidate_market"]))
        declared = entity["provenance"].pop("content_digest")
        encoded = json.dumps(
            entity, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        assert hashlib.sha256(encoded).hexdigest() == declared


class TestSyntheticProvenance:
    @pytest.mark.parametrize("scenario_id", REQUIRED_SCENARIO_IDS)
    def test_every_provenance_block_is_synthetic_and_version_consistent(
        self, scenario_id: str
    ) -> None:
        raw = read_json(scenario_path(shipped_version_dir(), scenario_id))
        provenances = [
            node
            for node in _walk_json(raw)
            if isinstance(node, dict) and "fixture_set_version" in node
        ]
        assert provenances
        for block in provenances:
            assert block["fixture_set_id"] == SHIPPED_FIXTURE_SET_ID
            assert block["fixture_set_version"] == SHIPPED_FIXTURE_SET_VERSION
            assert block["is_synthetic"] is True

    @pytest.mark.parametrize("scenario_id", REQUIRED_SCENARIO_IDS)
    def test_market_links_use_the_synthetic_invalid_domain(
        self, repo: FixtureRepository, scenario_id: str
    ) -> None:
        scenario = load(repo, scenario_id)
        for bundle in scenario.candidates:
            link = bundle.candidate_market.market_link
            assert link.startswith(SYNTHETIC_MARKET_LINK_PREFIX)
            assert ".invalid/" in link

    @pytest.mark.parametrize("scenario_id", REQUIRED_SCENARIO_IDS)
    def test_all_timestamps_are_fixed_utc(self, scenario_id: str) -> None:
        raw = read_json(scenario_path(shipped_version_dir(), scenario_id))
        timestamps = [
            node
            for node in _walk_json(raw)
            if isinstance(node, str) and ISO_DATE_PREFIX.match(node)
        ]
        assert timestamps
        for value in timestamps:
            assert UTC_TIMESTAMP.match(value), value

    @pytest.mark.parametrize("scenario_id", REQUIRED_SCENARIO_IDS)
    def test_no_credential_shaped_or_personal_data(
        self, repo: FixtureRepository, scenario_id: str
    ) -> None:
        assert find_sensitive_content(load(repo, scenario_id)) is None
        text = scenario_path(shipped_version_dir(), scenario_id).read_text(
            encoding="utf-8"
        )
        assert "@" not in text

    def test_manifest_has_no_sensitive_content(self) -> None:
        text = (shipped_version_dir() / "manifest.json").read_text(encoding="utf-8")
        assert "@" not in text


class TestScenarioMetadata:
    @pytest.mark.parametrize(
        ("scenario_id", "expected"),
        [(sid, meta) for sid, meta in EXPECTED_METADATA.items()],
    )
    def test_expected_outcome_class_and_reason_code(
        self,
        repo: FixtureRepository,
        scenario_id: str,
        expected: tuple[str, str | None],
    ) -> None:
        scenario = load(repo, scenario_id)
        assert scenario.expected_outcome_class == expected[0]
        assert scenario.expected_reason_code == expected[1]

    @pytest.mark.parametrize("scenario_id", REQUIRED_SCENARIO_IDS)
    def test_versioned_synthetic_fee_configuration(
        self, repo: FixtureRepository, scenario_id: str
    ) -> None:
        scenario = load(repo, scenario_id)
        assert scenario.fee_rate_ppm == SHIPPED_FEE_RATE_PPM
        assert scenario.fee_model_version == SHIPPED_FEE_MODEL_VERSION
        for bundle in scenario.candidates:
            assert bundle.market_snapshot.fee_model_version == SHIPPED_FEE_MODEL_VERSION

    @pytest.mark.parametrize("scenario_id", REQUIRED_SCENARIO_IDS)
    def test_every_candidate_is_open_with_an_explicit_side(
        self, repo: FixtureRepository, scenario_id: str
    ) -> None:
        scenario = load(repo, scenario_id)
        for bundle in scenario.candidates:
            assert bundle.candidate_market.status == "open"
            assert bundle.market_snapshot.side == bundle.evaluation_side


def test_shipped_directory_matches_the_recorded_version() -> None:
    assert shipped_version_dir().name == SHIPPED_FIXTURE_SET_VERSION
    assert isinstance(shipped_version_dir(), Path)
