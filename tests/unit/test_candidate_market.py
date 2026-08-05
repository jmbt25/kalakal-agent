"""Unit tests for CandidateMarket (§6.2.2): empty missing-field allowlist."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kalakal.domain import CandidateMarket, DataQuality
from tests.unit import factories as f


class TestCandidateMarket:
    def test_valid(self) -> None:
        market = f.make_candidate_market()
        assert market.status == "open"
        assert market.data_quality.is_complete is True

    def test_closed_status_valid(self) -> None:
        assert f.make_candidate_market(status="closed").status == "closed"

    @pytest.mark.parametrize(
        "field",
        [
            "schema_version",
            "market_id",
            "event_name",
            "series_description",
            "yes_means",
            "no_means",
            "status",
            "market_link",
            "as_of",
            "valid_until",
            "data_quality",
            "provenance",
        ],
    )
    def test_every_field_structurally_required(self, field: str) -> None:
        kwargs = f.candidate_market_kwargs()
        del kwargs[field]
        with pytest.raises(ValidationError):
            CandidateMarket(**kwargs)

    @pytest.mark.parametrize(
        ("path", "expected"),
        [
            ("event_name", "structural field"),
            ("bid_price_micro", "unknown field path"),
            ("yes_team_rating", "unknown field path"),
        ],
    )
    def test_empty_allowlist_rejects_any_missing_declaration(
        self, path: str, expected: str
    ) -> None:
        quality = DataQuality(is_complete=False, missing_fields=(path,), conflicts=())
        with pytest.raises(ValidationError, match=expected):
            CandidateMarket(**f.candidate_market_kwargs(data_quality=quality))

    def test_conflict_on_present_field_valid(self) -> None:
        quality = DataQuality(
            is_complete=False,
            missing_fields=(),
            conflicts=(f.make_conflict("series_description"),),
        )
        market = f.make_candidate_market(data_quality=quality)
        assert market.data_quality.is_complete is False

    def test_conflict_with_unknown_path_rejected(self) -> None:
        quality = DataQuality(
            is_complete=False,
            missing_fields=(),
            conflicts=(f.make_conflict("yes_team_rating"),),
        )
        with pytest.raises(ValidationError, match="unknown field path"):
            CandidateMarket(**f.candidate_market_kwargs(data_quality=quality))

    @pytest.mark.parametrize(
        "link",
        ["https://jup.ag/prediction/mkt-1", "https://example.com/mkt-1"],
    )
    def test_non_synthetic_link_rejected(self, link: str) -> None:
        with pytest.raises(ValidationError):
            CandidateMarket(**f.candidate_market_kwargs(market_link=link))

    def test_valid_until_before_as_of_rejected(self) -> None:
        with pytest.raises(ValidationError, match="valid_until"):
            CandidateMarket(
                **f.candidate_market_kwargs(as_of=f.ts(60), valid_until=f.ts(0))
            )

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CandidateMarket(**f.candidate_market_kwargs(order_book={}))

    def test_overlong_event_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CandidateMarket(**f.candidate_market_kwargs(event_name="x" * 201))

    @pytest.mark.parametrize("status", ["paused", "OPEN", ""])
    def test_unknown_status_rejected(self, status: str) -> None:
        with pytest.raises(ValidationError):
            CandidateMarket(**f.candidate_market_kwargs(status=status))
