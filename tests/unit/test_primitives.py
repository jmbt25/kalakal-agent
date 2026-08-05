"""Unit tests for shared strict domain primitives."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from kalakal.domain import EvidenceRef, FixtureProvenance, StrictModel, canonical_digest
from kalakal.domain.primitives import Identifier, SyntheticMarketLink, UtcDatetime
from tests.unit import factories as f


class _Probe(StrictModel):
    """Test-only carrier for primitive annotated types."""

    at: UtcDatetime
    ident: Identifier
    link: SyntheticMarketLink


def _probe_kwargs(**over: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "at": f.ts(),
        "ident": "id-1",
        "link": f.MARKET_LINK,
    }
    kwargs.update(over)
    return kwargs


class TestUtcDatetime:
    def test_utc_accepted(self) -> None:
        assert _Probe(**_probe_kwargs()).at == f.ts()

    @pytest.mark.parametrize(
        "value",
        [
            datetime(2026, 8, 5, 12, 0, 0),
            datetime(2026, 8, 5, 12, 0, 0, tzinfo=timezone(timedelta(hours=2))),
            datetime(2026, 8, 5, 12, 0, 0, tzinfo=timezone(timedelta(minutes=-30))),
        ],
        ids=["naive", "plus-2h", "minus-30m"],
    )
    def test_naive_and_non_utc_rejected(self, value: datetime) -> None:
        with pytest.raises(ValidationError, match="timezone-aware UTC"):
            _Probe(**_probe_kwargs(at=value))

    def test_string_rejected_in_python_mode(self) -> None:
        with pytest.raises(ValidationError):
            _Probe(**_probe_kwargs(at="2026-08-05T12:00:00Z"))

    def test_zero_offset_non_utc_tzinfo_accepted(self) -> None:
        value = datetime(2026, 8, 5, 12, 0, 0, tzinfo=timezone(timedelta(0)))
        assert _Probe(**_probe_kwargs(at=value)).at.utcoffset() == timedelta(0)


class TestIdentifier:
    @pytest.mark.parametrize("value", ["a", "mkt-1", "run_1.2:x", "A9"])
    def test_valid(self, value: str) -> None:
        assert _Probe(**_probe_kwargs(ident=value)).ident == value

    @pytest.mark.parametrize(
        "value", ["", "-leading", " space", "has space", "x" * 129, "émoji"]
    )
    def test_invalid(self, value: str) -> None:
        with pytest.raises(ValidationError):
            _Probe(**_probe_kwargs(ident=value))


class TestSyntheticMarketLink:
    def test_synthetic_domain_accepted(self) -> None:
        assert _Probe(**_probe_kwargs()).link == f.MARKET_LINK

    @pytest.mark.parametrize(
        "value",
        [
            "https://jup.ag/prediction/mkt-1",
            "https://markets.example.com/mkt-1",
            "http://markets.kalakal.invalid/mkt-1",
            "",
        ],
    )
    def test_non_synthetic_rejected(self, value: str) -> None:
        with pytest.raises(ValidationError):
            _Probe(**_probe_kwargs(link=value))


class TestStrictModelBehavior:
    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError, match="extra_field"):
            _Probe(**_probe_kwargs(extra_field="x"))

    def test_frozen(self) -> None:
        probe = _Probe(**_probe_kwargs())
        with pytest.raises(ValidationError):
            probe.ident = "other"

    def test_deterministic_serialization(self) -> None:
        first = _Probe(**_probe_kwargs())
        second = _Probe(**_probe_kwargs())
        assert first.model_dump_json() == second.model_dump_json()

    def test_utc_serializes_with_z_suffix(self) -> None:
        assert '"2026-08-05T12:00:00Z"' in _Probe(**_probe_kwargs()).model_dump_json()


class TestFixtureProvenance:
    def test_valid(self) -> None:
        assert f.make_provenance().is_synthetic is True

    @pytest.mark.parametrize("value", [False, 1, 0, "true", None])
    def test_is_synthetic_must_be_true(self, value: object) -> None:
        with pytest.raises(ValidationError):
            FixtureProvenance(**f.provenance_kwargs(is_synthetic=value))

    def test_is_synthetic_required(self) -> None:
        kwargs = f.provenance_kwargs()
        del kwargs["is_synthetic"]
        with pytest.raises(ValidationError):
            FixtureProvenance(**kwargs)

    @pytest.mark.parametrize(
        "digest", ["", "abc", "Z" * 64, f.sha_hex("x").upper(), f.sha_hex("x") + "0"]
    )
    def test_malformed_digest_rejected(self, digest: str) -> None:
        with pytest.raises(ValidationError):
            FixtureProvenance(**f.provenance_kwargs(content_digest=digest))


class TestEvidenceRef:
    @pytest.mark.parametrize("kind", ["market", "match", "snapshot", "fixture_source"])
    def test_valid_kinds(self, kind: str) -> None:
        assert EvidenceRef(kind=kind, ref_id="x").kind == kind  # type: ignore[arg-type]

    def test_unknown_kind_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EvidenceRef(kind="url", ref_id="x")  # type: ignore[arg-type]


class TestCanonicalDigest:
    def test_deterministic_and_order_independent(self) -> None:
        first = canonical_digest({"a": 1, "b": "x"})
        second = canonical_digest({"b": "x", "a": 1})
        assert first == second
        assert len(first) == 64

    def test_value_sensitivity(self) -> None:
        assert canonical_digest({"a": 1}) != canonical_digest({"a": 2})
        assert canonical_digest({"a": 1}) != canonical_digest({"a": "1"})

    @pytest.mark.parametrize("value", [1.5, True, None, [1]])
    def test_non_int_str_values_rejected(self, value: object) -> None:
        with pytest.raises(ValueError, match="must be str or int"):
            canonical_digest({"a": value})  # type: ignore[dict-item]
