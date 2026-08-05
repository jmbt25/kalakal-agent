"""Unit tests for MarketSnapshot (§6.2.4): bid/liquidity allowlist, ask bounds."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kalakal.domain import (
    MARKET_SNAPSHOT_MISSING_ALLOWLIST,
    DataQuality,
    MarketSnapshot,
)
from tests.unit import factories as f


def incomplete_quality(*missing: str) -> DataQuality:
    return DataQuality(is_complete=False, missing_fields=tuple(missing), conflicts=())


class TestMarketSnapshotAllowlist:
    @pytest.mark.parametrize("field", MARKET_SNAPSHOT_MISSING_ALLOWLIST)
    def test_declared_missing_field_valid(self, field: str) -> None:
        snapshot = f.make_market_snapshot(
            **{field: None}, data_quality=incomplete_quality(field)
        )
        assert getattr(snapshot, field) is None

    def test_both_declared_missing_valid(self) -> None:
        snapshot = f.make_market_snapshot(
            bid_price_micro=None,
            liquidity_hint_micro=None,
            data_quality=incomplete_quality(*MARKET_SNAPSHOT_MISSING_ALLOWLIST),
        )
        assert snapshot.data_quality.is_complete is False

    @pytest.mark.parametrize("field", MARKET_SNAPSHOT_MISSING_ALLOWLIST)
    def test_absent_but_undeclared_rejected(self, field: str) -> None:
        with pytest.raises(ValidationError, match="not declared"):
            f.make_market_snapshot(**{field: None})

    @pytest.mark.parametrize("field", MARKET_SNAPSHOT_MISSING_ALLOWLIST)
    def test_declared_but_present_rejected(self, field: str) -> None:
        with pytest.raises(ValidationError, match="declared missing but present"):
            f.make_market_snapshot(data_quality=incomplete_quality(field))

    @pytest.mark.parametrize(
        "path", ["ask_price_micro", "market_id", "fee_model_version", "captured_at"]
    )
    def test_structural_field_in_missing_fields_rejected(self, path: str) -> None:
        with pytest.raises(ValidationError, match="structural field"):
            f.make_market_snapshot(data_quality=incomplete_quality(path))

    def test_unknown_path_rejected(self) -> None:
        with pytest.raises(ValidationError, match="unknown field path"):
            f.make_market_snapshot(data_quality=incomplete_quality("yes_team_rating"))

    def test_conflict_on_present_ask_valid(self) -> None:
        quality = DataQuality(
            is_complete=False,
            missing_fields=(),
            conflicts=(f.make_conflict("ask_price_micro"),),
        )
        snapshot = f.make_market_snapshot(data_quality=quality)
        assert snapshot.ask_price_micro == 600_000


class TestMarketSnapshotStructure:
    def test_valid(self) -> None:
        snapshot = f.make_market_snapshot()
        assert snapshot.ask_price_micro == 600_000
        assert snapshot.side == "yes"

    @pytest.mark.parametrize(
        "field",
        [
            "schema_version",
            "market_id",
            "side",
            "ask_price_micro",
            "captured_at",
            "valid_until",
            "fee_model_version",
            "data_quality",
            "provenance",
        ],
    )
    def test_structural_fields_required(self, field: str) -> None:
        kwargs = f.market_snapshot_kwargs()
        del kwargs[field]
        with pytest.raises(ValidationError):
            MarketSnapshot(**kwargs)

    def test_ask_cannot_be_declared_missing_even_when_null(self) -> None:
        with pytest.raises(ValidationError):
            f.make_market_snapshot(
                ask_price_micro=None,
                data_quality=incomplete_quality("ask_price_micro"),
            )

    @pytest.mark.parametrize("value", [0, -1, 1_000_000, 1_000_001])
    def test_ask_bounds_exclusive(self, value: int) -> None:
        with pytest.raises(ValidationError):
            f.make_market_snapshot(ask_price_micro=value)

    @pytest.mark.parametrize("value", [1, 999_999])
    def test_ask_boundary_values_accepted(self, value: int) -> None:
        assert f.make_market_snapshot(ask_price_micro=value).ask_price_micro == value

    @pytest.mark.parametrize("value", [600_000.0, True, "600000"])
    def test_non_int_ask_rejected(self, value: object) -> None:
        with pytest.raises(ValidationError):
            f.make_market_snapshot(ask_price_micro=value)

    @pytest.mark.parametrize("value", [0, 1_000_000])
    def test_bid_bounds_exclusive(self, value: int) -> None:
        with pytest.raises(ValidationError):
            f.make_market_snapshot(bid_price_micro=value)

    def test_negative_liquidity_rejected(self) -> None:
        with pytest.raises(ValidationError):
            f.make_market_snapshot(liquidity_hint_micro=-1)

    @pytest.mark.parametrize("side", ["maybe", "YES", ""])
    def test_unknown_side_rejected(self, side: str) -> None:
        with pytest.raises(ValidationError):
            f.make_market_snapshot(side=side)

    def test_valid_until_before_captured_at_rejected(self) -> None:
        with pytest.raises(ValidationError, match="valid_until"):
            f.make_market_snapshot(captured_at=f.ts(60), valid_until=f.ts(0))

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            f.make_market_snapshot(order_depth=[])
