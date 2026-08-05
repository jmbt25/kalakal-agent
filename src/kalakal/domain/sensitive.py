"""Bounded detection of obvious credential-shaped content (architecture.md §6.1).

The decision-record validator must reject obvious credential patterns before
persistence. This scanner is pure, deterministic, dependency-free, and
deliberately narrow: it flags only strong indicators (key headers, known
token prefixes, explicit credential assignments, email shapes, long
private-key-like base58 payloads) so ordinary prose that merely mentions
words like "token" or "private key" is never rejected.

The scan fails closed: exhausting the string budget or the depth budget
returns a rejection indicator instead of silently skipping content, so a
credential can never hide behind bulk or nesting. The budgets are sized
well above the largest valid bounded DecisionRecord shape, so legitimate
records never approach them.
"""

from __future__ import annotations

import re
from typing import Final

from pydantic import BaseModel

SCAN_BUDGET_EXCEEDED: Final = "scan budget exceeded"
SCAN_DEPTH_EXCEEDED: Final = "scan depth exceeded"

_MAX_DEPTH = 12
_MAX_STRINGS = 20_000
_MAX_CHARS_PER_STRING = 4000

_SENSITIVE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "PEM private-key header",
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ),
    (
        "credential token prefix",
        re.compile(
            r"\b(?:sk-[A-Za-z0-9_-]{20,}"
            r"|sk_live_[A-Za-z0-9]{16,}"
            r"|AKIA[0-9A-Z]{16}"
            r"|ghp_[A-Za-z0-9]{30,}"
            r"|github_pat_[A-Za-z0-9_]{20,}"
            r"|xox[abprs]-[A-Za-z0-9-]{20,}"
            r"|AIza[0-9A-Za-z_-]{35})"
        ),
    ),
    (
        "credential assignment",
        re.compile(
            r"(?i)\b(?:api[ _-]?key|passwd|password|private[ _-]?key"
            r"|secret[ _-]?key|seed[ _-]?phrase|mnemonic|access[ _-]?token"
            r"|auth[ _-]?token|client[ _-]?secret)\s*[:=]\s*\S{8,}"
        ),
    ),
    (
        "email address",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    ),
    (
        # Long enough to exclude 64-char hex digests; catches e.g. base58
        # Solana secret keys (~88 chars).
        "base58 private-key-like payload",
        re.compile(r"\b[1-9A-HJ-NP-Za-km-z]{80,}\b"),
    ),
)


def find_sensitive_content(value: object) -> str | None:
    """Return the label of the first strong credential indicator, else None.

    Recursively scans strings inside models, tuples, and lists. Non-string
    scalars are ignored. Fails closed: exceeding the scan-string budget
    returns :data:`SCAN_BUDGET_EXCEEDED` and exceeding the depth budget
    returns :data:`SCAN_DEPTH_EXCEEDED`, so unscanned content is treated as
    a rejection, never as clean.
    """
    stack: list[tuple[object, int]] = [(value, 0)]
    scanned = 0
    while stack:
        current, depth = stack.pop()
        if depth > _MAX_DEPTH:
            return SCAN_DEPTH_EXCEEDED
        if isinstance(current, str):
            scanned += 1
            if scanned > _MAX_STRINGS:
                return SCAN_BUDGET_EXCEEDED
            text = current[:_MAX_CHARS_PER_STRING]
            for label, pattern in _SENSITIVE_PATTERNS:
                if pattern.search(text):
                    return label
        elif isinstance(current, BaseModel):
            for name in type(current).model_fields:
                stack.append((getattr(current, name), depth + 1))
        elif isinstance(current, tuple | list):
            for item in current:
                stack.append((item, depth + 1))
    return None
