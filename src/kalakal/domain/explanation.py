"""DecisionExplanation contract (architecture.md §6.2.8).

Source-aware and narrative-only: numbers of record live exclusively in the
deterministic contracts (§6.2.5–§6.2.7), never in this prose.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from kalakal.domain.primitives import (
    ConfidenceQualifier,
    EvidenceRef,
    ExplanationSource,
    FactorDirection,
    Identifier,
    LongText,
    MediumText,
    StrictModel,
    VersionStr,
)


class KeyFactor(StrictModel):
    """One qualitative factor with its direction and evidence reference."""

    factor: MediumText
    direction: FactorDirection
    evidence_ref: EvidenceRef


class DecisionExplanation(StrictModel):
    """The run's narrative explanation, agent- or orchestrator-sourced."""

    schema_version: Literal["1"]
    run_id: Identifier
    source: ExplanationSource
    summary: LongText
    key_factors: Annotated[tuple[KeyFactor, ...], Field(max_length=16)]
    conflicts: Annotated[tuple[MediumText, ...], Field(max_length=16)]
    data_gaps: Annotated[tuple[MediumText, ...], Field(max_length=16)]
    confidence_qualifier: ConfidenceQualifier
    evidence_refs: Annotated[tuple[EvidenceRef, ...], Field(max_length=16)]
    prompt_version: VersionStr | None = None
    model_metadata_ref: Identifier | None = None
    explanation_template_version: VersionStr | None = None

    @model_validator(mode="after")
    def _check_source_conditions(self) -> DecisionExplanation:
        if self.source == "agent":
            if self.prompt_version is None:
                raise ValueError("agent-sourced explanation requires prompt_version")
            if self.model_metadata_ref is None:
                raise ValueError(
                    "agent-sourced explanation requires model_metadata_ref"
                )
            if self.explanation_template_version is not None:
                raise ValueError(
                    "agent-sourced explanation must not carry "
                    "explanation_template_version"
                )
        else:
            if self.explanation_template_version is None:
                raise ValueError(
                    "orchestrator-sourced explanation requires "
                    "explanation_template_version"
                )
            if self.prompt_version is not None:
                raise ValueError(
                    "orchestrator-sourced explanation must not carry prompt_version"
                )
            if self.model_metadata_ref is not None:
                raise ValueError(
                    "orchestrator-sourced explanation must not carry model_metadata_ref"
                )
        return self
