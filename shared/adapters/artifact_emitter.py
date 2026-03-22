"""
Artifact Emitter — shared utility for spectrum-systems modules.

Every module that produces a governed artifact must use these helpers to:
  1. emit artifact metadata
  2. emit a lineage record
  3. emit an evaluation result (or explicitly mark evaluation as pending)

The emitter also provides lightweight persistence helpers for storing and
loading records under the canonical data directory tree::

    data/artifacts/   ← artifact metadata
    data/lineage/     ← lineage records
    data/evaluations/ ← evaluation results
    data/work_items/  ← work items

Usage::

    from shared.adapters.artifact_emitter import (
        create_artifact_metadata,
        create_lineage_record,
        create_evaluation_result,
        save_artifact_record,
        load_artifact_record,
    )

    meta = create_artifact_metadata(
        artifact_id="EVAL-PIPELINE-2026-001",
        artifact_type="evaluation_manifest",
        module_origin="spectrum-pipeline-engine",
        lifecycle_state="evaluated",
        contract_version="1.0.0",
        policy_id="regression-policy-v1.0.0",
    )
    lineage = create_lineage_record(
        artifact_id="EVAL-PIPELINE-2026-001",
        parent_artifacts=["run-pipeline-2026-001"],
        producing_module="spectrum-pipeline-engine",
        run_id="run-pipeline-2026-001",
    )
    save_artifact_record("artifacts", "EVAL-PIPELINE-2026-001", meta)
    save_artifact_record("lineage", "EVAL-PIPELINE-2026-001", lineage)
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from jsonschema import Draft202012Validator, FormatChecker

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DATA_ROOT = _REPO_ROOT / "data"
_AUTHORITATIVE_PROVENANCE_SCHEMA_PATH = _REPO_ROOT / "schemas" / "provenance-schema.json"
_ARTIFACT_METADATA_SCHEMA_PATH = _REPO_ROOT / "shared" / "artifact_models" / "artifact_metadata.schema.json"
_POLICY_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]*-v\d+\.\d+\.\d+$")

# Valid lifecycle states (mirrors lifecycle_states.json)
_VALID_LIFECYCLE_STATES = frozenset({
    "input",
    "transformed",
    "evaluated",
    "action_required",
    "in_progress",
    "resolved",
    "re_evaluated",
    "closed",
})


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

def create_artifact_metadata(
    *,
    artifact_id: str,
    artifact_type: str,
    module_origin: str,
    lifecycle_state: str,
    contract_version: str,
    policy_id: str,
    schema_version: str = "1.0.0",
    run_id: Optional[str] = None,
    created_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a canonical artifact metadata dict.

    All string fields must be non-empty.  *lifecycle_state* must be one of
    the recognised states defined in ``lifecycle_states.json``.

    Raises :class:`ValueError` on invalid input.
    """
    _require_non_empty("artifact_id", artifact_id)
    _require_non_empty("artifact_type", artifact_type)
    _require_non_empty("module_origin", module_origin)
    _require_non_empty("contract_version", contract_version)
    _require_policy_id(policy_id)
    _require_lifecycle_state(lifecycle_state)

    record: Dict[str, Any] = {
        "artifact_id": artifact_id,
        "artifact_type": artifact_type,
        "module_origin": module_origin,
        "created_at": created_at or _now_iso(),
        "lifecycle_state": lifecycle_state,
        "contract_version": contract_version,
        "policy_id": policy_id,
        "schema_version": schema_version,
    }
    if run_id:
        record["run_id"] = run_id
    _validate_artifact_metadata_record(record)
    return record


def create_provenance_record(
    *,
    record_id: str,
    record_type: str,
    source_document: str,
    source_revision: str,
    workflow_name: str,
    workflow_step: str,
    generated_by_system: str,
    generated_by_repo: str,
    generated_by_version: str,
    policy_id: str,
    trace_id: str,
    span_id: str,
    created_at: Optional[str] = None,
    updated_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Build and validate provenance for the primary runtime emission path."""
    _require_non_empty("record_id", record_id)
    _require_non_empty("record_type", record_type)
    _require_non_empty("source_document", source_document)
    _require_non_empty("source_revision", source_revision)
    _require_non_empty("workflow_name", workflow_name)
    _require_non_empty("workflow_step", workflow_step)
    _require_non_empty("generated_by_system", generated_by_system)
    _require_non_empty("generated_by_repo", generated_by_repo)
    _require_non_empty("generated_by_version", generated_by_version)
    _require_policy_id(policy_id)
    _require_non_empty("trace_id", trace_id)
    _require_non_empty("span_id", span_id)

    now = _now_iso()
    record: Dict[str, Any] = {
        "record_id": record_id,
        "record_type": record_type,
        "source_document": source_document,
        "source_revision": source_revision,
        "workflow_name": workflow_name,
        "workflow_step": workflow_step,
        "generated_by_system": generated_by_system,
        "generated_by_repo": generated_by_repo,
        "generated_by_version": generated_by_version,
        "policy_id": policy_id,
        "trace_id": trace_id,
        "span_id": span_id,
        "schema_version": "1.1.0",
        "created_at": created_at or now,
        "updated_at": updated_at or now,
    }
    _validate_provenance_record(record)
    return record


def create_lineage_record(
    *,
    artifact_id: str,
    parent_artifacts: List[str],
    producing_module: str,
    run_id: str,
    timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a canonical lineage record dict.

    *parent_artifacts* may be an empty list for root / input artifacts.

    Raises :class:`ValueError` on invalid input.
    """
    _require_non_empty("artifact_id", artifact_id)
    _require_non_empty("producing_module", producing_module)
    _require_non_empty("run_id", run_id)
    if not isinstance(parent_artifacts, list):
        raise ValueError("parent_artifacts must be a list")

    return {
        "artifact_id": artifact_id,
        "parent_artifacts": list(parent_artifacts),
        "producing_module": producing_module,
        "run_id": run_id,
        "timestamp": timestamp or _now_iso(),
    }


def create_evaluation_result(
    *,
    artifact_id: str,
    status: str,
    action_required: bool,
    rationale: str,
    evaluation_id: Optional[str] = None,
    linked_work_item_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a canonical evaluation result dict.

    Enforcement rules:
    - *status* must be one of ``pass``, ``fail``, ``partial``.
    - *action_required* must be a bool.
    - *rationale* must be non-empty.
    - When *action_required* is ``True``, *linked_work_item_id* must be
      a non-empty string.

    Raises :class:`ValueError` on constraint violations.
    """
    _require_non_empty("artifact_id", artifact_id)
    _require_non_empty("rationale", rationale)

    valid_statuses = {"pass", "fail", "partial"}
    if status not in valid_statuses:
        raise ValueError(
            f"evaluation status must be one of {sorted(valid_statuses)}, got '{status}'"
        )
    if not isinstance(action_required, bool):
        raise ValueError("action_required must be a boolean")

    if action_required and not linked_work_item_id:
        raise ValueError(
            "action_required=True requires a non-empty linked_work_item_id. "
            "Create a work item and supply its ID."
        )

    return {
        "evaluation_id": evaluation_id or f"EVAL-{uuid.uuid4().hex[:8].upper()}",
        "artifact_id": artifact_id,
        "status": status,
        "action_required": action_required,
        "rationale": rationale,
        "linked_work_item_id": linked_work_item_id,
    }


def create_work_item(
    *,
    source_artifact_id: str,
    priority: str,
    work_item_id: Optional[str] = None,
    status: str = "open",
    created_at: Optional[str] = None,
    resolution_notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a canonical data-backbone work item dict.

    Raises :class:`ValueError` on invalid input.
    """
    _require_non_empty("source_artifact_id", source_artifact_id)

    valid_priorities = {"critical", "high", "medium", "low"}
    if priority not in valid_priorities:
        raise ValueError(
            f"priority must be one of {sorted(valid_priorities)}, got '{priority}'"
        )

    valid_statuses = {"open", "in_progress", "resolved", "deferred"}
    if status not in valid_statuses:
        raise ValueError(
            f"status must be one of {sorted(valid_statuses)}, got '{status}'"
        )

    record: Dict[str, Any] = {
        "work_item_id": work_item_id or f"WI-{uuid.uuid4().hex[:8].upper()}",
        "source_artifact_id": source_artifact_id,
        "status": status,
        "priority": priority,
        "created_at": created_at or _now_iso(),
    }
    if resolution_notes:
        record["resolution_notes"] = resolution_notes
    return record


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

_STORE_NAMES = frozenset({"artifacts", "lineage", "evaluations", "work_items"})


def save_artifact_record(
    store: str,
    record_id: str,
    record: Dict[str, Any],
    data_root: Optional[Path] = None,
) -> Path:
    """Persist *record* as ``<data_root>/<store>/<record_id>.json``.

    *store* must be one of ``artifacts``, ``lineage``, ``evaluations``,
    ``work_items``.

    Returns the path written.

    Raises :class:`ValueError` for unknown *store* names.
    """
    if store not in _STORE_NAMES:
        raise ValueError(
            f"Unknown store '{store}'. Valid stores: {sorted(_STORE_NAMES)}"
        )
    root = (data_root or _DATA_ROOT) / store
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{record_id}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_artifact_record(
    store: str,
    record_id: str,
    data_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Load and return the record at ``<data_root>/<store>/<record_id>.json``.

    Raises :class:`ValueError` for unknown *store* names.
    Raises :class:`FileNotFoundError` when the record does not exist.
    """
    if store not in _STORE_NAMES:
        raise ValueError(
            f"Unknown store '{store}'. Valid stores: {sorted(_STORE_NAMES)}"
        )
    root = (data_root or _DATA_ROOT) / store
    path = root / f"{record_id}.json"
    if not path.is_file():
        raise FileNotFoundError(
            f"Record not found: {path}"
        )
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Enforcement / validation helpers
# ---------------------------------------------------------------------------

def validate_artifact_has_metadata(artifact_id: str, data_root: Optional[Path] = None) -> None:
    """Raise :class:`ValueError` when no metadata record exists for *artifact_id*."""
    try:
        load_artifact_record("artifacts", artifact_id, data_root)
    except FileNotFoundError:
        raise ValueError(
            f"Artifact '{artifact_id}' has no metadata record. "
            "Emit artifact metadata before advancing lifecycle state."
        )


def validate_artifact_has_lineage(artifact_id: str, data_root: Optional[Path] = None) -> None:
    """Raise :class:`ValueError` when no lineage record exists for *artifact_id*."""
    try:
        load_artifact_record("lineage", artifact_id, data_root)
    except FileNotFoundError:
        raise ValueError(
            f"Artifact '{artifact_id}' has no lineage record. "
            "Emit a lineage record before advancing lifecycle state."
        )


def validate_artifact_has_evaluation(artifact_id: str, data_root: Optional[Path] = None) -> None:
    """Raise :class:`ValueError` when no evaluation result exists for *artifact_id*."""
    try:
        load_artifact_record("evaluations", artifact_id, data_root)
    except FileNotFoundError:
        raise ValueError(
            f"Artifact '{artifact_id}' has no evaluation result. "
            "Emit an evaluation result (or mark as pending) before promotion."
        )


def validate_action_required_has_work_item(
    evaluation_result: Dict[str, Any],
    data_root: Optional[Path] = None,
) -> None:
    """Raise :class:`ValueError` when action_required=True but no work item exists.

    Checks that a work item record is present in the ``work_items`` store for
    the ``linked_work_item_id`` referenced in *evaluation_result*.
    """
    if not evaluation_result.get("action_required"):
        return  # no work item required

    linked_id = evaluation_result.get("linked_work_item_id")
    if not linked_id:
        raise ValueError(
            "action_required=True but linked_work_item_id is missing in evaluation result. "
            "Create a work item and link it."
        )
    try:
        load_artifact_record("work_items", linked_id, data_root)
    except FileNotFoundError:
        raise ValueError(
            f"action_required=True but work item '{linked_id}' does not exist in the "
            "work_items store. Create the work item record before promotion."
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _require_non_empty(field: str, value: str) -> None:
    if not value or not str(value).strip():
        raise ValueError(f"'{field}' must be a non-empty string, got: {value!r}")


def _require_lifecycle_state(state: str) -> None:
    if state not in _VALID_LIFECYCLE_STATES:
        raise ValueError(
            f"lifecycle_state '{state}' is not recognised. "
            f"Valid states: {sorted(_VALID_LIFECYCLE_STATES)}"
        )


def _require_policy_id(policy_id: str) -> None:
    _require_non_empty("policy_id", policy_id)
    if _POLICY_ID_PATTERN.fullmatch(policy_id) is None:
        raise ValueError(
            "policy_id must match pattern "
            "'^[a-z][a-z0-9-]*-v\\d+\\.\\d+\\.\\d+$'"
        )


def _validate_artifact_metadata_record(record: Dict[str, Any]) -> None:
    schema = json.loads(_ARTIFACT_METADATA_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(record), key=lambda err: list(err.path))
    if errors:
        raise ValueError(f"artifact metadata schema validation failed: {errors[0].message}")


def _validate_provenance_record(record: Dict[str, Any]) -> None:
    schema = json.loads(_AUTHORITATIVE_PROVENANCE_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(record), key=lambda err: list(err.path))
    if errors:
        raise ValueError(f"provenance schema validation failed: {errors[0].message}")
