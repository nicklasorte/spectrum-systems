"""Authority drift preflight gate.

A bounded shift-left helper invoked at admission time and during prompt
registry registration. It refuses to admit any new or modified surface
that fails ``authority_linter`` cleanliness, and emits a deterministic
``authority_drift_block_record`` artifact on failure.

This module is preparatory only. It does not adjudicate, decide, certify, or
enforce. It carries the canonical assertions to make that explicit. CDE/TPA/
GOV/SEL ownership boundaries are unchanged.

Files in scope (per task spec):
  * roadmap files       — ``docs/roadmap/``, ``docs/roadmaps/``
  * schemas             — ``contracts/schemas/`` and JSON Schema files
  * runtime modules     — ``spectrum_systems/modules/runtime/``
  * tests               — ``tests/``

Files outside scope short-circuit to admission_pass to avoid spurious blocks
on documentation that is not yet matrix-governed.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from spectrum_systems.modules.runtime.authority_linter import (
    AuthorityLinterError,
    lint_file,
    load_authority_matrix,
)

REPO_ROOT = Path(__file__).resolve().parents[3]

PREFLIGHT_SCOPE_PREFIXES: tuple[str, ...] = (
    "docs/roadmap/",
    "docs/roadmaps/",
    "contracts/schemas/",
    "spectrum_systems/modules/runtime/",
    "tests/",
)


class AuthorityDriftBlocked(ValueError):
    """Raised by the preflight when admission must fail closed.

    The exception carries the ``authority_drift_block_record`` artifact in the
    ``record`` attribute so callers can persist it without re-running the lint.
    """

    def __init__(self, record: dict[str, Any]) -> None:
        super().__init__(record.get("reason_code", "SHADOW_OWNERSHIP_OVERLAP"))
        self.record = record


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _hash(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _normalize(rel: str) -> str:
    rel = rel.replace("\\", "/").lstrip("./")
    prefix = str(REPO_ROOT).replace("\\", "/") + "/"
    if rel.startswith(prefix):
        rel = rel[len(prefix) :]
    return rel


def _in_scope(rel: str) -> bool:
    return any(rel.startswith(prefix) for prefix in PREFLIGHT_SCOPE_PREFIXES)


def authority_linter_clean(paths: Iterable[str | Path]) -> bool:
    """Convenience wrapper. True when no in-scope path has drift findings."""
    try:
        result = run_preflight(paths)
    except AuthorityDriftBlocked:
        return False
    return result["status"] == "pass"


def run_preflight(
    paths: Iterable[str | Path],
    *,
    raise_on_block: bool = False,
    now: str | None = None,
) -> dict[str, Any]:
    """Lint each in-scope path; build a pass record or block record.

    On clean: returns ``{"status": "pass", ...}``.
    On dirty: returns an ``authority_drift_block_record`` dict and, if
    ``raise_on_block`` is True, raises :class:`AuthorityDriftBlocked` with the
    same record.
    """
    try:
        matrix = load_authority_matrix()
    except AuthorityLinterError as exc:
        record = _block_record(
            reason="authority_matrix_unavailable",
            findings=[],
            scanned=[],
            now=now or _now(),
            extra={"error": str(exc)},
        )
        if raise_on_block:
            raise AuthorityDriftBlocked(record) from exc
        return record

    scanned: list[str] = []
    findings: list[dict[str, Any]] = []
    for raw in paths:
        rel = _normalize(str(raw))
        if not rel:
            continue
        if not _in_scope(rel):
            continue
        full = REPO_ROOT / rel
        if not full.is_file():
            continue
        scanned.append(rel)
        findings.extend(lint_file(full, matrix=matrix))

    if findings:
        record = _block_record(
            reason="SHADOW_OWNERSHIP_OVERLAP",
            findings=findings,
            scanned=scanned,
            now=now or _now(),
        )
        if raise_on_block:
            raise AuthorityDriftBlocked(record)
        return record

    return {
        "artifact_type": "authority_drift_preflight_pass",
        "schema_version": "1.0.0",
        "status": "pass",
        "scanned_paths": sorted(set(scanned)),
        "finding_count": 0,
        "generated_at": now or _now(),
    }


def _block_record(
    *,
    reason: str,
    findings: list[dict[str, Any]],
    scanned: list[str],
    now: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "artifact_type": "authority_drift_block_record",
        "schema_version": "1.0.0",
        "status": "halt",
        "reason_code": reason,
        "scanned_paths": sorted(set(scanned)),
        "finding_count": len(findings),
        "findings": findings,
        "generated_at": now,
    }
    if extra:
        record["context"] = extra
    record["record_hash"] = _hash(
        {
            "reason_code": reason,
            "findings": findings,
            "scanned_paths": sorted(set(scanned)),
        }
    )
    return record
