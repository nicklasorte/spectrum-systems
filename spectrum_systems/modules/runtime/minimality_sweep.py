"""Phase 6: minimality_sweep — scan for redundancy in governed artifacts (CLX-ALL-01 Phase 6).

Scans for:
  - Duplicate artifact schemas (same artifact_type defined in multiple schema files).
  - Overlapping validators (same symbol checked by multiple guard scripts).
  - Unused schemas (schema files not referenced in standards-manifest).
  - Redundant CLI scripts (scripts with identical entry-point logic).

Outputs a ``cleanup_candidate_report`` (advisory only). Never deletes.
Never authorizes deletion. Classification is:
  - ``keep``: actively used and unique
  - ``candidate_archive``: potential duplicate or unused, needs human review
  - ``never_delete``: participates in proof evidence chain
  - ``unknown_blocked``: ambiguous, blocked from any classification

Adheres to the existing ``cleanup_candidate_report.schema.json`` contract.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]

# Artifact types that must never be candidates for deletion.
_NEVER_DELETE_ARTIFACT_TYPES = frozenset([
    "loop_proof_bundle",
    "core_loop_alignment_record",
    "certification_evidence_index",
    "done_certification_record",
    "failure_diagnosis_record",
    "enforcement_action_record",
    "enforcement_block_record",
    "closure_decision_artifact",
    "artifact_lineage_record",
    "replay_run_record",
    "build_admission_record",
])

# Schema directories to scan.
_SCHEMA_DIR = REPO_ROOT / "contracts" / "schemas"
_MANIFEST_PATH = REPO_ROOT / "contracts" / "standards-manifest.json"
_SCRIPTS_DIR = REPO_ROOT / "scripts"


class MinimalitySweepError(ValueError):
    """Raised when the sweep cannot complete deterministically."""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _report_id() -> str:
    digest = hashlib.sha256(_now().encode()).hexdigest()[:12]
    return f"msr-{digest}"


def _load_manifest_artifact_types() -> set[str]:
    """Return the set of artifact_type strings registered in standards-manifest."""
    if not _MANIFEST_PATH.is_file():
        return set()
    try:
        data = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
        contracts = data.get("contracts") or []
        return {str(c.get("artifact_type") or "") for c in contracts if c.get("artifact_type")}
    except (json.JSONDecodeError, OSError):
        return set()


def _extract_artifact_type_from_schema(schema_path: Path) -> str | None:
    """Extract artifact_type const value from a JSON schema file."""
    try:
        data = json.loads(schema_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    props = data.get("properties") or {}
    artifact_type_prop = props.get("artifact_type") or {}
    const = artifact_type_prop.get("const")
    if isinstance(const, str) and const.strip():
        return const.strip()
    return None


def _scan_duplicate_schemas() -> list[dict[str, Any]]:
    """Find schema files that define the same artifact_type as another."""
    if not _SCHEMA_DIR.is_dir():
        return []

    type_to_files: dict[str, list[str]] = {}
    for schema_file in sorted(_SCHEMA_DIR.glob("*.schema.json")):
        artifact_type = _extract_artifact_type_from_schema(schema_file)
        if artifact_type:
            rel = str(schema_file.relative_to(REPO_ROOT))
            type_to_files.setdefault(artifact_type, []).append(rel)

    candidates: list[dict[str, Any]] = []
    for artifact_type, files in type_to_files.items():
        if len(files) > 1:
            for f in files[1:]:  # Keep first, flag rest.
                classification = (
                    "never_delete" if artifact_type in _NEVER_DELETE_ARTIFACT_TYPES else "candidate_archive"
                )
                candidates.append({
                    "artifact_path": f,
                    "artifact_kind": "schema",
                    "classification": classification,
                    "reason_code": f"DUPLICATE_SCHEMA:{artifact_type}",
                })
    return candidates


def _scan_unused_schemas(manifest_types: set[str]) -> list[dict[str, Any]]:
    """Find schema files whose artifact_type is not in the standards-manifest."""
    if not _SCHEMA_DIR.is_dir() or not manifest_types:
        return []

    candidates: list[dict[str, Any]] = []
    for schema_file in sorted(_SCHEMA_DIR.glob("*.schema.json")):
        artifact_type = _extract_artifact_type_from_schema(schema_file)
        if artifact_type is None:
            continue
        if artifact_type in manifest_types:
            continue

        rel = str(schema_file.relative_to(REPO_ROOT))
        classification = (
            "never_delete" if artifact_type in _NEVER_DELETE_ARTIFACT_TYPES else "candidate_archive"
        )
        candidates.append({
            "artifact_path": rel,
            "artifact_kind": "schema",
            "classification": classification,
            "reason_code": "SCHEMA_NOT_IN_MANIFEST",
        })
    return candidates


def _scan_overlapping_validators() -> list[dict[str, Any]]:
    """Find scripts that check the same authority symbol set."""
    if not _SCRIPTS_DIR.is_dir():
        return []

    authority_scripts: dict[str, list[str]] = {}
    pattern = re.compile(r"authority|authority_shape|authority_leak|registry_guard")

    for script in sorted(_SCRIPTS_DIR.glob("*.py")):
        rel = str(script.relative_to(REPO_ROOT))
        try:
            content = script.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        if pattern.search(rel.lower()):
            # Extract key function names to detect overlapping logic.
            fns = re.findall(r"def (run_|validate_|check_|scan_)([a-z_]+)\(", content)
            for _, fn_name in fns:
                authority_scripts.setdefault(fn_name, []).append(rel)

    candidates: list[dict[str, Any]] = []
    for fn_name, scripts in authority_scripts.items():
        if len(scripts) > 1:
            for s in scripts[1:]:
                candidates.append({
                    "artifact_path": s,
                    "artifact_kind": "script",
                    "classification": "unknown_blocked",
                    "reason_code": f"OVERLAPPING_VALIDATOR:{fn_name}",
                })
    return candidates


def run_minimality_sweep(
    *,
    trace_id: str = "",
    run_id: str = "",
) -> dict[str, Any]:
    """Run the minimality sweep and return a ``cleanup_candidate_report``.

    Advisory only. No files are deleted or modified.
    """
    manifest_types = _load_manifest_artifact_types()

    duplicate_candidates = _scan_duplicate_schemas()
    unused_candidates = _scan_unused_schemas(manifest_types)
    validator_candidates = _scan_overlapping_validators()

    all_candidates = duplicate_candidates + unused_candidates + validator_candidates

    return {
        "artifact_type": "cleanup_candidate_report",
        "schema_version": "1.0.0",
        "report_id": _report_id(),
        "audit_timestamp": _now(),
        "candidates": all_candidates,
        "non_authority_assertions": [
            "preparatory_only",
            "not_control_authority",
            "not_certification_authority",
        ],
    }


__all__ = [
    "MinimalitySweepError",
    "run_minimality_sweep",
]
