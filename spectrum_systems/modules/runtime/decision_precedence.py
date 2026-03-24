"""Canonical decision precedence helpers for governed runtime paths."""

from __future__ import annotations

from typing import Iterable

# Highest severity first.
CANONICAL_PRECEDENCE = ("rollback", "block", "freeze", "hold", "warn", "promote")
_RANK = {value: index for index, value in enumerate(CANONICAL_PRECEDENCE)}


def precedence_rank(value: str) -> int:
    normalized = str(value).strip().lower()
    return _RANK.get(normalized, len(CANONICAL_PRECEDENCE))


def most_severe(values: Iterable[str], *, default: str) -> str:
    items = [str(item).strip().lower() for item in values if str(item).strip()]
    if not items:
        return default
    return sorted(items, key=precedence_rank)[0]
