"""Test-only helpers for locating, copying, and tampering with fixtures.

Tamper tests always operate on temporary copies; the shipped fixture files
are never modified. ``tamper_scenario`` refreshes the manifest sha256 (and,
by default, the entity digests) so tests can reach validation layers deeper
than the raw-byte digest check.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from kalakal.fixtures.digest import fixture_entity_digest

SHIPPED_FIXTURE_SET_ID = "kalakal-synthetic-dota-fixtures"
SHIPPED_FIXTURE_SET_VERSION = "2026.08.06.1"
SHIPPED_FEE_RATE_PPM = 10_000
SHIPPED_FEE_MODEL_VERSION = "synthetic-fee-1"

REQUIRED_SCENARIO_IDS = (
    "clear-edge",
    "thin-edge",
    "conflicting-evidence",
    "stale-data",
    "outside-entry-band",
    "no-valid-candidates",
)

BUNDLE_ENTITY_KEYS = ("candidate_market", "match_context", "market_snapshot")


def shipped_version_dir() -> Path:
    return (
        Path(__file__).resolve().parents[2] / "fixtures" / SHIPPED_FIXTURE_SET_VERSION
    )


def copy_fixture_set(
    tmp_path: Path, version: str = SHIPPED_FIXTURE_SET_VERSION
) -> Path:
    target = tmp_path / version
    shutil.copytree(shipped_version_dir(), target)
    return target


def read_json(path: Path) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))


def dump_json_bytes(doc: dict[str, Any]) -> bytes:
    return (json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def write_json(path: Path, doc: dict[str, Any]) -> None:
    path.write_bytes(dump_json_bytes(doc))


def scenario_path(version_dir: Path, scenario_id: str) -> Path:
    manifest = read_json(version_dir / "manifest.json")
    filename = cast("str", manifest["scenarios"][scenario_id]["filename"])
    return version_dir / filename


def write_scenario_bytes(version_dir: Path, scenario_id: str, data: bytes) -> None:
    """Replace a scenario file's bytes and refresh its manifest sha256."""
    manifest = read_json(version_dir / "manifest.json")
    entry = manifest["scenarios"][scenario_id]
    (version_dir / entry["filename"]).write_bytes(data)
    entry["sha256"] = hashlib.sha256(data).hexdigest()
    write_json(version_dir / "manifest.json", manifest)


def reseal_entity_digests(scenario: dict[str, Any]) -> None:
    """Recompute every entity digest bottom-up after a deliberate tamper."""
    for bundle in scenario["candidates"]:
        for key in BUNDLE_ENTITY_KEYS:
            entity = bundle[key]
            entity["provenance"]["content_digest"] = fixture_entity_digest(entity)
    scenario["provenance"]["content_digest"] = fixture_entity_digest(scenario)


def tamper_scenario(
    version_dir: Path,
    scenario_id: str,
    mutate: Callable[[dict[str, Any]], None],
    *,
    reseal: bool = True,
) -> None:
    """Mutate one scenario document in a copied fixture set.

    With ``reseal`` the entity digests are recomputed so validation reaches
    the layers beyond digest checking; without it the stale digests remain
    to trigger the entity-digest mismatch path. The manifest sha256 is
    always refreshed.
    """
    scenario = read_json(scenario_path(version_dir, scenario_id))
    mutate(scenario)
    if reseal:
        reseal_entity_digests(scenario)
    write_scenario_bytes(version_dir, scenario_id, dump_json_bytes(scenario))


def tamper_manifest(
    version_dir: Path, mutate: Callable[[dict[str, Any]], None]
) -> None:
    manifest = read_json(version_dir / "manifest.json")
    mutate(manifest)
    write_json(version_dir / "manifest.json", manifest)
