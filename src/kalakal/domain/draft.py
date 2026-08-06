"""SimulatedDiscordDraft contract (architecture.md §6.2.9).

Structured duplicates of every mandatory element plus containment checks on
the rendered text. Numeric text rendering is the slice 5 generator's job;
this schema guarantees the labeled, synthetic, non-postable shape.
"""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from kalakal.domain.primitives import (
    AskPriceMicro,
    Identifier,
    LongText,
    MarketSide,
    MediumText,
    NetEdgePpm,
    ProbabilityPpm,
    ShortText,
    StrictModel,
    StrictTrue,
    SyntheticMarketLink,
    UtcDatetime,
    VersionStr,
)


class SimulatedDiscordDraft(StrictModel):
    """A deterministic, clearly simulated Discord draft — never postable."""

    schema_version: Literal["1"]
    run_id: Identifier
    market_id: Identifier
    side: MarketSide
    is_simulation: StrictTrue
    # The versioned deterministic renderer that produced this draft (§6.2.9):
    # recorded so a renderer-configuration change is visible in audit data
    # even when the rendered text happens to be unchanged.
    renderer_version: VersionStr
    simulation_label: Literal["SIMULATION — DO NOT POST"]
    event_name: ShortText
    side_meaning: ShortText
    market_link: SyntheticMarketLink
    ask_price_micro: AskPriceMicro
    probability_ppm: ProbabilityPpm
    estimator_display_label: Literal["DEMO ESTIMATOR — NOT PREDICTIVE"]
    net_edge_ppm: NetEdgePpm
    nfa_tag: Literal["#nfa"]
    generated_at: UtcDatetime
    expires_at: UtcDatetime
    stale_regeneration_warning: MediumText
    draft_text: LongText

    @model_validator(mode="after")
    def _check_mandatory_elements(self) -> SimulatedDiscordDraft:
        if self.expires_at <= self.generated_at:
            raise ValueError("expires_at must be after generated_at")
        if not self.draft_text.startswith(self.simulation_label):
            raise ValueError(
                "draft_text must start with the simulation label "
                f"{self.simulation_label!r}"
            )
        required_fragments = {
            "event_name": self.event_name,
            "side_meaning": self.side_meaning,
            "market_link": self.market_link,
            "nfa_tag": self.nfa_tag,
            "stale_regeneration_warning": self.stale_regeneration_warning,
        }
        for name, fragment in required_fragments.items():
            if fragment not in self.draft_text:
                raise ValueError(f"draft_text must contain {name}")
        return self
