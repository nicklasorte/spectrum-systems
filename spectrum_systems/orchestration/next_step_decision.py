"""Deterministic fail-closed control-layer next-step decision engine."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema

_CANONICAL_STRATEGY_PATH = "docs/architecture/system_strategy.md"
_CANONICAL_SOURCE_INDEX_PATH = "docs/architecture/system_source_index.md"

_STATES = [
    "draft_roadmap",
    "roadmap_under_review",
    "roadmap_approved",
    "execution_ready",
    "execution_in_progress",
    "execution_complete_unreviewed",
    "implementation_reviews_complete",
    "fix_roadmap_ready",
    "fixes_in_progress",
    "fixes_complete_unreviewed",
    "certification_pending",
    "certified_done",
    "blocked",
]

_ACTION_BY_STATE = {
    "draft_roadmap": "submit_for_review",
    "roadmap_under_review": "await_roadmap_review",
    "roadmap_approved": "prepare_execution",
    "execution_ready": "start_execution",
    "execution_in_progress": "await_execution_completion",
    "execution_complete_unreviewed": "request_implementation_reviews",
    "implementation_reviews_complete": "generate_fix_roadmap",
    "fix_roadmap_ready": "start_fixes",
    "fixes_in_progress": "await_fix_completion",
    "fixes_complete_unreviewed": "request_fix_review",
    "certification_pending": "run_certification",
    "certified_done": "none",
    "blocked": "resolve_blocking_issues",
}

_ALLOWED_ACTIONS_BY_STATE = {
    "draft_roadmap": ["submit_for_review"],
    "roadmap_under_review": ["await_roadmap_review", "block"],
    "roadmap_approved": ["prepare_execution", "block"],
    "execution_ready": ["start_execution", "block"],
    "execution_in_progress": ["await_execution_completion", "block"],
    "execution_complete_unreviewed": ["request_implementation_reviews", "generate_fix_roadmap", "block"],
    "implementation_reviews_complete": ["generate_fix_roadmap", "block"],
    "fix_roadmap_ready": ["start_fixes", "block"],
    "fixes_in_progress": ["await_fix_completion", "block"],
    "fixes_complete_unreviewed": ["request_fix_review", "block"],
    "certification_pending": ["run_certification", "block"],
    "certified_done": ["none"],
    "blocked": ["resolve_blocking_issues"],
}

_REQUIRED_PATHS_BY_STATE = {
    "roadmap_under_review": ["roadmap_review_artifact_paths"],
    "execution_complete_unreviewed": ["execution_report_paths"],
    "implementation_reviews_complete": ["implementation_review_paths"],
    "fix_roadmap_ready": ["fix_roadmap_path"],
    "fixes_in_progress": ["fix_execution_report_paths"],
    "fixes_complete_unreviewed": ["fix_execution_report_paths"],
    "certification_pending": ["done_certification_input_refs"],
}


class NextStepDecisionError(ValueError):
    """Raised when next-step decision inputs are not valid objects."""


def _load_json(path: str | Path) -> Dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise NextStepDecisionError(f"expected object artifact: {path}")
    return payload


def _path_exists(path_value: Any) -> bool:
    return isinstance(path_value, str) and path_value != "" and Path(path_value).is_file()


def _all_paths_exist(paths: Any) -> bool:
    return isinstance(paths, list) and all(_path_exists(path) for path in paths)


def _validate_governance_authority(manifest: Dict[str, Any]) -> tuple[list[str], bool, bool]:
    missing: list[str] = []

    strategy = manifest.get("strategy_authority")
    strategy_ok = True
    if not isinstance(strategy, dict):
        missing.append("strategy_authority")
        strategy_ok = False
    else:
        if strategy.get("path") != _CANONICAL_STRATEGY_PATH:
            missing.append("strategy_authority.path")
            strategy_ok = False
        elif not _path_exists(strategy.get("path")):
            missing.append("strategy_authority.path")
            strategy_ok = False

    source_authorities = manifest.get("source_authorities")
    source_ok = True
    if not isinstance(source_authorities, list) or not source_authorities:
        missing.append("source_authorities")
        source_ok = False
    else:
        source_index_path = Path(_CANONICAL_SOURCE_INDEX_PATH)
        source_index_text = source_index_path.read_text(encoding="utf-8") if source_index_path.is_file() else ""
        if not source_index_path.is_file():
            missing.append("docs/architecture/system_source_index.md")
            source_ok = False

        seen: set[tuple[str, str]] = set()
        for idx, item in enumerate(source_authorities):
            if not isinstance(item, dict):
                missing.append(f"source_authorities[{idx}]")
                source_ok = False
                continue
            source_id = item.get("source_id")
            source_path = item.get("path")
            if not isinstance(source_id, str) or not source_id:
                missing.append(f"source_authorities[{idx}].source_id")
                source_ok = False
            if not isinstance(source_path, str) or not source_path:
                missing.append(f"source_authorities[{idx}].path")
                source_ok = False
                continue
            if not _path_exists(source_path):
                missing.append(f"source_authorities[{idx}].path")
                source_ok = False
            elif source_index_text and (source_id not in source_index_text or source_path not in source_index_text):
                missing.append(f"source_authorities[{idx}].declared_in_source_index")
                source_ok = False
            key = (str(source_id), source_path)
            if key in seen:
                missing.append(f"source_authorities[{idx}].duplicate")
                source_ok = False
            seen.add(key)

    return sorted(set(missing)), strategy_ok, source_ok


def _detect_drift(manifest: Dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    for key in ("drift_detection_result_path", "drift_result_path"):
        path = manifest.get(key)
        if _path_exists(path):
            payload = _load_json(path)
            status = payload.get("drift_status")
            detected = payload.get("drift_detected")
            if detected is True or status in {"exceeds_threshold", "drift_detected", "blocking"}:
                reasons.append(f"{key}:{status or 'drift_detected'}")

    list_key = manifest.get("drift_detection_artifact_paths")
    if isinstance(list_key, list):
        for path in list_key:
            if not _path_exists(path):
                continue
            payload = _load_json(path)
            status = payload.get("drift_status")
            if payload.get("drift_detected") is True or status in {"exceeds_threshold", "drift_detected", "blocking"}:
                reasons.append(f"drift_detection_artifact_paths:{status or 'drift_detected'}")

    return bool(reasons), sorted(set(reasons))


def _required_input_missing_for_state(manifest: Dict[str, Any], state: str) -> list[str]:
    missing: list[str] = []
    for key in _REQUIRED_PATHS_BY_STATE.get(state, []):
        value = manifest.get(key)
        if key.endswith("_paths"):
            if not _all_paths_exist(value):
                missing.append(key)
        elif key.endswith("_path"):
            if not _path_exists(value):
                missing.append(key)
        elif key == "done_certification_input_refs":
            if not isinstance(value, dict) or not value:
                missing.append(key)
            else:
                required_refs = {
                    "replay_result_ref",
                    "regression_result_ref",
                    "certification_pack_ref",
                    "error_budget_ref",
                    "policy_ref",
                }
                for ref in sorted(required_refs):
                    if not isinstance(value.get(ref), str) or not value.get(ref):
                        missing.append(f"done_certification_input_refs.{ref}")
        else:
            if value in (None, "", []):
                missing.append(key)
    return missing


def _decision_id(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_next_step_decision(cycle_manifest_path: str) -> Dict[str, Any]:
    manifest = _load_json(cycle_manifest_path)

    cycle_id = str(manifest.get("cycle_id", "cycle-invalid"))
    state = str(manifest.get("current_state", "invalid"))
    decided_at = manifest.get("updated_at") if isinstance(manifest.get("updated_at"), str) else "1970-01-01T00:00:00Z"

    missing_inputs, strategy_ok, source_ok = _validate_governance_authority(manifest)
    blocking_reasons: list[str] = []
    drift_detected, drift_reasons = _detect_drift(manifest)

    if state not in _STATES:
        missing_inputs.append("current_state")
        next_action = "block"
        allowed_actions = ["block"]
        blocking_reasons.append("invalid lifecycle state")
    else:
        next_action = _ACTION_BY_STATE[state]
        allowed_actions = _ALLOWED_ACTIONS_BY_STATE[state]
        missing_inputs.extend(_required_input_missing_for_state(manifest, state))

    if missing_inputs:
        next_action = "block"
        blocking_reasons.append("missing required governance signals")

    if drift_detected:
        next_action = "generate_fix_roadmap"
        blocking_reasons.append("drift detected requires remediation")

    if state == "blocked":
        next_action = "resolve_blocking_issues"

    blocking = bool(missing_inputs or blocking_reasons or state == "blocked")
    if state == "certified_done" and not (missing_inputs or drift_detected):
        blocking = False

    trust_score = 100
    trust_score -= min(len(set(missing_inputs)) * 20, 80)
    if not strategy_ok:
        trust_score -= 20
    if not source_ok:
        trust_score -= 20
    if drift_detected:
        trust_score -= 25
    trust_score = max(0, min(100, trust_score))

    strategy_compliant = strategy_ok and state in _STATES and not drift_detected
    source_grounded = source_ok

    core_id_fields = {
        "cycle_id": cycle_id,
        "current_state": state,
        "next_action": next_action,
        "allowed_actions": allowed_actions,
        "blocking": blocking,
        "required_inputs_missing": sorted(set(missing_inputs)),
        "drift_detected": drift_detected,
        "drift_reasons": drift_reasons,
        "strategy_compliant": strategy_compliant,
        "source_grounded": source_grounded,
        "trust_score": trust_score,
        "decided_at": decided_at,
    }

    decision = {
        "decision_id": _decision_id(core_id_fields),
        "cycle_id": cycle_id,
        "current_state": state,
        "next_action": next_action,
        "allowed_actions": allowed_actions,
        "blocking": blocking,
        "blocking_reasons": sorted(set(blocking_reasons)),
        "required_inputs_missing": sorted(set(missing_inputs)),
        "drift_detected": drift_detected,
        "drift_reasons": drift_reasons,
        "strategy_compliant": strategy_compliant,
        "source_grounded": source_grounded,
        "trust_score": trust_score,
        "decision_rationale": (
            f"state={state};action={next_action};blocking={'true' if blocking else 'false'};"
            f"reasons={len(set(blocking_reasons))};drift={'true' if drift_detected else 'false'};trust={trust_score}"
        ),
        "decided_at": decided_at,
    }

    schema = load_schema("next_step_decision_artifact")
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(decision)
    return decision
