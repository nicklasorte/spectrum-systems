"""Authority drift repair engine.

Converts SHADOW_OWNERSHIP_OVERLAP findings from
``spectrum_systems.modules.runtime.authority_linter`` into a deterministic
``repair_plan_artifact`` and ``authority_repair_diff``.

This module is bounded:
  * It does not write files. It returns artifacts only.
  * It does not reproduce CDE/TPA/GOV/SEL logic. It only proposes textual
    rewrites that match the canonical owner already named in the matrix.
  * It fails closed if the matrix or input file is missing or unreadable.

The artifact shapes are intentionally narrow so they can flow into existing
FRE adapters without schema migration.
"""

from __future__ import annotations

import difflib
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from spectrum_systems.guards.authority_linter import (
    AuthorityLinterError,
    apply_authority_repair,
    detect_authority_drift,
    load_authority_matrix,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


class AuthorityRepairError(ValueError):
    """Raised when the repair engine cannot complete deterministically."""


def _hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _relative(path: Path) -> str:
    rel = str(path).replace("\\", "/")
    prefix = str(REPO_ROOT).replace("\\", "/") + "/"
    if rel.startswith(prefix):
        rel = rel[len(prefix) :]
    return rel


def repair_authority_drift(
    file_path: str | Path,
    *,
    matrix: dict[str, Any] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Build a ``repair_plan_artifact`` for the authority drift in ``file_path``.

    Returns a dict with the following top-level keys:

    * ``artifact_type`` — always ``"repair_plan_artifact"``.
    * ``repair_plan`` — input/output hashes, finding count, suggested fixes.
    * ``authority_repair_diff`` — unified-diff string between original and
      repaired content (empty when no findings).
    * ``findings`` — the underlying linter findings, for traceability.

    The function reads ``file_path`` once. It never writes.
    """
    target = Path(file_path)
    if not target.is_absolute():
        target = REPO_ROOT / target
    if not target.is_file():
        raise AuthorityRepairError(f"target file does not exist: {target}")

    try:
        original = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise AuthorityRepairError(f"failed to read {target}: {exc}") from exc

    try:
        active_matrix = matrix if matrix is not None else load_authority_matrix()
    except AuthorityLinterError as exc:
        raise AuthorityRepairError(str(exc)) from exc

    findings = detect_authority_drift(original, matrix=active_matrix)
    repaired = apply_authority_repair(original, findings)

    rel = _relative(target)
    diff_lines = list(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            repaired.splitlines(keepends=True),
            fromfile=f"a/{rel}",
            tofile=f"b/{rel}",
            n=3,
        )
    )
    diff_text = "".join(diff_lines)

    artifact: dict[str, Any] = {
        "artifact_type": "repair_plan_artifact",
        "schema_version": "1.0.0",
        "generated_at": now or _now(),
        "target_path": rel,
        "repair_plan": {
            "reason_code": "SHADOW_OWNERSHIP_OVERLAP",
            "finding_count": len(findings),
            "input_hash": _hash(original),
            "output_hash": _hash(repaired),
            "deterministic": True,
            "suggested_fixes": [
                {
                    "system": str(f["system"]),
                    "verb": str(f["verb"]),
                    "canonical_owner": f.get("canonical_owner"),
                    "line": int(f["line"]),
                    "match": str(f["match"]),
                    "suggested_fix": str(f["suggested_fix"]),
                }
                for f in findings
            ],
        },
        "authority_repair_diff": diff_text,
        "findings": findings,
    }
    return artifact


def repair_text(text: str, *, matrix: dict[str, Any] | None = None) -> tuple[str, list[dict[str, Any]]]:
    """In-memory variant for unit tests. Returns ``(repaired_text, findings)``."""
    try:
        active_matrix = matrix if matrix is not None else load_authority_matrix()
    except AuthorityLinterError as exc:
        raise AuthorityRepairError(str(exc)) from exc
    findings = detect_authority_drift(text, matrix=active_matrix)
    repaired = apply_authority_repair(text, findings)
    return repaired, findings
