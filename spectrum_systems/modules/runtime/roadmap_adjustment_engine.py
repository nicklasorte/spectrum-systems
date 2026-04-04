"""Deterministic governed roadmap self-adaptation engine (BATCH-A4)."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class RoadmapAdjustmentError(ValueError):
    """Raised when roadmap adjustment derivation/application fails closed."""


_ADJUSTMENT_TYPES = {"insert", "reorder", "defer", "block", "annotate"}


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _validate_schema(instance: dict[str, Any], schema_name: str, *, label: str) -> None:
    validator = Draft202012Validator(load_schema(schema_name), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.absolute_path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise RoadmapAdjustmentError(f"{label} failed schema validation ({schema_name}): {details}")


def _roadmap_type(roadmap: dict[str, Any]) -> str:
    if "schema_version" in roadmap and "generated_at" in roadmap:
        return "roadmap_artifact"
    if "version" in roadmap and "created_at" in roadmap:
        return "system_roadmap"
    raise RoadmapAdjustmentError("unsupported roadmap artifact for adjustments")


def derive_roadmap_adjustments(
    *,
    roadmap_artifact: dict[str, Any],
    exception_resolution_record: dict[str, Any],
    batch_handoff_bundle: dict[str, Any],
    eval_coverage_signal: dict[str, Any] | None,
    drift_signals: dict[str, Any] | None,
    unresolved_risks: list[str] | None,
    created_at: str,
) -> list[dict[str, Any]]:
    if not isinstance(created_at, str) or not created_at.strip():
        raise RoadmapAdjustmentError("created_at is required")

    roadmap_id = str(roadmap_artifact.get("roadmap_id") or "")
    if not roadmap_id:
        raise RoadmapAdjustmentError("roadmap_id is required")

    source_batch_id = str(batch_handoff_bundle.get("source_batch_id") or "BATCH-UNKNOWN")
    exception_ref = str(exception_resolution_record.get("exception_classification_ref") or "exception_classification_record:ECR-UNKNOWN")
    trace_id = str(batch_handoff_bundle.get("trace_id") or exception_resolution_record.get("trace_id") or "")
    if not trace_id:
        raise RoadmapAdjustmentError("trace_id is required")

    pending_batches = [
        str(batch.get("batch_id"))
        for batch in roadmap_artifact.get("batches", [])
        if isinstance(batch, dict) and str(batch.get("status")) in {"not_started", "blocked"}
    ]
    target_batch_id = pending_batches[0] if pending_batches else source_batch_id

    exception_class = str(batch_handoff_bundle.get("latest_exception_class") or "unknown_blocker")
    review_required = bool(exception_resolution_record.get("requires_human_review", False))
    coverage_missing = bool((eval_coverage_signal or {}).get("coverage_gap_detected", False) or exception_class == "missing_eval_coverage")
    drift_detected = bool((drift_signals or {}).get("drift_detected", False) or exception_class in {"drift_detected", "replay_mismatch"})
    repeated_failure = bool((drift_signals or {}).get("repeated_failure", False))
    unresolved_critical = sorted(
        set(item for item in (unresolved_risks or []) if isinstance(item, str) and ("critical" in item.lower() or item.startswith("AUTH_")))
    )

    adjustments: list[dict[str, Any]] = []

    def _emit(adj_type: str, *, reason_codes: list[str], supporting_signals: list[str], target: str, new_position: int | None = None) -> None:
        if adj_type not in _ADJUSTMENT_TYPES:
            raise RoadmapAdjustmentError(f"unsupported adjustment type: {adj_type}")
        seed = {
            "roadmap_id": roadmap_id,
            "source_batch_id": source_batch_id,
            "exception_ref": exception_ref,
            "adjustment_type": adj_type,
            "target_batch_id": target,
            "new_position": new_position,
            "reason_codes": sorted(reason_codes),
            "supporting_signals": sorted(supporting_signals),
            "trace_id": trace_id,
        }
        adj = {
            "adjustment_id": f"RADJ-{_canonical_hash(seed)[:12].upper()}",
            "roadmap_id": roadmap_id,
            "source_batch_id": source_batch_id,
            "source_exception_ref": exception_ref,
            "adjustment_type": adj_type,
            "target_batch_id": target,
            "new_position": new_position,
            "reason_codes": sorted(reason_codes),
            "supporting_signals": sorted(supporting_signals),
            "affected_dependencies": [],
            "safety_classification": "hard_gate_block" if adj_type == "block" else "governed_change",
            "requires_human_review": review_required or adj_type in {"block", "reorder"},
            "created_at": created_at,
            "trace_id": trace_id,
        }
        _validate_schema(adj, "roadmap_adjustment_record", label="roadmap_adjustment_record")
        adjustments.append(adj)

    if coverage_missing and target_batch_id:
        _emit(
            "insert",
            reason_codes=["missing_eval_coverage"],
            supporting_signals=["eval_coverage_gap"],
            target=target_batch_id,
            new_position=1,
        )

    if drift_detected and target_batch_id:
        _emit(
            "defer",
            reason_codes=["drift_detected"],
            supporting_signals=["drift_signal"],
            target=target_batch_id,
            new_position=len(pending_batches) + 1,
        )

    if unresolved_critical and target_batch_id:
        _emit(
            "block",
            reason_codes=["unresolved_critical_risk"],
            supporting_signals=unresolved_critical,
            target=target_batch_id,
        )

    if review_required and target_batch_id:
        _emit(
            "annotate",
            reason_codes=["review_required"],
            supporting_signals=["human_review_required"],
            target=target_batch_id,
        )

    if repeated_failure and target_batch_id:
        _emit(
            "reorder",
            reason_codes=["repeated_failure"],
            supporting_signals=["failure_recurrence_detected"],
            target=target_batch_id,
            new_position=1,
        )

    return sorted(adjustments, key=lambda item: (str(item["adjustment_type"]), str(item["target_batch_id"]), str(item["adjustment_id"])))


def apply_roadmap_adjustments(*, roadmap_artifact: dict[str, Any], adjustments: list[dict[str, Any]], created_at: str) -> dict[str, Any]:
    roadmap_kind = _roadmap_type(roadmap_artifact)
    schema_name = roadmap_kind
    _validate_schema(roadmap_artifact, schema_name, label=schema_name)

    for record in adjustments:
        _validate_schema(record, "roadmap_adjustment_record", label="roadmap_adjustment_record")

    updated = copy.deepcopy(roadmap_artifact)
    batch_rows = [dict(row) for row in updated.get("batches", []) if isinstance(row, dict)]

    by_id = {str(row.get("batch_id")): index for index, row in enumerate(batch_rows)}

    def _resolve_insert_batch_id() -> str:
        for candidate in ["BATCH-E", "BATCH-R", "BATCH-D", "BATCH-Z"]:
            if candidate not in by_id:
                return candidate
        raise RoadmapAdjustmentError("no deterministic insert batch id available")

    for record in sorted(adjustments, key=lambda item: str(item["adjustment_id"])):
        batch_id = str(record["target_batch_id"])
        if batch_id not in by_id:
            raise RoadmapAdjustmentError(f"adjustment target batch does not exist: {batch_id}")
        idx = by_id[batch_id]
        adj_type = str(record["adjustment_type"])

        if adj_type == "block":
            batch_rows[idx]["status"] = "blocked"
        elif adj_type == "annotate":
            if roadmap_kind == "roadmap_artifact":
                title = str(batch_rows[idx].get("title") or batch_id)
                if not title.startswith("[REVIEW_REQUIRED]"):
                    batch_rows[idx]["title"] = f"[REVIEW_REQUIRED] {title}"
            else:
                desc = str(batch_rows[idx].get("description") or "")
                tag = "[review_required]"
                if tag not in desc:
                    batch_rows[idx]["description"] = f"{tag} {desc}".strip()
        elif adj_type == "reorder":
            row = batch_rows.pop(idx)
            batch_rows.insert(0, row)
        elif adj_type == "defer":
            row = batch_rows.pop(idx)
            batch_rows.append(row)
        elif adj_type == "insert":
            insert_id = _resolve_insert_batch_id()
            target = batch_rows[idx]
            inherited_deps = list(target.get("depends_on", []))
            if roadmap_kind == "roadmap_artifact":
                inserted = {
                    "batch_id": insert_id,
                    "title": "Deterministic Eval Coverage Remediation",
                    "step_ids": ["RDX-A4-EVAL"],
                    "depends_on": inherited_deps,
                    "required_signals": ["eval_coverage_gap_resolved"],
                    "hard_gate_after": True,
                    "execution_mode": "pqx_batch",
                    "trust_goal": "eval_coverage_integrity",
                    "status": "not_started",
                }
            else:
                max_priority = max(int(item.get("priority", 0)) for item in batch_rows)
                inserted = {
                    "batch_id": f"A4-EVAL-{max_priority+1:03d}",
                    "acronym": "A4",
                    "title": "Eval Coverage Remediation",
                    "goal": "Close required eval coverage gap before downstream execution",
                    "depends_on": inherited_deps,
                    "hard_gate": True,
                    "priority": max_priority + 1,
                    "status": "not_started",
                    "allowed_when": ["dependencies_completed"],
                    "stop_conditions": ["missing_required_artifact", "failed_required_test", "hard_gate_failed"],
                    "artifacts_expected": ["a4_eval_remediation_artifact"],
                    "tests_required": ["pytest tests/test_roadmap_multi_batch_executor.py"],
                    "description": "A4 inserted deterministic remediation batch.",
                }
            target["depends_on"] = [inserted["batch_id"]]
            batch_rows.insert(idx, inserted)
        else:
            raise RoadmapAdjustmentError(f"unsupported adjustment type: {adj_type}")

        by_id = {str(row.get("batch_id")): i for i, row in enumerate(batch_rows)}

    for row in batch_rows:
        deps = row.get("depends_on", [])
        if any(dep not in by_id for dep in deps):
            raise RoadmapAdjustmentError(f"broken dependency detected for {row.get('batch_id')}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def _dfs(node: str) -> None:
        if node in visited:
            return
        if node in visiting:
            raise RoadmapAdjustmentError("dependency cycle introduced")
        visiting.add(node)
        for dep in batch_rows[by_id[node]].get("depends_on", []):
            _dfs(dep)
        visiting.remove(node)
        visited.add(node)

    for node in by_id:
        _dfs(node)

    updated["batches"] = batch_rows
    if roadmap_kind == "system_roadmap":
        updated["created_at"] = created_at
        for i, row in enumerate(updated["batches"], start=1):
            row["priority"] = i
        updated["version"] = _bump_patch(str(updated.get("version", "1.0.0")))
    else:
        updated["generated_at"] = created_at

    _validate_schema(updated, schema_name, label=f"updated_{schema_name}")
    return updated


def _bump_patch(version: str) -> str:
    parts = version.split(".")
    if len(parts) != 3 or any(not piece.isdigit() for piece in parts):
        raise RoadmapAdjustmentError("system_roadmap version must be semver")
    return f"{parts[0]}.{parts[1]}.{int(parts[2]) + 1}"


__all__ = ["RoadmapAdjustmentError", "derive_roadmap_adjustments", "apply_roadmap_adjustments"]
