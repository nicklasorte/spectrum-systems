"""RFX-N20 — Operator handbook generated from live reason codes.

Generates a structured operator handbook from the live RFX reason code
registry. Each reason code must have a plain-language action description.
Codes without plain-language actions are flagged.

This module is a non-owning phase-label support helper. It does not own
the reason code registry or operator tooling — those are governed surfaces
whose authority is declared in ``docs/architecture/system_registry.md``.
This module generates a handbook as an operator-readable artifact.

Failure prevented: operators encountering a reason code with no plain-language
action, blocking diagnosis and repair.

Signal improved: operator handbook coverage; plain-language action completeness.

Reason codes:
  rfx_handbook_missing_action      — reason code entry lacks a plain-language action
  rfx_handbook_missing_owner       — reason code entry lacks an owner context
  rfx_handbook_empty               — no reason code entries supplied
  rfx_handbook_duplicate_code      — two entries share the same reason code
  rfx_handbook_missing_code        — entry has a blank or missing reason code field
  rfx_handbook_malformed_entry     — a reason code entry row is not a dict
"""

from __future__ import annotations

from typing import Any


def build_rfx_operator_handbook(
    *,
    reason_code_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build an operator handbook from a list of reason code registry entries.

    Each entry must have:
      ``code``           — the reason code string
      ``plain_action``   — plain-language description of what to do
      ``owner_context``  — canonical owner system context
      ``failure_prevented`` — what failure this code signals
    """
    reason: list[str] = []
    handbook_entries: list[dict[str, Any]] = []
    seen_codes: set[str] = set()

    if not reason_code_entries:
        reason.append("rfx_handbook_empty")
        return {
            "artifact_type": "rfx_operator_handbook",
            "schema_version": "1.0.0",
            "entries": handbook_entries,
            "reason_codes_emitted": sorted(set(reason)),
            "status": "incomplete",
            "signals": {
                "total_codes": 0,
                "covered_codes": 0,
                "coverage_rate": 0.0,
            },
        }

    for entry in reason_code_entries:
        if not isinstance(entry, dict):
            reason.append("rfx_handbook_malformed_entry")
            continue
        code = str(entry.get("code") or "").strip()
        if not code:
            reason.append("rfx_handbook_missing_code")
            continue

        if code in seen_codes:
            reason.append("rfx_handbook_duplicate_code")
        seen_codes.add(code)

        plain_action = str(entry.get("plain_action") or "").strip()
        if not plain_action:
            reason.append("rfx_handbook_missing_action")

        owner_context = str(entry.get("owner_context") or "").strip()
        if not owner_context:
            reason.append("rfx_handbook_missing_owner")

        handbook_entries.append({
            "code": code,
            "plain_action": plain_action or None,
            "owner_context": owner_context or None,
            "failure_prevented": str(entry.get("failure_prevented") or "").strip() or None,
            "severity": entry.get("severity", "medium"),
        })

    covered_codes = sum(1 for e in handbook_entries if e.get("plain_action"))
    total_codes = len(handbook_entries)
    unique_reasons = sorted(set(reason))
    return {
        "artifact_type": "rfx_operator_handbook",
        "schema_version": "1.0.0",
        "entries": handbook_entries,
        "reason_codes_emitted": unique_reasons,
        "status": "complete" if not unique_reasons else "incomplete",
        "signals": {
            "total_codes": total_codes,
            "covered_codes": covered_codes,
            "coverage_rate": covered_codes / max(total_codes, 1),
        },
    }
