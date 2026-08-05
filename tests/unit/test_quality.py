"""Unit tests for the DataQuality block and typed conflicts (§6.2.12)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kalakal.domain import DataConflict, DataQuality, EvidenceRef
from tests.unit import factories as f


class TestDataQuality:
    def test_complete_valid(self) -> None:
        quality = f.complete_quality()
        assert quality.is_complete is True

    def test_incomplete_with_missing_field_valid(self) -> None:
        quality = DataQuality(
            is_complete=False,
            missing_fields=("yes_team_rating",),
            conflicts=(),
        )
        assert quality.missing_fields == ("yes_team_rating",)

    def test_incomplete_with_conflict_only_valid(self) -> None:
        quality = DataQuality(
            is_complete=False,
            missing_fields=(),
            conflicts=(f.make_conflict("patch_label"),),
        )
        assert len(quality.conflicts) == 1

    def test_complete_with_missing_field_rejected(self) -> None:
        with pytest.raises(ValidationError, match="is_complete=true"):
            DataQuality(
                is_complete=True,
                missing_fields=("yes_team_rating",),
                conflicts=(),
            )

    def test_complete_with_conflict_rejected(self) -> None:
        with pytest.raises(ValidationError, match="is_complete=true"):
            DataQuality(
                is_complete=True,
                missing_fields=(),
                conflicts=(f.make_conflict("patch_label"),),
            )

    def test_incomplete_without_gap_rejected(self) -> None:
        with pytest.raises(ValidationError, match="is_complete=false"):
            DataQuality(is_complete=False, missing_fields=(), conflicts=())

    def test_duplicate_missing_paths_rejected(self) -> None:
        with pytest.raises(ValidationError, match="duplicate"):
            DataQuality(
                is_complete=False,
                missing_fields=("yes_team_rating", "yes_team_rating"),
                conflicts=(),
            )

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DataQuality(
                is_complete=True,
                missing_fields=(),
                conflicts=(),
                notes="extra",  # type: ignore[call-arg]
            )

    @pytest.mark.parametrize("value", [1, 0, "true", None])
    def test_is_complete_requires_bool(self, value: object) -> None:
        with pytest.raises(ValidationError):
            DataQuality(is_complete=value, missing_fields=(), conflicts=())  # type: ignore[arg-type]

    @pytest.mark.parametrize("path", ["", "Team_A", "1rating", "a.b", "x" * 101])
    def test_malformed_field_paths_rejected(self, path: str) -> None:
        with pytest.raises(ValidationError):
            DataQuality(is_complete=False, missing_fields=(path,), conflicts=())


class TestDataConflict:
    def test_valid(self) -> None:
        conflict = f.make_conflict("patch_label")
        assert conflict.field_path == "patch_label"
        assert len(conflict.evidence_refs) == 1

    def test_empty_evidence_refs_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DataConflict(
                field_path="patch_label",
                description="Sources disagree.",
                evidence_refs=(),
            )

    def test_missing_field_path_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DataConflict(
                description="Sources disagree.",  # type: ignore[call-arg]
                evidence_refs=(EvidenceRef(kind="market", ref_id="mkt-1"),),
            )

    def test_overlong_description_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DataConflict(
                field_path="patch_label",
                description="x" * 501,
                evidence_refs=(EvidenceRef(kind="market", ref_id="mkt-1"),),
            )

    def test_empty_description_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DataConflict(
                field_path="patch_label",
                description="",
                evidence_refs=(EvidenceRef(kind="market", ref_id="mkt-1"),),
            )

    def test_arbitrary_payload_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DataConflict(
                field_path="patch_label",
                description="Sources disagree.",
                evidence_refs=(EvidenceRef(kind="market", ref_id="mkt-1"),),
                payload={"raw": "blob"},  # type: ignore[call-arg]
            )
