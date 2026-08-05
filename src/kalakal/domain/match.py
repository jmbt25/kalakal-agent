"""MatchContext contract (architecture.md §6.2.3).

The prediction-market side mapping is structural: estimator-consumed inputs
are named for the market side they belong to (``yes_team_*`` / ``no_team_*``),
so a fixture or adapter can never invert the sides positionally. Team
identity is never inferred from free text such as ``yes_means``.
"""

from __future__ import annotations

from typing import Annotated, Final, Literal

from pydantic import Field, model_validator

from kalakal.domain.primitives import (
    BestOf,
    FixtureProvenance,
    Identifier,
    ShortText,
    StrictModel,
    SyntheticForm,
    SyntheticRating,
    UtcDatetime,
)
from kalakal.domain.quality import DataQuality, enforce_data_quality_correspondence

# §6.2.3 / §10.1: the estimator-consumed synthetic evidence fields. These —
# and only these — are conditionally optional and form the missing_fields
# allowlist; every other field is structural.
MATCH_ESTIMATOR_FIELDS: Final[tuple[str, ...]] = (
    "yes_team_rating",
    "yes_team_form",
    "no_team_rating",
    "no_team_form",
)


class RosterEntry(StrictModel):
    """One synthetic roster entry."""

    team_name: ShortText
    player_handle: ShortText


class MatchContext(StrictModel):
    """Validated synthetic match context for one candidate market."""

    schema_version: Literal["1"]
    match_id: Identifier
    market_id: Identifier
    yes_team_name: ShortText
    no_team_name: ShortText
    best_of: BestOf
    tournament_name: ShortText
    tournament_tier: ShortText
    rosters: Annotated[tuple[RosterEntry, ...], Field(min_length=2, max_length=20)]
    patch_label: ShortText
    scheduled_start: UtcDatetime
    as_of: UtcDatetime
    valid_until: UtcDatetime
    yes_team_rating: SyntheticRating | None = None
    yes_team_form: SyntheticForm | None = None
    no_team_rating: SyntheticRating | None = None
    no_team_form: SyntheticForm | None = None
    data_quality: DataQuality
    provenance: FixtureProvenance

    @model_validator(mode="after")
    def _check_invariants(self) -> MatchContext:
        if self.valid_until < self.as_of:
            raise ValueError("valid_until must not precede as_of")
        if self.yes_team_name == self.no_team_name:
            raise ValueError("yes_team_name and no_team_name must differ")
        roster_teams = {entry.team_name for entry in self.rosters}
        side_teams = {self.yes_team_name, self.no_team_name}
        unknown_teams = roster_teams - side_teams
        if unknown_teams:
            raise ValueError(
                "roster team names must match the yes/no team names; unknown: "
                f"{sorted(unknown_teams)}"
            )
        missing_teams = side_teams - roster_teams
        if missing_teams:
            raise ValueError(
                "both the yes-side and no-side teams must appear in the roster; "
                f"missing: {sorted(missing_teams)}"
            )
        handles = [entry.player_handle for entry in self.rosters]
        if len(set(handles)) != len(handles):
            raise ValueError("roster player handles must be unique")
        enforce_data_quality_correspondence(
            contract_name="MatchContext",
            data_quality=self.data_quality,
            allowlisted_values={
                name: getattr(self, name) for name in MATCH_ESTIMATOR_FIELDS
            },
            known_field_names=frozenset(type(self).model_fields),
        )
        return self
