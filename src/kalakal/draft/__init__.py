"""Deterministic simulated Discord-draft generation (§6.2.9)."""

from kalakal.draft.simulated import (
    FIXTURE_DRAFT_CONFIG,
    DraftGenerationError,
    DraftSkippedNoBet,
    DraftStaleAtGeneration,
    SimulatedDraftConfig,
    SimulatedDraftOutcome,
    draft_identity_key,
    format_micro_as_cents,
    format_ppm_as_percent,
    format_ppm_as_signed_points,
    format_utc_timestamp,
    generate_simulated_draft,
)

__all__ = [
    "FIXTURE_DRAFT_CONFIG",
    "DraftGenerationError",
    "DraftSkippedNoBet",
    "DraftStaleAtGeneration",
    "SimulatedDraftConfig",
    "SimulatedDraftOutcome",
    "draft_identity_key",
    "format_micro_as_cents",
    "format_ppm_as_percent",
    "format_ppm_as_signed_points",
    "format_utc_timestamp",
    "generate_simulated_draft",
]
