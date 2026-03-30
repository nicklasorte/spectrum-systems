"""Deterministic fail-closed cycle runner for autonomous execution loop foundation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from jsonschema import Draft202012Validator

from spectrum_systems.contracts import load_schema


class CycleRunnerError(ValueError):
    """Raised when cycle orchestration cannot proceed deterministically."""


_STATES = {
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
}


def _load_json(path: str | Path) -> Dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CycleRunnerError(f"expected object artifact: {path}")
    return payload


def _validate_manifest(manifest: Dict[str, Any]) -> None:
    schema = load_schema("cycle_manifest")
    Draft202012Validator(schema).validate(manifest)


def _path_exists(path_value: Any) -> bool:
    return isinstance(path_value, str) and path_value != "" and Path(path_value).is_file()


def _all_paths_exist(paths: Any) -> bool:
    return isinstance(paths, list) and all(_path_exists(path) for path in paths)


def _reviews_complete(paths: list[str]) -> bool:
    reviewers = set()
    for path in paths:
        payload = _load_json(path)
        reviewer = payload.get("reviewer")
        if isinstance(reviewer, str):
            reviewers.add(reviewer)
    return {"claude", "codex"}.issubset(reviewers)


def _roadmap_approved_from_reviews(paths: list[str]) -> bool:
    if not paths:
        return False
    for path in paths:
        payload = _load_json(path)
        if payload.get("approval_state") == "approved":
            return True
    return False


def _certification_handoff(manifest: Dict[str, Any]) -> Dict[str, Any]:
    refs = manifest.get("done_certification_input_refs")
    if not isinstance(refs, dict) or not refs:
        raise CycleRunnerError("certification handoff requires done_certification_input_refs")
    required = {
        "replay_result_ref",
        "regression_result_ref",
        "certification_pack_ref",
        "error_budget_ref",
        "policy_ref",
    }
    missing = sorted(k for k in required if not isinstance(refs.get(k), str) or not refs[k])
    if missing:
        raise CycleRunnerError(f"certification handoff missing refs: {', '.join(missing)}")
    return {
        "handoff_module": "spectrum_systems.modules.governance.done_certification.run_done_certification",
        "input_refs": refs,
    }


def run_cycle(manifest_path: str | Path) -> Dict[str, Any]:
    """Load cycle manifest and return deterministic next-action decision."""
    manifest = _load_json(manifest_path)
    _validate_manifest(manifest)

    state = manifest["current_state"]
    if state not in _STATES:
        raise CycleRunnerError(f"unsupported cycle state: {state}")

    def blocked(reason: str) -> Dict[str, Any]:
        issues = [*manifest.get("blocking_issues", []), reason]
        return {
            "cycle_id": manifest["cycle_id"],
            "status": "blocked",
            "current_state": state,
            "next_state": "blocked",
            "next_action": "resolve_blocking_issues",
            "blocking_issues": issues,
        }

    roadmap_path = manifest.get("roadmap_artifact_path")
    if state != "certified_done" and not _path_exists(roadmap_path):
        return blocked("missing required artifact: roadmap_artifact_path")

    if state == "draft_roadmap":
        return {
            "cycle_id": manifest["cycle_id"],
            "status": "ok",
            "current_state": state,
            "next_state": "roadmap_under_review",
            "next_action": "request_roadmap_review",
            "blocking_issues": manifest.get("blocking_issues", []),
        }

    if state == "roadmap_under_review":
        review_paths = manifest.get("roadmap_review_artifact_paths", [])
        if not _all_paths_exist(review_paths):
            return blocked("missing required artifact: roadmap_review_artifact_paths")
        approval_state = manifest.get("roadmap_approval_state", "pending")
        review_approved = _roadmap_approved_from_reviews(review_paths)
        if approval_state != "approved" and not review_approved:
            return blocked("roadmap approval required before execution")
        return {
            "cycle_id": manifest["cycle_id"],
            "status": "ok",
            "current_state": state,
            "next_state": "roadmap_approved",
            "next_action": "lock_approved_roadmap",
            "blocking_issues": manifest.get("blocking_issues", []),
        }

    if state == "roadmap_approved":
        hard_gates = manifest.get("hard_gates", {})
        if not all(bool(hard_gates.get(k)) for k in ("roadmap_approved", "execution_contracts_pinned", "review_templates_present")):
            return blocked("hard gates not satisfied for execution readiness")
        return {
            "cycle_id": manifest["cycle_id"],
            "status": "ok",
            "current_state": state,
            "next_state": "execution_ready",
            "next_action": "prepare_execution_request",
            "blocking_issues": manifest.get("blocking_issues", []),
        }

    if state == "execution_ready":
        if not _path_exists(manifest.get("pqx_execution_request_path")):
            return blocked("missing required artifact: pqx_execution_request_path")
        return {
            "cycle_id": manifest["cycle_id"],
            "status": "ok",
            "current_state": state,
            "next_state": "execution_in_progress",
            "next_action": "invoke_pqx_execution_stub",
            "integration_handoff": {
                "handoff_module": "spectrum_systems.modules.runtime.pqx_slice_runner",
                "mode": "stub_only"
            },
            "blocking_issues": manifest.get("blocking_issues", []),
        }

    if state == "execution_in_progress":
        reports = manifest.get("execution_report_paths", [])
        if not _all_paths_exist(reports):
            return blocked("missing required artifact: execution_report_paths")
        return {
            "cycle_id": manifest["cycle_id"],
            "status": "ok",
            "current_state": state,
            "next_state": "execution_complete_unreviewed",
            "next_action": "request_implementation_reviews",
            "blocking_issues": manifest.get("blocking_issues", []),
        }

    if state == "execution_complete_unreviewed":
        review_paths = manifest.get("implementation_review_paths", [])
        if not _all_paths_exist(review_paths):
            return blocked("missing required artifact: implementation_review_paths")
        if not _reviews_complete(review_paths):
            return blocked("dual implementation reviews required: claude + codex")
        return {
            "cycle_id": manifest["cycle_id"],
            "status": "ok",
            "current_state": state,
            "next_state": "implementation_reviews_complete",
            "next_action": "ingest_implementation_reviews",
            "blocking_issues": manifest.get("blocking_issues", []),
        }

    if state == "implementation_reviews_complete":
        if not _path_exists(manifest.get("fix_roadmap_path")):
            return blocked("missing required artifact: fix_roadmap_path")
        return {
            "cycle_id": manifest["cycle_id"],
            "status": "ok",
            "current_state": state,
            "next_state": "fix_roadmap_ready",
            "next_action": "dispatch_fix_bundles",
            "blocking_issues": manifest.get("blocking_issues", []),
        }

    if state == "fix_roadmap_ready":
        return {
            "cycle_id": manifest["cycle_id"],
            "status": "ok",
            "current_state": state,
            "next_state": "fixes_in_progress",
            "next_action": "execute_fix_bundles_via_pqx",
            "blocking_issues": manifest.get("blocking_issues", []),
        }

    if state == "fixes_in_progress":
        reports = manifest.get("execution_report_paths", [])
        if not _all_paths_exist(reports):
            return blocked("missing required artifact: execution_report_paths_for_fixes")
        return {
            "cycle_id": manifest["cycle_id"],
            "status": "ok",
            "current_state": state,
            "next_state": "fixes_complete_unreviewed",
            "next_action": "request_post_fix_review",
            "blocking_issues": manifest.get("blocking_issues", []),
        }

    if state in {"fixes_complete_unreviewed", "certification_pending"}:
        if _path_exists(manifest.get("certification_record_path")):
            return {
                "cycle_id": manifest["cycle_id"],
                "status": "ok",
                "current_state": state,
                "next_state": "certified_done",
                "next_action": "archive_cycle",
                "blocking_issues": manifest.get("blocking_issues", []),
            }
        return {
            "cycle_id": manifest["cycle_id"],
            "status": "ok",
            "current_state": state,
            "next_state": "certification_pending",
            "next_action": "invoke_done_certification",
            "integration_handoff": _certification_handoff(manifest),
            "blocking_issues": manifest.get("blocking_issues", []),
        }

    if state == "certified_done":
        return {
            "cycle_id": manifest["cycle_id"],
            "status": "ok",
            "current_state": state,
            "next_state": "certified_done",
            "next_action": "none",
            "blocking_issues": [],
        }

    if state == "blocked":
        return {
            "cycle_id": manifest["cycle_id"],
            "status": "blocked",
            "current_state": state,
            "next_state": "blocked",
            "next_action": "resolve_blocking_issues",
            "blocking_issues": manifest.get("blocking_issues", ["cycle is explicitly blocked"]),
        }

    raise CycleRunnerError(f"unhandled cycle state: {state}")
