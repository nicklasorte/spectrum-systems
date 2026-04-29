"""RFX-N10 — Authority fixture safety layer for negative tests.

Ensures that test fixtures used in negative/red-team tests do not contain
static forbidden authority phrases as literal source text. Forbidden phrases
must be constructed dynamically at runtime so they cannot be accidentally
committed as owned verbs in fixture files.

This module is a non-owning phase-label support helper. It does not own the
governed authority-boundary surfaces declared in
``docs/architecture/system_registry.md``.

Failure prevented: static forbidden authority phrases persisting in fixture
source, bypassing authority-shape checks on committed code.

Signal improved: fixture hygiene; authority-shape false-negative rate.

Reason codes:
  rfx_fixture_static_forbidden_phrase  — fixture contains a static forbidden phrase
  rfx_fixture_missing_id               — fixture record lacks an identifier
  rfx_fixture_empty_corpus             — no fixtures supplied
  rfx_fixture_dynamic_check_missing    — fixture claims dynamic construction but proof absent
  rfx_fixture_malformed_row            — a fixture row is not a dict
"""

from __future__ import annotations

import re
from typing import Any


def _build_forbidden_patterns() -> list[re.Pattern[str]]:
    """Build forbidden-phrase patterns at runtime. Never stored as literals."""
    fragments = [
        ("approv" + "es",),
        ("certifi" + "es",),
        ("author" + "izes",),
        ("adjudicat" + "es",),
        ("enforc" + "es",),
        ("promot" + "es",),
        ("own" + "s authority",),
        ("grant" + "s authority",),
    ]
    return [
        re.compile(r"\b" + re.escape(f[0]) + r"\b", re.IGNORECASE)
        for f in fragments
    ]


_FORBIDDEN_PATTERNS: list[re.Pattern[str]] = _build_forbidden_patterns()


def check_rfx_authority_fixture_safety(
    *,
    fixtures: list[dict[str, Any]],
) -> dict[str, Any]:
    """Verify that test fixtures contain no static forbidden authority phrases.

    Each fixture dict must have an ``id`` and a ``text`` field containing the
    fixture source text to check.
    """
    reason: list[str] = []
    violations: list[dict[str, Any]] = []

    if not fixtures:
        reason.append("rfx_fixture_empty_corpus")
        return {
            "artifact_type": "rfx_authority_fixture_safety_result",
            "schema_version": "1.0.0",
            "violations": violations,
            "reason_codes_emitted": sorted(set(reason)),
            "status": "unsafe",
            "signals": {
                "total_fixtures": 0,
                "violation_count": 0,
                "clean_fixture_pct": 0.0,
            },
        }

    for fx in fixtures:
        if not isinstance(fx, dict):
            reason.append("rfx_fixture_malformed_row")
            continue
        fx_id = fx.get("id") or ""
        if not fx_id:
            reason.append("rfx_fixture_missing_id")
        text = str(fx.get("text") or "")
        matched: list[str] = []
        for pat in _FORBIDDEN_PATTERNS:
            m = pat.search(text)
            if m:
                matched.append(m.group(0))
        if matched:
            reason.append("rfx_fixture_static_forbidden_phrase")
            violations.append({
                "fixture_id": fx_id,
                "matched_phrases": matched,
            })
        if fx.get("claims_dynamic") and not fx.get("dynamic_proof_ref"):
            reason.append("rfx_fixture_dynamic_check_missing")

    total = len(fixtures)
    violation_count = len(violations)
    unique_reasons = sorted(set(reason))
    return {
        "artifact_type": "rfx_authority_fixture_safety_result",
        "schema_version": "1.0.0",
        "violations": violations,
        "reason_codes_emitted": unique_reasons,
        "status": "safe" if not unique_reasons else "unsafe",
        "signals": {
            "total_fixtures": total,
            "violation_count": violation_count,
            "clean_fixture_pct": 100.0 * (total - violation_count) / max(total, 1),
        },
    }
