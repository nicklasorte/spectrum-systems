"""FRE: authority_repair_candidate_generator — bounded repair from preflight failure packets (CLX-ALL-01 Phase 1).

Consumes an ``authority_preflight_failure_packet`` and produces bounded
``authority_repair_candidate`` artifacts containing rename/vocabulary-correction
patches only.

Constraints (hard):
  - Never introduces new ownership.
  - Only proposes rename or vocabulary_correction patch types.
  - Structural or semantic expansion is BLOCKED.
  - CDE must authorize before PQX applies any patch.
  - Guard scripts and canonical-owner files are excluded from patching.

This module is FRE-bounded: it produces repair candidates, not decisions.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]

# Canonical owner sets — only these may be used as replacements.
_CANONICAL_OWNERS = frozenset(["AEX", "PQX", "EVL", "TPA", "CDE", "SEL", "FRE", "GOV", "LIN", "REP", "OBS"])

# Files that must never be patched.
_NEVER_PATCH_SUBSTRINGS = [
    "authority_shape_preflight",
    "authority_shape_early_gate",
    "authority_shape_vocabulary",
    "authority_leak_guard",
    "system_registry_guard",
    "authority_preflight_expanded",
    "run_authority",
    "validate_forbidden_authority",
    "authority_linter",
    "authority_repair_candidate_generator",
]

# Allowed patch types (CDE authorization constraint).
_ALLOWED_PATCH_TYPES = frozenset(["rename", "vocabulary_correction"])


class AuthorityRepairCandidateError(ValueError):
    """Raised when the generator cannot produce a deterministic candidate."""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _candidate_id(trace_id: str, source_packet_id: str) -> str:
    digest = hashlib.sha256(f"arc-{trace_id}-{source_packet_id}".encode()).hexdigest()[:12]
    return f"arc-{digest}"


def _is_never_patch(file_path: str) -> bool:
    low = file_path.lower()
    return any(sub in low for sub in _NEVER_PATCH_SUBSTRINGS)


def _first_replacement(suggestions: list[str]) -> str | None:
    """Return the first suggestion that uses a canonical safety suffix, or None."""
    safe_suffixes = ("_signal", "_observation", "_input", "_finding", "_evidence", "_advisory", "_record")
    for s in suggestions:
        if any(s.endswith(sfx) for sfx in safe_suffixes):
            return s
    return None


def _is_safe_rename(original: str, replacement: str) -> bool:
    """A rename is safe when it's a pure vocabulary correction with no semantic expansion."""
    if not original or not replacement:
        return False
    # Reject if replacement introduces new canonical system ownership terms.
    low_rep = replacement.lower()
    unsafe = ["_authority", "_owner", "_canonical", "_decides", "_enforces"]
    return not any(u in low_rep for u in unsafe)


def generate_authority_repair_candidates(
    *,
    failure_packet: dict[str, Any],
    trace_id: str,
    run_id: str = "",
) -> list[dict[str, Any]]:
    """Generate repair candidates from an ``authority_preflight_failure_packet``.

    Returns a list of ``authority_repair_candidate`` dicts. Each candidate
    covers one file with at least one patchable violation. Candidates for
    files that must never be patched are skipped.

    Raises ``AuthorityRepairCandidateError`` on invalid input.
    """
    if not isinstance(failure_packet, dict):
        raise AuthorityRepairCandidateError("failure_packet must be a dict")

    artifact_type = failure_packet.get("artifact_type", "")
    if artifact_type != "authority_preflight_failure_packet":
        raise AuthorityRepairCandidateError(
            f"Expected authority_preflight_failure_packet, got '{artifact_type}'"
        )

    packet_id = str(failure_packet.get("packet_id") or "")
    if not packet_id:
        raise AuthorityRepairCandidateError("failure_packet missing packet_id")

    violations: list[dict[str, Any]] = failure_packet.get("violations") or []

    # Group violations by file.
    by_file: dict[str, list[dict[str, Any]]] = {}
    for v in violations:
        f = str(v.get("file") or "")
        if not f:
            continue
        by_file.setdefault(f, []).append(v)

    candidates: list[dict[str, Any]] = []

    for file_path, file_violations in by_file.items():
        if _is_never_patch(file_path):
            continue

        patches: list[dict[str, Any]] = []
        safe_to_apply = True
        blocked_reason: str | None = None

        for v in file_violations:
            original_symbol = str(v.get("symbol") or "")
            suggestions = v.get("suggested_replacements") or []
            owners = v.get("canonical_owners") or []
            violation_type = v.get("violation_type", "vocabulary_violation")

            if not original_symbol:
                continue

            replacement = _first_replacement(suggestions)
            if replacement is None:
                safe_to_apply = False
                blocked_reason = f"No safe replacement found for symbol '{original_symbol}'"
                continue

            patch_type = "rename" if violation_type == "vocabulary_violation" else "vocabulary_correction"

            if not _is_safe_rename(original_symbol, replacement):
                safe_to_apply = False
                blocked_reason = f"Replacement '{replacement}' for '{original_symbol}' is not safe"
                continue

            canonical_owner = owners[0] if owners else "UNKNOWN"

            patches.append({
                "file": file_path,
                "line": v.get("line"),
                "original_symbol": original_symbol,
                "replacement_symbol": replacement,
                "patch_type": patch_type,
                "rationale": (
                    f"Rename '{original_symbol}' → '{replacement}' to remove "
                    f"authority-cluster term owned by {canonical_owner}."
                ),
                "canonical_owner": canonical_owner,
            })

        if not patches:
            continue

        candidate = {
            "artifact_type": "authority_repair_candidate",
            "schema_version": "1.0.0",
            "candidate_id": _candidate_id(trace_id, f"{packet_id}-{file_path}"),
            "trace_id": trace_id,
            "run_id": run_id,
            "source_packet_id": packet_id,
            "repair_type": "vocabulary_correction",
            "patches": patches,
            "safe_to_apply": safe_to_apply,
            "blocked_reason": blocked_reason,
            "producer_authority": "FRE",
            "non_authority_assertions": [
                "This candidate requires CDE authorization before PQX applies it.",
                "Only rename and vocabulary_correction patch types are permitted.",
                "Structural or semantic expansion is blocked.",
            ],
            "emitted_at": _now(),
        }
        candidates.append(candidate)

    return candidates


__all__ = [
    "AuthorityRepairCandidateError",
    "generate_authority_repair_candidates",
]
