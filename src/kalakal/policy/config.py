"""Versioned, immutable policy configuration (architecture.md §6.2.7).

The entry band is externally sourced configuration — the Jup Callers
Season 1 counted entry band of 10¢–90¢ (CLAUDE.md §8,
docs/research/jupcallers.md). The minimum net edge is a Kalakal fixture-MVP
policy choice, not a Jupiter or Jup Callers rule, and its provenance text
says so. Every configured rule carries truthful provenance, and the complete
configuration has a canonical digest so any change to a threshold or its
provenance changes every dependent decision digest.

Values are constructor-supplied only: nothing here reads environment
variables, files, or mutable global state.
"""

from __future__ import annotations

from typing import Annotated, Final

from pydantic import Field, model_validator

from kalakal.domain.primitives import (
    PPM_PER_UNIT,
    AskPriceMicro,
    ShortText,
    StrictModel,
    VersionStr,
    canonical_digest,
)

MinNetEdgePpm = Annotated[int, Field(gt=0, le=PPM_PER_UNIT)]


class PolicyConfig(StrictModel):
    """One immutable, versioned set of policy thresholds with provenance.

    The entry band is inclusive on both ends; the minimum net edge is
    inclusive. Threshold fields reuse the domain micro/ppm ranges, so a
    zero, negative, float, or out-of-domain threshold cannot validate.
    """

    policy_version: VersionStr
    min_entry_price_micro: AskPriceMicro
    max_entry_price_micro: AskPriceMicro
    min_net_edge_ppm: MinNetEdgePpm
    entry_band_source: ShortText
    min_net_edge_source: ShortText

    @model_validator(mode="after")
    def _check_invariants(self) -> PolicyConfig:
        if self.min_entry_price_micro >= self.max_entry_price_micro:
            raise ValueError(
                "min_entry_price_micro must be strictly below max_entry_price_micro"
            )
        return self


def policy_config_digest(config: PolicyConfig) -> str:
    """Canonical SHA-256 digest of the complete policy configuration.

    Covers every field, thresholds and provenance alike, so any
    configuration change changes every dependent decision digest.
    """
    return canonical_digest(
        {
            "policy_version": config.policy_version,
            "min_entry_price_micro": config.min_entry_price_micro,
            "max_entry_price_micro": config.max_entry_price_micro,
            "min_net_edge_ppm": config.min_net_edge_ppm,
            "entry_band_source": config.entry_band_source,
            "min_net_edge_source": config.min_net_edge_source,
        }
    )


# Module-level immutable default for the fixture MVP. The engine takes an
# explicit config parameter; nothing depends on this constant implicitly.
FIXTURE_POLICY_CONFIG: Final = PolicyConfig(
    policy_version="fixture-policy-1",
    min_entry_price_micro=100_000,
    max_entry_price_micro=900_000,
    min_net_edge_ppm=20_000,
    entry_band_source=(
        "Jup Callers Season 1 counted entry band (10¢–90¢): externally "
        "sourced configured rule per docs/research/jupcallers.md and "
        "CLAUDE.md §8."
    ),
    min_net_edge_source=(
        "Kalakal fixture-MVP minimum net edge: project policy choice, not a "
        "Jupiter or Jup Callers rule (docs/implementation-plan.md Slice 4)."
    ),
)
