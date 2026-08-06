"""Deterministic fixture entity-digest algorithm (architecture.md §6.1).

One algorithm covers every fixture-derived entity, including the scenario
document itself:

1. Take the entity's parsed JSON object.
2. Remove only the entity's *own* ``provenance.content_digest`` member.
   Nested entities keep their complete provenance blocks (digest included),
   so a scenario digest covers its entities' digests without ever being
   self-referential.
3. Serialize canonically: UTF-8, sorted object keys, compact ``(",", ":")``
   separators, array order preserved, ``ensure_ascii`` disabled.
4. The digest is the SHA-256 hex digest of those bytes.

Floats are rejected outright — money, prices, and probabilities are integer
micro-units/ppm, and a float could not round-trip bit-stably.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping


def canonical_fixture_json(value: object) -> bytes:
    """Canonical UTF-8 JSON bytes of ``value`` for digest computation."""
    _require_digestable(value)
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def fixture_entity_digest(entity: Mapping[str, object]) -> str:
    """SHA-256 hex digest of ``entity`` minus its own provenance digest."""
    provenance = entity.get("provenance")
    if not isinstance(provenance, Mapping) or "content_digest" not in provenance:
        raise ValueError(
            "entity must carry a provenance object with a content_digest member"
        )
    reduced_provenance = {
        key: value for key, value in provenance.items() if key != "content_digest"
    }
    reduced_entity = {
        key: (reduced_provenance if key == "provenance" else value)
        for key, value in entity.items()
    }
    return hashlib.sha256(canonical_fixture_json(reduced_entity)).hexdigest()


def _require_digestable(value: object) -> None:
    if value is None or isinstance(value, bool | int | str):
        return
    if isinstance(value, float):
        raise ValueError("float values are not permitted in fixture content")
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("fixture object keys must be strings")
            _require_digestable(item)
        return
    if isinstance(value, list | tuple):
        for item in value:
            _require_digestable(item)
        return
    raise ValueError(f"unsupported fixture value type: {type(value).__name__}")
