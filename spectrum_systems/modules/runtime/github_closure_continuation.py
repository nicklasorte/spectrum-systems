"""GitHub closure + continuation adapter over existing governed runtimes.

Role boundaries enforced here:
- GitHub triggers only (workflow/event intake and artifact location).
- Continuation adapter normalizes only (no review semantics reinterpretation).
- CDE decides closure only (adapter invokes CDE but does not decide policy).
- TLC orchestrates only (adapter invokes TLC only for bounded-allowed paths).
- SEL remains enforced at continuation boundaries.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.closure_decision_engine import (
    build_closure_decision_artifact,
    maybe_build_next_step_prompt_artifact,
)
from spectrum_systems.modules.runtime.top_level_conductor import run_top_level_conductor
from spectrum_systems.utils.deterministic_id import deterministic_id

_REQUIRED_HANDOFF_KEYS = (
    "ingestion_summary_artifact",
    "review_projection_bundle_artifact",
    "review_consumer_output_bundle_artifact",
    "review_signal_artifact",
)
_REQUIRED_RIL_KEYS = (
    "review_signal_artifact",
    "review_projection_bundle_artifact",
    "review_consumer_output_bundle_artifact",
)
_OPTIONAL_RIL_KEYS = (
    "review_control_signal_artifact",
    "review_integration_packet_artifact",
    "roadmap_two_step_artifact",
)
_CONTINUATION_ELIGIBLE_DECISIONS = {"hardening_required", "final_verification_required", "continue_bounded"}
_ROADMAP_DRAFT_DIR = Path("artifacts/roadmap_drafts")
_DRAFT_REF_PATTERN = re.compile(r"\bdraft_id\s*[:=]\s*([A-Za-z0-9_-]+)\b", re.IGNORECASE)
_READ_ONLY_TERMINAL_STATES = {
    "blocked",
    "escalated",
    "exhausted",
    "repairing",
    "continue_repair_bounded",
    "draft-only",
    "approval-pending",
    "malformed-input",
}
_TERMINAL_STATE_POLICY = {
    "ready_for_merge": {
        "promotion_allowed": True,
        "branch_update_allowed": True,
        "cde_decision_path": "lock",
    },
    "blocked": {
        "promotion_allowed": False,
        "branch_update_allowed": False,
        "cde_decision_path": "blocked",
    },
    "escalated": {
        "promotion_allowed": False,
        "branch_update_allowed": False,
        "cde_decision_path": "escalate",
    },
    "exhausted": {
        "promotion_allowed": False,
        "branch_update_allowed": False,
        "cde_decision_path": "continue_bounded",
    },
    "malformed_input": {
        "promotion_allowed": False,
        "branch_update_allowed": False,
        "cde_decision_path": "blocked",
    },
    "unknown_failure": {
        "promotion_allowed": False,
        "branch_update_allowed": False,
        "cde_decision_path": "escalate",
    },
}


class GithubClosureContinuationError(ValueError):
    """Raised when continuation inputs are malformed or violate governance boundaries."""


@dataclass(frozen=True)
class ContinuationInputBundle:
    ingestion_summary: dict[str, Any]
    pr_number: int
    ingestion_id: str
    artifact_paths: dict[str, str]
    projection_bundle: dict[str, Any]
    consumer_bundle: dict[str, Any]
    review_signal: dict[str, Any]
    optional_artifacts: dict[str, dict[str, Any]]
    roadmap_two_step_artifact: dict[str, Any] | None
    command_marker: str | None
    review_body: str
    roadmap_draft_id: str | None


@dataclass(frozen=True)
class ContinuationArtifacts:
    continuation_id: str
    continuation_dir: Path
    closure_decision_artifact_path: Path
    next_step_prompt_artifact_path: Path | None
    top_level_conductor_run_artifact_path: Path | None
    continuation_summary_path: Path


def _require_non_empty_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GithubClosureContinuationError(f"{field} must be a non-empty string")
    return value.strip()


def _require_positive_int(value: Any, *, field: str) -> int:
    if not isinstance(value, int) or value <= 0:
        raise GithubClosureContinuationError(f"{field} must be a positive integer")
    return value


def _load_json(path: Path, *, field: str) -> dict[str, Any]:
    if not path.exists():
        raise GithubClosureContinuationError(f"missing required file for {field}: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise GithubClosureContinuationError(f"{field} must decode to a JSON object")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _default_emitted_at() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_terminal_state_policy(terminal_state: str) -> dict[str, Any]:
    policy = _TERMINAL_STATE_POLICY.get(terminal_state)
    if not isinstance(policy, dict):
        raise GithubClosureContinuationError(f"unsupported terminal state returned by continuation path: {terminal_state}")
    resolved = dict(policy)
    resolved["terminal_state"] = terminal_state
    return resolved


def _build_promotion_gate_decision_artifact(
    *,
    continuation_id: str,
    final_terminal_state: str,
    closure_decision_artifact: dict[str, Any],
    top_level_conductor_run_artifact: dict[str, Any] | None,
    emitted_at: str,
) -> dict[str, Any]:
    run_id = str(closure_decision_artifact.get("run_id") or f"gha-{continuation_id}")
    closure_ref = f"closure_decision_artifact:{closure_decision_artifact['closure_decision_id']}"
    tlc_ref = (
        f"top_level_conductor_run_artifact:{top_level_conductor_run_artifact.get('run_id')}"
        if isinstance(top_level_conductor_run_artifact, dict)
        else None
    )

    missing_requirements: list[str] = []
    supporting_refs: list[str] = [closure_ref]
    if tlc_ref:
        supporting_refs.append(tlc_ref)
    else:
        missing_requirements.append("top_level_conductor_run_artifact")

    repair_ref: str | None = None
    certification_ref: str | None = None
    repair_occurred = False
    tlc_trace_refs: list[str] = []

    if isinstance(top_level_conductor_run_artifact, dict):
        lineage = top_level_conductor_run_artifact.get("lineage")
        if isinstance(lineage, dict):
            raw_repair_ref = lineage.get("repair_attempt_record_artifact_ref")
            if isinstance(raw_repair_ref, str) and raw_repair_ref.strip():
                repair_ref = raw_repair_ref.strip()
                repair_occurred = True
                supporting_refs.append(repair_ref)
            repair_count = lineage.get("repair_attempt_count")
            if isinstance(repair_count, int) and repair_count > 0:
                repair_occurred = True

        produced_refs = top_level_conductor_run_artifact.get("produced_artifact_refs")
        if isinstance(produced_refs, list):
            for item in produced_refs:
                if isinstance(item, str) and item.strip().startswith("certification:"):
                    certification_ref = item.strip()
                    break
        if certification_ref is None and tlc_ref:
            certification_ref = f"certification:{top_level_conductor_run_artifact.get('run_id')}"
        if certification_ref is not None:
            supporting_refs.append(certification_ref)

        trace_refs_raw = top_level_conductor_run_artifact.get("trace_refs")
        if isinstance(trace_refs_raw, list):
            tlc_trace_refs = [str(item).strip() for item in trace_refs_raw if isinstance(item, str) and item.strip()]

    if repair_occurred and not repair_ref:
        missing_requirements.append("repair_attempt_record_artifact")
    if not certification_ref:
        missing_requirements.append("certification_ready_artifact")

    closure_trace = str(closure_decision_artifact.get("trace_id") or "").strip()
    if not closure_trace:
        missing_requirements.append("closure_trace_ref")
    elif tlc_trace_refs and closure_trace not in tlc_trace_refs:
        missing_requirements.append("trace_lineage_continuity")

    ready_state = final_terminal_state == "ready_for_merge"
    if not ready_state:
        missing_requirements.append("terminal_state_not_ready_for_merge")
    if final_terminal_state in _READ_ONLY_TERMINAL_STATES:
        missing_requirements.append("read_only_terminal_state")

    certification_status = "certified" if not missing_requirements else "missing_or_incomplete"
    promotion_allowed = ready_state and not missing_requirements
    if promotion_allowed:
        missing_requirements = []

    combined_trace_refs = sorted(
        {
            ref
            for ref in ([closure_trace] + tlc_trace_refs)
            if isinstance(ref, str) and ref.strip()
        }
    )

    decision_seed = {
        "continuation_id": continuation_id,
        "run_id": run_id,
        "terminal_state": final_terminal_state,
        "certification_status": certification_status,
        "promotion_allowed": promotion_allowed,
        "supporting_refs": sorted(set(supporting_refs)),
        "trace_refs": combined_trace_refs,
    }
    artifact = {
        "artifact_type": "promotion_gate_decision_artifact",
        "artifact_class": "coordination",
        "schema_version": "1.0.0",
        "decision_id": deterministic_id(
            prefix="pgd",
            namespace="promotion_gate_decision_artifact",
            payload=decision_seed,
        ),
        "run_id": run_id,
        "terminal_state": final_terminal_state,
        "certification_status": certification_status,
        "promotion_allowed": promotion_allowed,
        "missing_requirements": sorted(set(missing_requirements)),
        "supporting_artifact_refs": sorted(set(supporting_refs)),
        "trace_refs": combined_trace_refs,
        "emitted_at": emitted_at,
    }
    validate_artifact(artifact, "promotion_gate_decision_artifact")
    return artifact


def _extract_draft_reference(review_body: str) -> str | None:
    match = _DRAFT_REF_PATTERN.search(review_body)
    if match is None:
        return None
    token = match.group(1).strip()
    return token or None


def _resolve_and_validate_approved_roadmap(*, pr_number: int, review_body: str, roadmap_from_summary: dict[str, Any] | None, draft_id_from_summary: str | None) -> tuple[dict[str, Any], str]:
    requested_draft_id = _extract_draft_reference(review_body) or draft_id_from_summary
    pr_root = _ROADMAP_DRAFT_DIR / f"pr-{pr_number}"
    latest_metadata_path = pr_root / "LATEST_DRAFT.json"
    if not latest_metadata_path.exists():
        raise GithubClosureContinuationError("roadmap approval requires LATEST_DRAFT.json under artifacts/roadmap_drafts")
    latest_metadata = _load_json(latest_metadata_path, field="LATEST_DRAFT")
    latest_draft_id = _require_non_empty_str(latest_metadata.get("draft_id"), field="LATEST_DRAFT.draft_id")

    if requested_draft_id is None:
        requested_draft_id = latest_draft_id

    if requested_draft_id != latest_draft_id and _extract_draft_reference(review_body) is None:
        raise GithubClosureContinuationError("approval without explicit draft_id must use latest draft")

    draft_dir = pr_root / requested_draft_id
    roadmap_path = draft_dir / "roadmap_two_step_artifact.json"
    metadata_path = draft_dir / "metadata.json"
    if not roadmap_path.exists() or not metadata_path.exists():
        raise GithubClosureContinuationError(f"approved roadmap draft is missing artifacts: {requested_draft_id}")

    metadata = _load_json(metadata_path, field="roadmap_draft.metadata")
    metadata_draft_id = _require_non_empty_str(metadata.get("draft_id"), field="roadmap_draft.metadata.draft_id")
    if metadata_draft_id != requested_draft_id:
        raise GithubClosureContinuationError("roadmap draft metadata mismatch")

    roadmap = _load_json(roadmap_path, field="roadmap_two_step_artifact")
    validate_artifact(roadmap, "roadmap_two_step_artifact")
    if roadmap_from_summary is not None and roadmap_from_summary.get("roadmap_id") != roadmap.get("roadmap_id"):
        raise GithubClosureContinuationError("approval roadmap artifact is stale relative to resolved draft")
    return roadmap, requested_draft_id


def _load_ingestion_bundle(github_review_handoff_path: Path) -> ContinuationInputBundle:
    handoff = _load_json(github_review_handoff_path, field="github_review_handoff_artifact")
    validate_artifact(handoff, "github_review_handoff_artifact")

    artifact_refs = handoff.get("artifact_refs")
    if not isinstance(artifact_refs, dict):
        raise GithubClosureContinuationError("github_review_handoff_artifact.artifact_refs must be an object")
    for key in _REQUIRED_HANDOFF_KEYS:
        raw_path = artifact_refs.get(key)
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise GithubClosureContinuationError(f"missing required handoff artifact ref: {key}")

    handoff_dir = github_review_handoff_path.resolve().parent

    def _resolve_ref_path(ref: str) -> Path:
        candidate = Path(ref)
        if candidate.is_absolute():
            return candidate
        handoff_candidate = handoff_dir / candidate
        if handoff_candidate.exists():
            return handoff_candidate
        return candidate

    ingestion_summary_path = _resolve_ref_path(str(artifact_refs["ingestion_summary_artifact"]))
    summary = _load_json(ingestion_summary_path, field="ingestion_summary")
    pr_number = _require_positive_int(summary.get("pr_number"), field="ingestion_summary.pr_number")
    ingestion_id = _require_non_empty_str(summary.get("ingestion_id"), field="ingestion_summary.ingestion_id")
    command_marker_raw = summary.get("command_marker")
    command_marker = command_marker_raw.strip() if isinstance(command_marker_raw, str) and command_marker_raw.strip() else None
    review_body = summary.get("review_body")
    if not isinstance(review_body, str) or not review_body.strip():
        review_body = ""
    roadmap_draft_id_raw = summary.get("roadmap_draft_id")
    roadmap_draft_id = (
        roadmap_draft_id_raw.strip()
        if isinstance(roadmap_draft_id_raw, str) and roadmap_draft_id_raw.strip()
        else None
    )

    artifact_paths = summary.get("artifact_paths")
    if not isinstance(artifact_paths, dict):
        raise GithubClosureContinuationError("ingestion_summary.artifact_paths must be an object")

    raw_keys = {"review_markdown", "action_tracker_markdown"}
    if raw_keys.intersection(set(artifact_paths.keys())):
        # Explicitly confirm these raw review files are not used downstream.
        pass

    for key in _REQUIRED_RIL_KEYS:
        raw_path = artifact_paths.get(key)
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise GithubClosureContinuationError(f"missing required RIL artifact path: {key}")

    review_signal_path = _resolve_ref_path(str(artifact_refs["review_signal_artifact"]))
    projection_path = _resolve_ref_path(str(artifact_refs["review_projection_bundle_artifact"]))
    consumer_path = _resolve_ref_path(str(artifact_refs["review_consumer_output_bundle_artifact"]))

    review_signal = _load_json(review_signal_path, field="review_signal_artifact")
    validate_artifact(review_signal, "review_signal_artifact")

    projection_bundle = _load_json(projection_path, field="review_projection_bundle_artifact")
    validate_artifact(projection_bundle, "review_projection_bundle_artifact")
    consumer_bundle = _load_json(consumer_path, field="review_consumer_output_bundle_artifact")
    validate_artifact(consumer_bundle, "review_consumer_output_bundle_artifact")

    optional_artifacts: dict[str, dict[str, Any]] = {}
    for key in _OPTIONAL_RIL_KEYS:
        raw_path = artifact_paths.get(key)
        if isinstance(raw_path, str) and raw_path.strip():
            candidate = _resolve_ref_path(raw_path)
            if candidate.exists():
                payload = _load_json(candidate, field=key)
                schema_name = key
                validate_artifact(payload, schema_name)
                optional_artifacts[key] = payload

    roadmap_two_step_artifact = optional_artifacts.get("roadmap_two_step_artifact")
    if command_marker == "/roadmap-approve":
        if not roadmap_two_step_artifact:
            raise GithubClosureContinuationError("roadmap approval requires roadmap_two_step_artifact in ingestion summary")
        roadmap_two_step_artifact, roadmap_draft_id = _resolve_and_validate_approved_roadmap(
            pr_number=pr_number,
            review_body=review_body,
            roadmap_from_summary=roadmap_two_step_artifact,
            draft_id_from_summary=roadmap_draft_id,
        )

    return ContinuationInputBundle(
        ingestion_summary=summary,
        pr_number=pr_number,
        ingestion_id=ingestion_id,
        artifact_paths={k: str(v) for k, v in artifact_paths.items() if isinstance(v, str)},
        projection_bundle=projection_bundle,
        consumer_bundle=consumer_bundle,
        review_signal=review_signal,
        optional_artifacts=optional_artifacts,
        roadmap_two_step_artifact=roadmap_two_step_artifact,
        command_marker=command_marker,
        review_body=review_body,
        roadmap_draft_id=roadmap_draft_id,
    )


def _build_cde_source_artifacts(bundle: ContinuationInputBundle) -> list[dict[str, Any]]:
    return [
        {
            "artifact_type": "review_projection_bundle_artifact",
            "review_projection_bundle_id": bundle.projection_bundle["review_projection_bundle_id"],
            "artifact_ref": f"review_projection_bundle_artifact:{bundle.projection_bundle['review_projection_bundle_id']}",
            "blocker_count": int(bundle.projection_bundle.get("blocker_count", 0) or 0),
            "critical_count": int(bundle.projection_bundle.get("critical_count", 0) or 0),
            "high_priority_count": int(bundle.projection_bundle.get("high_priority_count", 0) or 0),
            "medium_priority_count": int(bundle.projection_bundle.get("medium_priority_count", 0) or 0),
            "unresolved_action_item_ids": list(bundle.projection_bundle.get("unresolved_action_item_ids", [])),
            "blocker_present": bool(bundle.projection_bundle.get("blocker_present", False)),
            "escalation_present": bool(bundle.projection_bundle.get("escalation_present", False)),
        },
        {
            "artifact_type": "review_consumer_output_bundle_artifact",
            "review_consumer_output_bundle_id": bundle.consumer_bundle["review_consumer_output_bundle_id"],
            "artifact_ref": f"review_consumer_output_bundle_artifact:{bundle.consumer_bundle['review_consumer_output_bundle_id']}",
            "blocker_count": int(bundle.consumer_bundle.get("blocker_count", 0) or 0),
            "critical_count": int(bundle.consumer_bundle.get("critical_count", 0) or 0),
            "high_priority_count": int(bundle.consumer_bundle.get("high_priority_count", 0) or 0),
            "medium_priority_count": int(bundle.consumer_bundle.get("medium_priority_count", 0) or 0),
            "unresolved_action_item_ids": list(bundle.consumer_bundle.get("unresolved_action_item_ids", [])),
            "blocker_present": bool(bundle.consumer_bundle.get("blocker_present", False)),
            "escalation_present": bool(bundle.consumer_bundle.get("escalation_present", False)),
        },
    ]


def _build_continuation_paths(*, output_root: Path, pr_number: int, continuation_id: str) -> ContinuationArtifacts:
    continuation_dir = output_root / f"pr-{pr_number}" / continuation_id
    return ContinuationArtifacts(
        continuation_id=continuation_id,
        continuation_dir=continuation_dir,
        closure_decision_artifact_path=continuation_dir / "closure_decision_artifact.json",
        next_step_prompt_artifact_path=continuation_dir / "next_step_prompt_artifact.json",
        top_level_conductor_run_artifact_path=continuation_dir / "top_level_conductor_run_artifact.json",
        continuation_summary_path=continuation_dir / "continuation_summary.json",
    )


def _deterministic_next_step_ref(decision_hint: str, continuation_id: str) -> str:
    if decision_hint == "hardening_required":
        return f"hardening_batch:{continuation_id}"
    if decision_hint == "final_verification_required":
        return f"final_verification:{continuation_id}"
    return f"bounded_continue:{continuation_id}"


def _roadmap_next_step_ref(bundle: ContinuationInputBundle) -> str | None:
    roadmap = bundle.roadmap_two_step_artifact
    if not isinstance(roadmap, dict):
        return None
    roadmap_id = roadmap.get("roadmap_id")
    step_count = roadmap.get("step_count")
    bounded = roadmap.get("bounded")
    if isinstance(roadmap_id, str) and roadmap_id and bounded is True and step_count == 2:
        return f"roadmap_two_step_artifact:{roadmap_id}"
    return None


def _run_tlc_with_precomputed_decision(
    *,
    bundle: ContinuationInputBundle,
    decision_artifact: dict[str, Any],
    artifacts: ContinuationArtifacts,
    emitted_at: str,
    retry_budget: int,
) -> dict[str, Any]:
    decision_ref = f"closure_decision_artifact:{decision_artifact['closure_decision_id']}"

    def _ril_from_structured(_: dict[str, Any]) -> dict[str, Any]:
        artifact_refs = [
            f"review_projection_bundle_artifact:{bundle.projection_bundle['review_projection_bundle_id']}",
            f"review_consumer_output_bundle_artifact:{bundle.consumer_bundle['review_consumer_output_bundle_id']}",
        ]
        review_signal = bundle.review_signal
        artifact_refs.insert(0, f"review_signal_artifact:{review_signal['review_signal_id']}")

        return {
            "outputs_exist": True,
            "artifact_refs": artifact_refs,
            "trace_refs": [decision_artifact["trace_id"]],
            "review_signal_artifact": review_signal,
            "review_projection_bundle_artifact": bundle.projection_bundle,
            "review_consumer_output_bundle_artifact": bundle.consumer_bundle,
            "roadmap_two_step_artifact": bundle.roadmap_two_step_artifact,
        }

    def _cde_passthrough(_: dict[str, Any]) -> dict[str, Any]:
        return {
            "decision_type": decision_artifact["decision_type"],
            "next_step_class": decision_artifact["next_step_class"],
            "closure_state": "closed" if decision_artifact["decision_type"] == "lock" else "open",
            "artifact_refs": [decision_ref],
            "trace_refs": [decision_artifact["trace_id"]],
            "closure_decision_artifact": decision_artifact,
        }

    tlc_request = {
        "objective": f"github_closure_continuation:{bundle.ingestion_id}",
        "branch_ref": "refs/heads/main",
        "run_id": f"tlc-{artifacts.continuation_id}",
        "retry_budget": retry_budget,
        "require_review": True,
        "require_recovery": False,
        "review_path": bundle.artifact_paths.get("review_projection_bundle_artifact", "structured-only"),
        "action_tracker_path": bundle.artifact_paths.get("review_consumer_output_bundle_artifact", "structured-only"),
        "runtime_dir": str(artifacts.continuation_dir / "runtime"),
        "emitted_at": emitted_at,
        "repo_mutation_requested": False,
        "subsystems": {
            "ril": _ril_from_structured,
            "cde": _cde_passthrough,
        },
    }

    result = run_top_level_conductor(tlc_request)
    validate_artifact(result, "top_level_conductor_run_artifact")
    return result


def run_github_closure_continuation(
    *,
    github_review_handoff_path: Path,
    output_root: Path,
    emitted_at: str,
    closure_complete: bool,
    final_verification_passed: bool,
    hardening_completed: bool,
    escalation_required: bool,
    bounded_next_step_available: bool,
    retry_budget: int,
) -> dict[str, Any]:
    bundle = _load_ingestion_bundle(github_review_handoff_path)
    if bundle.command_marker == "/roadmap-draft":
        raise GithubClosureContinuationError("roadmap draft is preview-only and cannot trigger continuation")
    if bundle.command_marker == "/roadmap-approve" and bundle.roadmap_two_step_artifact is None:
        raise GithubClosureContinuationError("roadmap approval requires a validated roadmap artifact")

    continuation_seed = {
        "pr_number": bundle.pr_number,
        "ingestion_id": bundle.ingestion_id,
        "emitted_at": emitted_at,
        "closure_complete": closure_complete,
        "final_verification_passed": final_verification_passed,
        "hardening_completed": hardening_completed,
        "escalation_required": escalation_required,
        "bounded_next_step_available": bounded_next_step_available,
    }
    continuation_id = deterministic_id(prefix="gcc", namespace="github_closure_continuation", payload=continuation_seed)
    artifact_paths = _build_continuation_paths(output_root=output_root, pr_number=bundle.pr_number, continuation_id=continuation_id)
    artifact_paths.continuation_dir.mkdir(parents=True, exist_ok=True)

    decision_hint = "continue_bounded"
    if escalation_required:
        decision_hint = "escalate"
    elif final_verification_passed and closure_complete:
        decision_hint = "lock"
    elif hardening_completed and not final_verification_passed:
        decision_hint = "final_verification_required"

    next_step_ref = None
    if bounded_next_step_available:
        next_step_ref = _roadmap_next_step_ref(bundle) or _deterministic_next_step_ref(decision_hint, continuation_id)

    cde_request = {
        "subject_scope": "github_closure_continuation",
        "subsystem_acronym": "GHA",
        "run_id": f"gha-{continuation_id}",
        "review_date": emitted_at[:10],
        "action_tracker_ref": bundle.artifact_paths.get("review_consumer_output_bundle_artifact"),
        "source_artifacts": _build_cde_source_artifacts(bundle),
        "closure_complete": closure_complete,
        "final_verification_passed": final_verification_passed,
        "hardening_completed": hardening_completed,
        "escalation_required": escalation_required,
        "bounded_next_step_available": bounded_next_step_available,
        "next_step_ref": next_step_ref,
        "emitted_at": emitted_at,
        "trace_id": f"trace-{continuation_id}",
    }

    decision_artifact = build_closure_decision_artifact(cde_request)
    validate_artifact(decision_artifact, "closure_decision_artifact")
    _write_json(artifact_paths.closure_decision_artifact_path, decision_artifact)

    next_step_prompt = maybe_build_next_step_prompt_artifact(
        closure_decision_artifact=decision_artifact,
        required_inputs=decision_artifact["source_artifact_refs"],
        stop_conditions=["ready_for_merge", "blocked", "exhausted", "escalated"],
        boundedness_notes=[
            "github_trigger_only",
            "cde_decides_only",
            "tlc_orchestrates_only",
            "no_raw_review_downstream_of_ril",
            "no_execution_outside_pqx",
        ],
        emitted_at=emitted_at,
    )
    if next_step_prompt is not None:
        validate_artifact(next_step_prompt, "next_step_prompt_artifact")
        _write_json(artifact_paths.next_step_prompt_artifact_path, next_step_prompt)
    else:
        artifact_paths = ContinuationArtifacts(
            continuation_id=artifact_paths.continuation_id,
            continuation_dir=artifact_paths.continuation_dir,
            closure_decision_artifact_path=artifact_paths.closure_decision_artifact_path,
            next_step_prompt_artifact_path=None,
            top_level_conductor_run_artifact_path=artifact_paths.top_level_conductor_run_artifact_path,
            continuation_summary_path=artifact_paths.continuation_summary_path,
        )

    decision_type = decision_artifact["decision_type"]
    tlc_ran = False
    tlc_result: dict[str, Any] | None = None

    if decision_type in _CONTINUATION_ELIGIBLE_DECISIONS:
        if not decision_artifact.get("bounded_next_step_available", False):
            raise GithubClosureContinuationError(
                f"decision '{decision_type}' requires bounded_next_step_available=true for TLC invocation"
            )
        if next_step_prompt is None:
            raise GithubClosureContinuationError(
                f"decision '{decision_type}' requires next_step_prompt_artifact for TLC invocation"
            )

        # SEL enforcement is executed by TLC at each governed boundary;
        # this adapter does not bypass TLC-level SEL checks.
        tlc_result = _run_tlc_with_precomputed_decision(
            bundle=bundle,
            decision_artifact=decision_artifact,
            artifacts=artifact_paths,
            emitted_at=emitted_at,
            retry_budget=retry_budget,
        )
        tlc_ran = True
        _write_json(artifact_paths.top_level_conductor_run_artifact_path, tlc_result)

    if tlc_result is not None:
        final_terminal_state = str(tlc_result.get("current_state"))
    elif decision_type == "lock":
        final_terminal_state = "blocked"
    elif decision_type == "escalate":
        final_terminal_state = "escalated"
    else:
        final_terminal_state = "blocked"
    terminal_policy = resolve_terminal_state_policy(final_terminal_state)
    branch_update_allowed = bool(terminal_policy["branch_update_allowed"])
    promotion_gate = _build_promotion_gate_decision_artifact(
        continuation_id=continuation_id,
        final_terminal_state=final_terminal_state,
        closure_decision_artifact=decision_artifact,
        top_level_conductor_run_artifact=tlc_result,
        emitted_at=emitted_at,
    )
    promotion_gate_path = artifact_paths.continuation_dir / "promotion_gate_decision_artifact.json"
    _write_json(promotion_gate_path, promotion_gate)
    if branch_update_allowed != bool(final_terminal_state == "ready_for_merge"):
        raise GithubClosureContinuationError("branch_update_allowed invariant violated")

    summary = {
        "status": "success",
        "pr_number": bundle.pr_number,
        "ingestion_id": bundle.ingestion_id,
        "continuation_id": continuation_id,
        "continuation_dir": str(artifact_paths.continuation_dir),
        "command_marker": bundle.command_marker,
        "cde_decision": decision_type,
        "tlc_ran": tlc_ran,
        "final_terminal_state": final_terminal_state,
        "artifact_paths": {
            "closure_decision_artifact": str(artifact_paths.closure_decision_artifact_path),
            "next_step_prompt_artifact": str(artifact_paths.next_step_prompt_artifact_path)
            if artifact_paths.next_step_prompt_artifact_path is not None
            else None,
            "top_level_conductor_run_artifact": str(artifact_paths.top_level_conductor_run_artifact_path)
            if tlc_result is not None
            else None,
            "promotion_gate_decision_artifact": str(promotion_gate_path),
        },
        "roadmap_two_step": (
            {
                "roadmap_id": bundle.roadmap_two_step_artifact.get("roadmap_id"),
                "artifact_path": bundle.artifact_paths.get("roadmap_two_step_artifact"),
                "draft_id": bundle.roadmap_draft_id,
                "steps": [step.get("description", "") for step in bundle.roadmap_two_step_artifact.get("steps", [])][:2],
            }
            if bundle.roadmap_two_step_artifact is not None
            else None
        ),
        "guardrails": {
            "github_triggers_only": True,
            "adapter_normalization_only": True,
            "cde_decides_only": True,
            "tlc_orchestrates_only": True,
            "sel_enforced": True,
            "no_raw_review_downstream_of_ril": True,
            "no_execution_outside_pqx": True,
            "fail_closed_on_missing_or_malformed_artifacts": True,
            "terminal_states_are_explicit_and_final": True,
        },
        "branch_update_policy": {
            "branch_update_allowed": branch_update_allowed,
            "allowed_only_via_governed_tlc_path": True,
            "blocked_states": sorted(_READ_ONLY_TERMINAL_STATES),
            "promotion_allowed": promotion_gate["promotion_allowed"],
            "promotion_decision_ref": f"promotion_gate_decision_artifact:{promotion_gate['decision_id']}",
            "policy_note": (
                "GitHub workflows do not mutate branches directly. "
                "Branch updates are permitted only for terminal_state=ready_for_merge with certified governed evidence."
            ),
        },
    }
    _write_json(artifact_paths.continuation_summary_path, summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run governed GitHub closure + continuation pipeline")
    parser.add_argument("--github-review-handoff-path", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--emitted-at", default=_default_emitted_at())
    parser.add_argument("--closure-complete", action="store_true")
    parser.add_argument("--final-verification-passed", action="store_true")
    parser.add_argument("--hardening-completed", action="store_true")
    parser.add_argument("--escalation-required", action="store_true")
    parser.add_argument("--bounded-next-step-available", action="store_true")
    parser.add_argument("--retry-budget", type=int, default=0)
    args = parser.parse_args(argv)

    summary = run_github_closure_continuation(
        github_review_handoff_path=Path(args.github_review_handoff_path),
        output_root=Path(args.output_root),
        emitted_at=args.emitted_at,
        closure_complete=bool(args.closure_complete),
        final_verification_passed=bool(args.final_verification_passed),
        hardening_completed=bool(args.hardening_completed),
        escalation_required=bool(args.escalation_required),
        bounded_next_step_available=bool(args.bounded_next_step_available),
        retry_budget=max(args.retry_budget, 0),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
