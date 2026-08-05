"""Unit tests for SimulatedDiscordDraft (§6.2.9)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kalakal.domain import SIMULATION_DRAFT_LABEL, SimulatedDiscordDraft
from tests.unit import factories as f


class TestSimulatedDiscordDraft:
    def test_valid(self) -> None:
        draft = f.make_draft()
        assert draft.is_simulation is True
        assert draft.draft_text.startswith(SIMULATION_DRAFT_LABEL)

    @pytest.mark.parametrize("minutes", [4, 3])
    def test_expiry_must_follow_generation(self, minutes: int) -> None:
        with pytest.raises(ValidationError, match="expires_at"):
            f.make_draft(expires_at=f.ts(minutes))  # generated_at is ts(4)

    def test_text_without_leading_label_rejected(self) -> None:
        kwargs = f.draft_kwargs()
        kwargs["draft_text"] = "Synthetic call\n" + kwargs["draft_text"]
        with pytest.raises(ValidationError, match="must start with"):
            SimulatedDiscordDraft(**kwargs)

    @pytest.mark.parametrize(
        ("fragment_field", "message"),
        [
            ("event_name", "event_name"),
            ("side_meaning", "side_meaning"),
            ("market_link", "market_link"),
            ("nfa_tag", "nfa_tag"),
            ("stale_regeneration_warning", "stale_regeneration_warning"),
        ],
    )
    def test_text_missing_mandatory_element_rejected(
        self, fragment_field: str, message: str
    ) -> None:
        kwargs = f.draft_kwargs()
        fragment = str(kwargs[fragment_field])
        kwargs["draft_text"] = str(kwargs["draft_text"]).replace(fragment, "")
        with pytest.raises(ValidationError, match=message):
            SimulatedDiscordDraft(**kwargs)

    @pytest.mark.parametrize("value", [False, 1, "true"])
    def test_is_simulation_must_be_true(self, value: object) -> None:
        with pytest.raises(ValidationError):
            f.make_draft(is_simulation=value)

    @pytest.mark.parametrize(
        "label", ["SIMULATION - DO NOT POST", "simulation — do not post", ""]
    )
    def test_simulation_label_literal_enforced(self, label: str) -> None:
        with pytest.raises(ValidationError):
            f.make_draft(simulation_label=label)

    def test_real_domain_link_rejected(self) -> None:
        with pytest.raises(ValidationError):
            f.make_draft(market_link="https://jup.ag/prediction/mkt-1")

    @pytest.mark.parametrize("tag", ["#NFA", "nfa", ""])
    def test_nfa_tag_literal_enforced(self, tag: str) -> None:
        with pytest.raises(ValidationError):
            f.make_draft(nfa_tag=tag)

    def test_estimator_label_literal_enforced(self) -> None:
        with pytest.raises(ValidationError):
            f.make_draft(estimator_display_label="REAL MODEL")

    @pytest.mark.parametrize("value", [600_000.0, True])
    def test_non_int_ask_rejected(self, value: object) -> None:
        with pytest.raises(ValidationError):
            f.make_draft(ask_price_micro=value)

    @pytest.mark.parametrize(
        "field",
        [
            "schema_version",
            "run_id",
            "market_id",
            "side",
            "is_simulation",
            "simulation_label",
            "event_name",
            "side_meaning",
            "market_link",
            "ask_price_micro",
            "probability_ppm",
            "estimator_display_label",
            "net_edge_ppm",
            "nfa_tag",
            "generated_at",
            "expires_at",
            "stale_regeneration_warning",
            "draft_text",
        ],
    )
    def test_required_fields(self, field: str) -> None:
        kwargs = f.draft_kwargs()
        del kwargs[field]
        with pytest.raises(ValidationError):
            SimulatedDiscordDraft(**kwargs)

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            f.make_draft(discord_channel_id="123")
