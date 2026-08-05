"""DataQuality block and typed conflicts (architecture.md §6.2.12).

Structural invalidity is a schema failure, never incompleteness. This block
only lets *structurally valid* entities declare genuinely unavailable
allowlisted evidence fields or typed conflicts.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, model_validator

from kalakal.domain.primitives import (
    EvidenceRef,
    FieldPath,
    MediumText,
    StrictModel,
)


class DataConflict(StrictModel):
    """Typed, bounded, audit-safe conflict entry — never untyped prose."""

    field_path: FieldPath
    description: MediumText
    evidence_refs: Annotated[tuple[EvidenceRef, ...], Field(min_length=1, max_length=8)]


class DataQuality(StrictModel):
    """Completeness and conflict declaration for an evidence-bearing contract."""

    is_complete: bool
    missing_fields: Annotated[tuple[FieldPath, ...], Field(max_length=8)]
    conflicts: Annotated[tuple[DataConflict, ...], Field(max_length=16)]

    @model_validator(mode="after")
    def _check_consistency(self) -> DataQuality:
        if len(set(self.missing_fields)) != len(self.missing_fields):
            raise ValueError("missing_fields must not contain duplicate paths")
        has_gap = bool(self.missing_fields) or bool(self.conflicts)
        if self.is_complete and has_gap:
            raise ValueError(
                "is_complete=true requires empty missing_fields and conflicts"
            )
        if not self.is_complete and not has_gap:
            raise ValueError(
                "is_complete=false requires at least one missing field or conflict"
            )
        return self


def enforce_data_quality_correspondence(
    *,
    contract_name: str,
    data_quality: DataQuality,
    allowlisted_values: dict[str, object],
    known_field_names: frozenset[str],
) -> None:
    """Enforce the §6.2.12 exact correspondence rules for one contract.

    ``allowlisted_values`` maps each allowlisted evidence field name to its
    current value; every other known field is structural and can never be
    excused via ``missing_fields``.
    """
    for path in data_quality.missing_fields:
        if path not in allowlisted_values:
            if path in known_field_names:
                raise ValueError(
                    f"{contract_name}: structural field {path!r} may not be "
                    "declared missing"
                )
            raise ValueError(
                f"{contract_name}: unknown field path {path!r} in missing_fields"
            )
        if allowlisted_values[path] is not None:
            raise ValueError(
                f"{contract_name}: field {path!r} is declared missing but present"
            )
    for name, value in allowlisted_values.items():
        if value is None and name not in data_quality.missing_fields:
            raise ValueError(
                f"{contract_name}: field {name!r} is absent but not declared "
                "in missing_fields"
            )
    for conflict in data_quality.conflicts:
        if conflict.field_path not in known_field_names:
            raise ValueError(
                f"{contract_name}: conflict names unknown field path "
                f"{conflict.field_path!r}"
            )
