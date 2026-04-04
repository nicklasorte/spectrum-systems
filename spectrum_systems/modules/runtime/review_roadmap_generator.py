"""Deterministic roadmap derivation from governed repo review snapshots."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Dict, List

from spectrum_systems.modules.runtime.program_layer import (
    ProgramLayerError,
    apply_program_constraints,
)
from spectrum_systems.modules.runtime.tpa_complexity_governance import calculate_tpa_priority_score

from spectrum_systems.modules.runtime.repo_review_snapshot_store import (
    RepoReviewSnapshotStoreError,
    validate_repo_review_snapshot,
)


class ReviewRoadmapGeneratorError(ValueError):
    """Raised when review-driven roadmap derivation cannot proceed fail-closed."""


_UNSAFE_RESPONSES = {"freeze", "block"}


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _require_non_empty_string(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReviewRoadmapGeneratorError(f"{label} must be a non-empty string")
    return value.strip()


def _require_string_list(value: Any, *, label: str) -> List[str]:
    if not isinstance(value, list) or not value:
        raise ReviewRoadmapGeneratorError(f"{label} must be a non-empty list")
    normalized = []
    for entry in value:
        normalized.append(_require_non_empty_string(entry, label=label))
    return sorted(set(normalized))


def _normalize_handoff(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    try:
        validate_repo_review_snapshot(snapshot)
    except RepoReviewSnapshotStoreError as exc:
        raise ReviewRoadmapGeneratorError(str(exc)) from exc

    handoff = snapshot.get("roadmap_handoff")
    if not isinstance(handoff, dict):
        raise ReviewRoadmapGeneratorError("repo_review_snapshot.roadmap_handoff is required")

    constraints = handoff.get("sequencing_constraints")
    if not isinstance(constraints, list):
        raise ReviewRoadmapGeneratorError("roadmap_handoff.sequencing_constraints must be a list")

    normalized_constraints: List[Dict[str, str]] = []
    for item in constraints:
        if not isinstance(item, dict):
            raise ReviewRoadmapGeneratorError("sequencing_constraints entries must be objects")
        normalized_constraints.append(
            {
                "before": _require_non_empty_string(item.get("before"), label="sequencing_constraints.before"),
                "after": _require_non_empty_string(item.get("after"), label="sequencing_constraints.after"),
                "reason": _require_non_empty_string(item.get("reason"), label="sequencing_constraints.reason"),
            }
        )

    return {
        "build_candidates": _require_string_list(handoff.get("build_candidates"), label="roadmap_handoff.build_candidates"),
        "hardening_targets": _require_string_list(handoff.get("hardening_targets"), label="roadmap_handoff.hardening_targets"),
        "merge_consolidation_targets": _require_string_list(
            handoff.get("merge_consolidation_targets"),
            label="roadmap_handoff.merge_consolidation_targets",
        ),
        "defer_targets": _require_string_list(handoff.get("defer_targets"), label="roadmap_handoff.defer_targets"),
        "sequencing_constraints": sorted(
            normalized_constraints,
            key=lambda item: (item["before"], item["after"], item["reason"]),
        ),
        "next_hard_gate": _require_non_empty_string(handoff.get("next_hard_gate"), label="roadmap_handoff.next_hard_gate"),
    }


def build_review_roadmap(
    *,
    snapshot: Dict[str, Any],
    control_decision: Dict[str, Any],
    program_artifact: Dict[str, Any] | None = None,
    complexity_budget_artifacts: List[Dict[str, Any]] | None = None,
    complexity_trend_artifacts: List[Dict[str, Any]] | None = None,
    tpa_simplification_campaign_artifacts: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    handoff = _normalize_handoff(snapshot)

    system_response = _require_non_empty_string(control_decision.get("system_response"), label="control_decision.system_response")
    if system_response not in {"allow", "warn", "freeze", "block"}:
        raise ReviewRoadmapGeneratorError("control_decision.system_response must be allow|warn|freeze|block")

    readiness = "ready"
    generation_status = "generated"
    if system_response == "warn":
        readiness = "degraded"
    elif system_response in _UNSAFE_RESPONSES:
        readiness = "unsafe"
        generation_status = "blocked"

    steps: List[Dict[str, str]] = []
    if generation_status == "generated":
        for target in handoff["hardening_targets"]:
            steps.append({"category": "hardening", "target": target})
        for target in handoff["merge_consolidation_targets"]:
            steps.append({"category": "consolidation", "target": target})
        if system_response == "allow":
            for target in handoff["build_candidates"]:
                steps.append({"category": "build", "target": target})
        for target in handoff["defer_targets"]:
            steps.append({"category": "defer", "target": target})

    filtered_out_targets: List[str] = []
    if generation_status == "generated" and program_artifact is not None:
        try:
            constraint_result = apply_program_constraints(steps=steps, program_artifact=program_artifact)
        except ProgramLayerError as exc:
            raise ReviewRoadmapGeneratorError(f"program constraint failure: {exc}") from exc
        steps = constraint_result.ordered_steps
        filtered_out_targets = constraint_result.filtered_out_targets

    budget_by_target = {
        str(item.get("module_or_path")): item
        for item in (complexity_budget_artifacts or [])
        if isinstance(item, dict) and str(item.get("module_or_path", "")).strip()
    }
    trend_by_target = {
        str(item.get("module")): item
        for item in (complexity_trend_artifacts or [])
        if isinstance(item, dict) and str(item.get("module", "")).strip()
    }
    campaign_by_target = {
        str(item.get("target_module")): item
        for item in (tpa_simplification_campaign_artifacts or [])
        if isinstance(item, dict) and str(item.get("target_module", "")).strip()
    }

    category_rank = {"hardening": 0, "consolidation": 1, "build": 2, "defer": 3}
    enriched_steps: List[Dict[str, Any]] = []
    for step in steps:
        target = step["target"]
        tpa_priority_score = calculate_tpa_priority_score(
            budget=budget_by_target.get(target),
            trend=trend_by_target.get(target),
            campaign=campaign_by_target.get(target),
        )
        enriched = dict(step)
        enriched["tpa_priority_score"] = tpa_priority_score
        enriched_steps.append(enriched)

    steps = sorted(
        enriched_steps,
        key=lambda item: (
            category_rank.get(item["category"], 99),
            -int(item.get("tpa_priority_score", 0)),
            item["target"],
        ),
    )

    seed = {
        "snapshot_id": snapshot["snapshot_id"],
        "control_decision_id": control_decision.get("decision_id"),
        "system_response": system_response,
        "handoff": handoff,
        "steps": steps,
        "generation_status": generation_status,
        "program_id": None if program_artifact is None else str(program_artifact.get("program_id") or ""),
        "filtered_out_targets": filtered_out_targets,
        "tpa_priority_signals": [
            {
                "target": step["target"],
                "tpa_priority_score": int(step.get("tpa_priority_score", 0)),
            }
            for step in steps
        ],
    }
    digest = _canonical_hash(seed)
    return {
        "artifact_type": "review_roadmap_plan",
        "artifact_id": f"rrp-{digest[:16]}",
        "schema_version": "1.0.0",
        "source_snapshot_id": snapshot["snapshot_id"],
        "source_review_id": snapshot["review_id"],
        "readiness": readiness,
        "generation_status": generation_status,
        "system_response": system_response,
        "next_hard_gate": handoff["next_hard_gate"],
        "build_candidates": handoff["build_candidates"],
        "hardening_targets": handoff["hardening_targets"],
        "merge_consolidation_targets": handoff["merge_consolidation_targets"],
        "defer_targets": handoff["defer_targets"],
        "sequencing_constraints": handoff["sequencing_constraints"],
        "ordered_steps": steps,
        "program_id": None if program_artifact is None else str(program_artifact.get("program_id") or ""),
        "filtered_out_targets": filtered_out_targets,
        "policy_assertions": {
            "hardening_before_expansion": generation_status == "blocked" or all(
                step["category"] != "build" or any(prev["category"] == "hardening" for prev in steps[:idx])
                for idx, step in enumerate(steps)
            ),
            "consolidation_before_invention": generation_status == "blocked" or all(
                step["category"] != "build" or any(prev["category"] == "consolidation" for prev in steps[:idx])
                for idx, step in enumerate(steps)
            ),
        },
        "source_handoff": copy.deepcopy(handoff),
    }


__all__ = ["ReviewRoadmapGeneratorError", "build_review_roadmap"]
