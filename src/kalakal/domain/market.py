"""CandidateMarket and MarketSnapshot contracts (architecture.md §6.2.2, §6.2.4)."""

from __future__ import annotations

from typing import Final, Literal

from pydantic import model_validator

from kalakal.domain.primitives import (
    AskPriceMicro,
    BidPriceMicro,
    FixtureProvenance,
    Identifier,
    LiquidityMicro,
    MarketSide,
    MarketStatus,
    ShortText,
    StrictModel,
    SyntheticMarketLink,
    UtcDatetime,
    VersionStr,
)
from kalakal.domain.quality import DataQuality, enforce_data_quality_correspondence

# §6.2.2: the CandidateMarket allowlist is empty — nothing may be excused
# via missing_fields.
CANDIDATE_MARKET_MISSING_ALLOWLIST: Final[tuple[str, ...]] = ()

# §6.2.4: only these evidence fields may be absent or null, and only when
# declared in missing_fields.
MARKET_SNAPSHOT_MISSING_ALLOWLIST: Final[tuple[str, ...]] = (
    "bid_price_micro",
    "liquidity_hint_micro",
)


class CandidateMarket(StrictModel):
    """A synthetic candidate market; every field is structurally required."""

    schema_version: Literal["1"]
    market_id: Identifier
    event_name: ShortText
    series_description: ShortText
    yes_means: ShortText
    no_means: ShortText
    status: MarketStatus
    market_link: SyntheticMarketLink
    as_of: UtcDatetime
    valid_until: UtcDatetime
    data_quality: DataQuality
    provenance: FixtureProvenance

    @model_validator(mode="after")
    def _check_invariants(self) -> CandidateMarket:
        if self.valid_until < self.as_of:
            raise ValueError("valid_until must not precede as_of")
        enforce_data_quality_correspondence(
            contract_name="CandidateMarket",
            data_quality=self.data_quality,
            allowlisted_values={},
            known_field_names=frozenset(type(self).model_fields),
        )
        return self


class MarketSnapshot(StrictModel):
    """A synthetic order-book snapshot for one (market, side).

    A snapshot without an ask price is structurally invalid, not incomplete.
    """

    schema_version: Literal["1"]
    market_id: Identifier
    side: MarketSide
    ask_price_micro: AskPriceMicro
    bid_price_micro: BidPriceMicro | None = None
    liquidity_hint_micro: LiquidityMicro | None = None
    captured_at: UtcDatetime
    valid_until: UtcDatetime
    fee_model_version: VersionStr
    data_quality: DataQuality
    provenance: FixtureProvenance

    @model_validator(mode="after")
    def _check_invariants(self) -> MarketSnapshot:
        if self.valid_until < self.captured_at:
            raise ValueError("valid_until must not precede captured_at")
        enforce_data_quality_correspondence(
            contract_name="MarketSnapshot",
            data_quality=self.data_quality,
            allowlisted_values={
                name: getattr(self, name) for name in MARKET_SNAPSHOT_MISSING_ALLOWLIST
            },
            known_field_names=frozenset(type(self).model_fields),
        )
        return self
