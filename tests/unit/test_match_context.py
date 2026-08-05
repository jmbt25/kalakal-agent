"""Unit tests for MatchContext (§6.2.3): estimator-consumed allowlist."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kalakal.domain import (
    MATCH_ESTIMATOR_FIELDS,
    DataQuality,
    MatchContext,
    RosterEntry,
)
from tests.unit import factories as f


def incomplete_quality(*missing: str) -> DataQuality:
    return DataQuality(is_complete=False, missing_fields=tuple(missing), conflicts=())


class TestMatchContextAllowlist:
    @pytest.mark.parametrize("field", MATCH_ESTIMATOR_FIELDS)
    def test_declared_missing_estimator_field_valid(self, field: str) -> None:
        context = f.make_match_context(
            **{field: None}, data_quality=incomplete_quality(field)
        )
        assert getattr(context, field) is None
        assert context.data_quality.missing_fields == (field,)

    def test_all_estimator_fields_missing_valid(self) -> None:
        overrides: dict[str, object] = {name: None for name in MATCH_ESTIMATOR_FIELDS}
        context = f.make_match_context(
            **overrides,
            data_quality=incomplete_quality(*MATCH_ESTIMATOR_FIELDS),
        )
        assert context.data_quality.is_complete is False

    @pytest.mark.parametrize("field", MATCH_ESTIMATOR_FIELDS)
    def test_absent_but_undeclared_rejected(self, field: str) -> None:
        with pytest.raises(ValidationError, match="not declared"):
            f.make_match_context(**{field: None})

    @pytest.mark.parametrize("field", MATCH_ESTIMATOR_FIELDS)
    def test_declared_but_present_rejected(self, field: str) -> None:
        with pytest.raises(ValidationError, match="declared missing but present"):
            f.make_match_context(data_quality=incomplete_quality(field))

    @pytest.mark.parametrize(
        "path", ["yes_team_name", "patch_label", "scheduled_start", "provenance"]
    )
    def test_structural_field_in_missing_fields_rejected(self, path: str) -> None:
        with pytest.raises(ValidationError, match="structural field"):
            f.make_match_context(data_quality=incomplete_quality(path))

    def test_unknown_path_in_missing_fields_rejected(self) -> None:
        with pytest.raises(ValidationError, match="unknown field path"):
            f.make_match_context(data_quality=incomplete_quality("draw_team_rating"))

    def test_is_complete_true_requires_all_estimator_inputs(self) -> None:
        # A null estimator input with is_complete=true fails: the null value
        # is undeclared, so the exact-correspondence rule rejects it.
        with pytest.raises(ValidationError, match="not declared"):
            f.make_match_context(yes_team_rating=None)

    def test_conflict_on_estimator_field_validates_as_contract(self) -> None:
        # Contract-level: valid. The estimator itself refuses it (§10.1).
        quality = DataQuality(
            is_complete=False,
            missing_fields=(),
            conflicts=(f.make_conflict("yes_team_rating"),),
        )
        context = f.make_match_context(data_quality=quality)
        assert context.data_quality.conflicts[0].field_path == "yes_team_rating"

    def test_conflict_with_unknown_path_rejected(self) -> None:
        quality = DataQuality(
            is_complete=False,
            missing_fields=(),
            conflicts=(f.make_conflict("ask_price_micro"),),
        )
        with pytest.raises(ValidationError, match="unknown field path"):
            f.make_match_context(data_quality=quality)


class TestRosterIntegrity:
    def test_valid_roster(self) -> None:
        context = f.make_match_context()
        assert {entry.team_name for entry in context.rosters} == {
            f.YES_TEAM_NAME,
            f.NO_TEAM_NAME,
        }

    def test_unknown_roster_team_rejected(self) -> None:
        rosters = (
            RosterEntry(team_name=f.YES_TEAM_NAME, player_handle="syn-a-one"),
            RosterEntry(team_name="SYN-C", player_handle="syn-c-one"),
        )
        with pytest.raises(ValidationError, match="must match the yes/no team"):
            f.make_match_context(rosters=rosters)

    def test_single_team_roster_rejected(self) -> None:
        rosters = (
            RosterEntry(team_name=f.YES_TEAM_NAME, player_handle="syn-a-one"),
            RosterEntry(team_name=f.YES_TEAM_NAME, player_handle="syn-a-two"),
        )
        with pytest.raises(ValidationError, match="must appear in the roster"):
            f.make_match_context(rosters=rosters)

    def test_duplicate_player_handles_rejected(self) -> None:
        rosters = (
            RosterEntry(team_name=f.YES_TEAM_NAME, player_handle="syn-one"),
            RosterEntry(team_name=f.NO_TEAM_NAME, player_handle="syn-one"),
        )
        with pytest.raises(ValidationError, match="handles must be unique"):
            f.make_match_context(rosters=rosters)

    def test_identical_side_team_names_rejected(self) -> None:
        rosters = (
            RosterEntry(team_name=f.YES_TEAM_NAME, player_handle="syn-a-one"),
            RosterEntry(team_name=f.YES_TEAM_NAME, player_handle="syn-a-two"),
        )
        with pytest.raises(ValidationError, match="must differ"):
            f.make_match_context(no_team_name=f.YES_TEAM_NAME, rosters=rosters)

    def test_single_entry_roster_rejected(self) -> None:
        rosters = (RosterEntry(team_name=f.YES_TEAM_NAME, player_handle="syn-a-one"),)
        with pytest.raises(ValidationError):
            f.make_match_context(rosters=rosters)


class TestMatchContextStructure:
    def test_valid(self) -> None:
        context = f.make_match_context()
        assert context.best_of == 3
        assert context.yes_team_rating == f.YES_TEAM_RATING

    @pytest.mark.parametrize(
        "field",
        [
            "schema_version",
            "match_id",
            "market_id",
            "yes_team_name",
            "no_team_name",
            "best_of",
            "tournament_name",
            "tournament_tier",
            "rosters",
            "patch_label",
            "scheduled_start",
            "as_of",
            "valid_until",
            "data_quality",
            "provenance",
        ],
    )
    def test_structural_fields_required(self, field: str) -> None:
        kwargs = f.match_context_kwargs()
        del kwargs[field]
        with pytest.raises(ValidationError):
            MatchContext(**kwargs)

    @pytest.mark.parametrize("value", [0, -1, 10_001])
    def test_rating_bounds(self, value: int) -> None:
        with pytest.raises(ValidationError):
            f.make_match_context(yes_team_rating=value)

    @pytest.mark.parametrize("value", [-1, 101])
    def test_form_bounds(self, value: int) -> None:
        with pytest.raises(ValidationError):
            f.make_match_context(no_team_form=value)

    @pytest.mark.parametrize("value", [600.0, True, "600"])
    def test_non_int_rating_rejected(self, value: object) -> None:
        with pytest.raises(ValidationError):
            f.make_match_context(yes_team_rating=value)

    @pytest.mark.parametrize("value", [1, 2, 3, 5, 7])
    def test_best_of_supported_values_accepted(self, value: int) -> None:
        assert f.make_match_context(best_of=value).best_of == value

    @pytest.mark.parametrize("value", [0, 8, -1, 3.0, True, False])
    def test_best_of_out_of_range_or_non_int_rejected(self, value: object) -> None:
        with pytest.raises(ValidationError):
            f.make_match_context(best_of=value)

    def test_empty_rosters_rejected(self) -> None:
        with pytest.raises(ValidationError):
            f.make_match_context(rosters=())

    def test_valid_until_before_as_of_rejected(self) -> None:
        with pytest.raises(ValidationError, match="valid_until"):
            f.make_match_context(as_of=f.ts(60), valid_until=f.ts(0))

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            f.make_match_context(coach_name="synthetic")
