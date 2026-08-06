"""Deterministic, source-aware explanation generation (§5.2, §6.2.8)."""

from kalakal.explain.generator import (
    EXPLANATION_TEMPLATE_VERSION,
    AgentQualitativeContent,
    EvidenceCatalog,
    ExplanationGenerationError,
    assemble_agent_explanation,
    build_evidence_catalog,
    find_numeric_narrative,
    find_unresolved_evidence_refs,
    generate_no_valid_candidates_explanation,
    generate_stub_abstention_explanation,
    generate_stub_post_selection_explanation,
)

__all__ = [
    "EXPLANATION_TEMPLATE_VERSION",
    "AgentQualitativeContent",
    "EvidenceCatalog",
    "ExplanationGenerationError",
    "assemble_agent_explanation",
    "build_evidence_catalog",
    "find_numeric_narrative",
    "find_unresolved_evidence_refs",
    "generate_no_valid_candidates_explanation",
    "generate_stub_abstention_explanation",
    "generate_stub_post_selection_explanation",
]
