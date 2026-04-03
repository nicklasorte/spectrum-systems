"""Program direction layer for deterministic roadmap constraints and progress tracking."""

from __future__ import annotations

from dataclasses import dataclass
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


__all__ = [
    "ProgramConstraintResult",
    "ProgramLayerError",
    "apply_program_constraints",
    "build_program_progress",
    "get_batch_program_mapping",
    "resolve_program_for_batch",
]
