"""Program direction layer for deterministic roadmap constraints and progress tracking."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


class ProgramLayerError(ValueError):
    """Raised when program-layer inputs are invalid or ambiguous."""


_BATCH_TO_PROGRAM: dict[str, str] = {
    "BATCH-A": "PRG-FOUNDATION-GOVERNANCE",
    "BATCH-B": "PRG-FOUNDATION-GOVERNANCE",
    "BATCH-C": "PRG-FOUNDATION-GOVERNANCE",
    "BATCH-D": "PRG-ROADMAP-EXECUTION",
    "BATCH-E": "PRG-ROADMAP-EXECUTION",
    "BATCH-F": "PRG-ROADMAP-EXECUTION",
    "BATCH-G": "PRG-ROADMAP-EXECUTION",
    "BATCH-H": "PRG-QUALITY-CERTIFICATION",
    "BATCH-I": "PRG-QUALITY-CERTIFICATION",
    "BATCH-J": "PRG-QUALITY-CERTIFICATION",
    "BATCH-K": "PRG-QUALITY-CERTIFICATION",
    "BATCH-L": "PRG-QUALITY-CERTIFICATION",
    "BATCH-M": "PRG-QUALITY-CERTIFICATION",
}


@dataclass(frozen=True)
class ProgramConstraintResult:
    """Deterministic result of applying program constraints to candidate roadmap steps."""

    ordered_steps: list[dict[str, str]]
    filtered_out_targets: list[str]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def get_batch_program_mapping() -> dict[str, str]:
    """Return canonical batch (A-M) ownership mapping to single owning program IDs."""

    return dict(sorted(_BATCH_TO_PROGRAM.items()))


def resolve_program_for_batch(batch_id: str) -> str:
    """Return owning program ID for a batch; fail closed on unknown or malformed IDs."""

    normalized = str(batch_id or "").strip().upper()
    if not normalized:
        raise ProgramLayerError("batch_id is required to resolve program ownership")
    if normalized not in _BATCH_TO_PROGRAM:
        raise ProgramLayerError(f"batch_id '{batch_id}' is not in canonical A-M mapping")
    return _BATCH_TO_PROGRAM[normalized]


def _normalized_targets(value: Any, *, label: str) -> set[str]:
    if not isinstance(value, list):
        raise ProgramLayerError(f"{label} must be a list")
    normalized = {str(item).strip() for item in value if str(item).strip()}
    return normalized


def _priority_score(step: dict[str, str], priority_rules: dict[str, int], original_index: int) -> tuple[int, str, int]:
    key_exact = f"{step['category']}:{step['target']}"
    key_category = f"{step['category']}:*"
    score = priority_rules.get(key_exact, priority_rules.get(key_category, 1_000_000))
    return (score, step["target"], original_index)


def apply_program_constraints(
    *,
    steps: list[dict[str, str]],
    program_artifact: dict[str, Any],
) -> ProgramConstraintResult:
    """Filter and order roadmap steps using allowed/disallowed targets and priority rules."""

    allowed = _normalized_targets(program_artifact.get("allowed_targets", []), label="program_artifact.allowed_targets")
    disallowed = _normalized_targets(
        program_artifact.get("disallowed_targets", []),
        label="program_artifact.disallowed_targets",
    )

    if allowed & disallowed:
        raise ProgramLayerError("program_artifact has overlapping allowed_targets and disallowed_targets")

    raw_rules = program_artifact.get("priority_rules")
    if not isinstance(raw_rules, list):
        raise ProgramLayerError("program_artifact.priority_rules must be a list")
    priority_rules: dict[str, int] = {}
    for entry in raw_rules:
        if not isinstance(entry, dict):
            raise ProgramLayerError("program_artifact.priority_rules entries must be objects")
        category = str(entry.get("category") or "").strip()
        target = str(entry.get("target") or "*").strip() or "*"
        priority = entry.get("priority")
        if not category:
            raise ProgramLayerError("program_artifact.priority_rules.category is required")
        if not isinstance(priority, int) or priority < 1:
            raise ProgramLayerError("program_artifact.priority_rules.priority must be integer >= 1")
        priority_rules[f"{category}:{target}"] = priority

    filtered: list[dict[str, str]] = []
    filtered_out: set[str] = set()
    for step in steps:
        target = str(step.get("target") or "").strip()
        if not target:
            continue
        if target in disallowed or (allowed and target not in allowed):
            filtered_out.add(target)
            continue
        filtered.append({"category": str(step["category"]), "target": target})

    ordered = [
        step
        for _, step in sorted(
            enumerate(filtered),
            key=lambda item: _priority_score(item[1], priority_rules, item[0]),
        )
    ]

    return ProgramConstraintResult(
        ordered_steps=ordered,
        filtered_out_targets=sorted(filtered_out),
    )


def build_program_progress(
    *,
    program_artifact: dict[str, Any],
    completed_batches: list[str],
    trace_id: str,
) -> dict[str, Any]:
    """Build deterministic program_progress artifact from declared program batches."""

    declared = [str(batch).strip().upper() for batch in program_artifact.get("batches", [])]
    if not declared:
        raise ProgramLayerError("program_artifact.batches must be a non-empty list")
    deduped_declared = sorted(set(batch for batch in declared if batch))

    completed = sorted(set(str(batch).strip().upper() for batch in completed_batches if str(batch).strip()))
    completed_valid = [batch for batch in completed if batch in deduped_declared]
    remaining = sorted(batch for batch in deduped_declared if batch not in completed_valid)

    total = len(deduped_declared)
    ratio = 100.0 if total == 0 else round((len(completed_valid) / total) * 100, 2)

    blockers = sorted(set(str(item).strip() for item in program_artifact.get("blocking_conditions", []) if str(item).strip()))
    status = str(program_artifact.get("status") or "active").strip().lower()
    if blockers:
        readiness = "blocked"
    elif ratio >= 100.0 and status in {"completed", "active"}:
        readiness = "ready_for_closeout"
    elif ratio == 0:
        readiness = "not_started"
    else:
        readiness = "in_progress"

    return {
        "program_id": str(program_artifact["program_id"]),
        "schema_version": "1.0.0",
        "completed_batches": completed_valid,
        "remaining_batches": remaining,
        "progress_percentage": ratio,
        "blocking_conditions": blockers,
        "readiness_state": readiness,
        "trace_id": str(trace_id),
    }


def build_program_constraint_signal(
    *,
    program_artifact: dict[str, Any],
    program_status: dict[str, Any] | None = None,
    trace_id: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Emit deterministic governed program_constraint_signal from program artifact + status."""

    program_status = dict(program_status or {})
    program_id = str(program_artifact.get("program_id") or "").strip()
    if not program_id:
        raise ProgramLayerError("program_artifact.program_id is required")

    version = str(program_status.get("program_version") or program_artifact.get("schema_version") or "1.0.0").strip()
    allowed_targets = sorted({str(item).strip() for item in program_artifact.get("allowed_targets", []) if str(item).strip()})
    disallowed_targets = sorted({str(item).strip() for item in program_artifact.get("disallowed_targets", []) if str(item).strip()})
    if set(allowed_targets) & set(disallowed_targets):
        raise ProgramLayerError("allowed_targets and disallowed_targets must not overlap")

    priority_ordering = sorted(
        {str(item).strip().upper() for item in program_status.get("priority_ordering", []) if str(item).strip()}
    )
    if not priority_ordering:
        priority_ordering = [str(item).strip().upper() for item in program_artifact.get("batches", []) if str(item).strip()]

    success_criteria = sorted({str(item).strip() for item in program_artifact.get("success_criteria", []) if str(item).strip()})
    blocking_conditions = sorted(
        {
            str(item).strip()
            for item in [*(program_artifact.get("blocking_conditions", []) or []), *(program_status.get("blocking_conditions", []) or [])]
            if str(item).strip()
        }
    )

    enforcement_mode = str(program_status.get("enforcement_mode") or "block").strip().lower()
    if enforcement_mode not in {"warn", "freeze", "block"}:
        raise ProgramLayerError("enforcement_mode must be one of warn, freeze, block")

    payload = {
        "program_id": program_id,
        "program_version": version,
        "allowed_targets": allowed_targets,
        "disallowed_targets": disallowed_targets,
        "priority_ordering": priority_ordering,
        "success_criteria": success_criteria,
        "blocking_conditions": blocking_conditions,
        "enforcement_mode": enforcement_mode,
        "created_at": created_at or _utc_now(),
        "trace_id": str(trace_id),
    }
    return payload


def validate_roadmap_against_program(
    *,
    roadmap_artifact: dict[str, Any],
    program_constraint_signal: dict[str, Any],
    created_at: str | None = None,
) -> dict[str, Any]:
    """Deterministic roadmap alignment validation against enforced program boundaries."""

    batches = [row for row in roadmap_artifact.get("batches", []) if isinstance(row, dict)]
    allowed = {str(item).strip().upper() for item in program_constraint_signal.get("allowed_targets", []) if str(item).strip()}
    disallowed = {str(item).strip().upper() for item in program_constraint_signal.get("disallowed_targets", []) if str(item).strip()}
    priority = [str(item).strip().upper() for item in program_constraint_signal.get("priority_ordering", []) if str(item).strip()]

    violations: list[dict[str, str]] = []
    batch_ids = [str(row.get("batch_id") or "").strip().upper() for row in batches if str(row.get("batch_id") or "").strip()]
    for bid in batch_ids:
        if bid in disallowed:
            violations.append({"reason_code": "disallowed_target", "batch_id": bid, "detail": f"batch {bid} is disallowed"})
        if allowed and bid not in allowed:
            violations.append({"reason_code": "target_not_allowed", "batch_id": bid, "detail": f"batch {bid} not in allowed_targets"})

    if priority:
        positions = {batch_id: idx for idx, batch_id in enumerate(batch_ids)}
        observed_priority = [b for b in priority if b in positions]
        if observed_priority != sorted(observed_priority, key=lambda b: positions[b]):
            violations.append(
                {
                    "reason_code": "priority_violation",
                    "batch_id": observed_priority[0] if observed_priority else "",
                    "detail": "roadmap ordering violates program priority_ordering",
                }
            )

    goal = str(roadmap_artifact.get("goal") or "").strip().lower()
    success_criteria = [str(item).strip().lower() for item in program_constraint_signal.get("success_criteria", []) if str(item).strip()]
    if goal and success_criteria and not any(goal in criterion or criterion in goal for criterion in success_criteria):
        violations.append({"reason_code": "goal_misalignment", "batch_id": "", "detail": "roadmap goal not aligned to program success criteria"})

    alignment_status = "aligned" if not violations else "invalid"
    fail_closed = alignment_status != "aligned"
    normalized = {
        "program_id": str(program_constraint_signal.get("program_id") or ""),
        "roadmap_id": str(roadmap_artifact.get("roadmap_id") or ""),
        "alignment_status": alignment_status,
        "fail_closed": fail_closed,
        "violations": sorted(violations, key=lambda item: (item["reason_code"], item["batch_id"], item["detail"])),
        "created_at": created_at or _utc_now(),
        "trace_id": str(program_constraint_signal.get("trace_id") or roadmap_artifact.get("trace_id") or "trace-missing"),
    }
    normalized["alignment_id"] = f"PRA-{_canonical_hash(normalized)[:12].upper()}"
    return normalized


def detect_program_drift(
    *,
    program_constraint_signal: dict[str, Any],
    executed_batches: list[str],
    planned_batches: list[str],
    trace_id: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Detect deterministic program drift categories required for governed continuation."""

    allowed = {str(item).strip().upper() for item in program_constraint_signal.get("allowed_targets", []) if str(item).strip()}
    priority = [str(item).strip().upper() for item in program_constraint_signal.get("priority_ordering", []) if str(item).strip()]
    executed = [str(item).strip().upper() for item in executed_batches if str(item).strip()]
    planned = [str(item).strip().upper() for item in planned_batches if str(item).strip()]

    drift_type = "none"
    affected: list[str] = []
    severity = "low"
    evidence: list[str] = []

    disallowed_executed = sorted([b for b in executed if allowed and b not in allowed])
    if disallowed_executed:
        drift_type = "target_violation"
        affected = disallowed_executed
        severity = "high"
        evidence.append("executed_batch_not_in_allowed_targets")
    elif priority:
        priority_index = {b: i for i, b in enumerate(priority)}
        ordered_exec = [b for b in executed if b in priority_index]
        if ordered_exec != sorted(ordered_exec, key=lambda b: priority_index[b]):
            drift_type = "priority_violation"
            affected = ordered_exec
            severity = "medium"
            evidence.append("execution_order_not_matching_priority_ordering")
    elif sorted(set(executed) - set(planned)):
        drift_type = "scope_expansion"
        affected = sorted(set(executed) - set(planned))
        severity = "high"
        evidence.append("executed_batches_not_declared_in_plan")
    elif len(executed) >= 3 and len(set(executed[-3:])) == 1:
        drift_type = "repetition_churn"
        affected = [executed[-1]]
        severity = "medium"
        evidence.append("same_batch_repeated_three_times")

    drift_detected = drift_type != "none"
    signal = {
        "program_id": str(program_constraint_signal.get("program_id") or ""),
        "drift_detected": drift_detected,
        "drift_type": drift_type,
        "affected_batches": sorted(set(affected)),
        "severity": severity,
        "evidence_refs": sorted(set(evidence)),
        "created_at": created_at or _utc_now(),
        "trace_id": str(trace_id),
    }
    return signal


def build_program_feedback_record(
    *,
    program_id: str,
    completed_batches: list[str],
    blocked_batches: list[str],
    recurring_failures: list[str],
    drift_signals: list[str],
    risk_signals: list[str],
    improvement_recommendations: list[str],
    trace_id: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build deterministic program feedback artifact for future roadmap generation."""

    return {
        "program_id": str(program_id),
        "completed_batches": sorted({str(item).strip().upper() for item in completed_batches if str(item).strip()}),
        "blocked_batches": sorted({str(item).strip().upper() for item in blocked_batches if str(item).strip()}),
        "recurring_failures": sorted({str(item).strip() for item in recurring_failures if str(item).strip()}),
        "drift_signals": sorted({str(item).strip() for item in drift_signals if str(item).strip()}),
        "risk_signals": sorted({str(item).strip() for item in risk_signals if str(item).strip()}),
        "improvement_recommendations": sorted(
            {str(item).strip() for item in improvement_recommendations if str(item).strip()}
        ),
        "created_at": created_at or _utc_now(),
        "trace_id": str(trace_id),
    }


__all__ = [
    "ProgramConstraintResult",
    "ProgramLayerError",
    "apply_program_constraints",
    "build_program_constraint_signal",
    "build_program_feedback_record",
    "build_program_progress",
    "detect_program_drift",
    "get_batch_program_mapping",
    "resolve_program_for_batch",
    "validate_roadmap_against_program",
]
