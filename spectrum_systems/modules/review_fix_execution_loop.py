"""RQX-B2 one-cycle review-fix execution loop with mandatory TPA gating before PQX."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema, validate_artifact
from spectrum_systems.modules.review_handoff_disposition import emit_review_handoff_disposition
from spectrum_systems.modules.review_queue_executor import run_review_queue_executor
from spectrum_systems.modules.runtime.codex_to_pqx_task_wrapper import run_wrapped_pqx_task
from spectrum_systems.modules.runtime.lineage_authenticity import LineageAuthenticityError, verify_authenticity

REQUEST_FILE_SUFFIX = "_review_fix_execution_request_artifact.json"
RESULT_FILE_SUFFIX = "_review_fix_execution_result_artifact.json"
OPERATOR_HANDOFF_FILE_SUFFIX = "_review_operator_handoff_artifact.json"


class ReviewFixExecutionLoopError(ValueError):
    """Raised when the one-cycle review-fix loop must fail closed."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_tpa_gate_provenance_token(tpa_slice_artifact: Mapping[str, Any]) -> str:
    gate_artifact = tpa_slice_artifact.get("artifact")
    if not isinstance(gate_artifact, Mapping):
        raise ReviewFixExecutionLoopError("tpa_slice_artifact.artifact must be an object")
    payload = {
        "artifact_id": str(tpa_slice_artifact.get("artifact_id") or ""),
        "run_id": str(tpa_slice_artifact.get("run_id") or ""),
        "trace_id": str(tpa_slice_artifact.get("trace_id") or ""),
        "slice_id": str(tpa_slice_artifact.get("slice_id") or ""),
        "step_id": str(tpa_slice_artifact.get("step_id") or ""),
        "phase": str(tpa_slice_artifact.get("phase") or ""),
        "produced_at": str(tpa_slice_artifact.get("produced_at") or ""),
        "artifact_kind": str(gate_artifact.get("artifact_kind") or ""),
        "review_signal_refs": sorted(str(ref) for ref in (gate_artifact.get("review_signal_refs") or []) if str(ref)),
        "selection_inputs": gate_artifact.get("selection_inputs") or {},
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def validate_tpa_slice_authority(*, request_artifact: Mapping[str, Any], repo_root: Path) -> dict[str, Any]:
    tpa_slice_artifact = request_artifact["tpa_slice_artifact"]
    artifact_id = str(tpa_slice_artifact.get("artifact_id") or "").strip()
    if not artifact_id:
        raise ReviewFixExecutionLoopError("authoritative TPA provenance requires tpa_slice_artifact.artifact_id")

    try:
        authenticity = verify_authenticity(artifact=dict(tpa_slice_artifact), expected_issuer="TPA")
    except LineageAuthenticityError as exc:
        raise ReviewFixExecutionLoopError(f"authoritative TPA provenance authenticity invalid:{exc}") from exc

    expected_trace_id = str(request_artifact.get("trace_id") or tpa_slice_artifact.get("trace_id") or "").strip()
    if not expected_trace_id or str(tpa_slice_artifact.get("trace_id") or "").strip() != expected_trace_id:
        raise ReviewFixExecutionLoopError("authoritative TPA provenance trace_id mismatch")

    expected_step_id = str((((request_artifact.get("pqx_task_wrapper") or {}).get("task_identity") or {}).get("step_id") or "")).strip()
    if expected_step_id and str(tpa_slice_artifact.get("step_id") or "").strip() != expected_step_id:
        raise ReviewFixExecutionLoopError("authoritative TPA provenance step_id mismatch")

    request_id = str(request_artifact.get("request_id") or "").strip()
    scope = str(authenticity.get("scope") or "")
    if request_id and f":{request_id}:" not in scope:
        raise ReviewFixExecutionLoopError("authoritative TPA provenance request binding mismatch")

    # Local authority files remain optional audit/debug artifacts and are non-authoritative.
    path = repo_root / "artifacts" / "tpa_authority" / f"{artifact_id}.json"
    artifact_ref = str(path) if path.is_file() else None
    return {
        "artifact_ref": artifact_ref,
        "issued_by_system": "TPA",
        "authenticity": authenticity,
    }


def validate_tpa_gate_authoritative_provenance(*, request_artifact: Mapping[str, Any], repo_root: Path) -> dict[str, Any]:
    """Backward-compatible wrapper; authority is enforced by authenticity verification only."""
    return validate_tpa_slice_authority(request_artifact=request_artifact, repo_root=repo_root)


def _validate(instance: dict[str, Any], schema_name: str) -> None:
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda error: str(error.path))
    if errors:
        raise ReviewFixExecutionLoopError("; ".join(error.message for error in errors))


def validate_review_fix_execution_request_artifact(request_artifact: dict[str, Any]) -> None:
    _validate(request_artifact, "review_fix_execution_request_artifact")


def validate_review_fix_execution_result_artifact(result_artifact: dict[str, Any]) -> None:
    _validate(result_artifact, "review_fix_execution_result_artifact")


def validate_review_operator_handoff_artifact(handoff_artifact: dict[str, Any]) -> None:
    _validate(handoff_artifact, "review_operator_handoff_artifact")


def _handoff_reason_and_next_action(result_artifact: Mapping[str, Any]) -> tuple[str, str]:
    status = result_artifact["status"]
    if status == "blocked_checkpoint_missing":
        return "checkpoint_required", "request_checkpoint_decision"
    if status == "blocked_by_tpa":
        return "tpa_blocked", "manual_review_required"
    if status == "execution_failed":
        return "execution_failed", "request_failure_diagnosis"

    verdict = result_artifact["post_fix_review"]["verdict"]
    if verdict == "fix_required":
        return "post_cycle_fix_still_required", "schedule_follow_on_cycle"
    if verdict == "not_safe_to_merge":
        return "post_cycle_not_safe_to_merge", "escalate_to_owner"
    return "review_incomplete", "manual_review_required"


def _build_operator_handoff_artifact(
    request_artifact: Mapping[str, Any],
    result_artifact: Mapping[str, Any],
    *,
    review_result_artifact: Mapping[str, Any] | None,
    emitted_at: str,
) -> dict[str, Any]:
    handoff_reason, recommended_next_action = _handoff_reason_and_next_action(result_artifact)
    unresolved_finding_refs: list[str] = []
    if isinstance(review_result_artifact, Mapping):
        review_id = str(review_result_artifact["review_id"])
        for finding in review_result_artifact.get("findings", []):
            if isinstance(finding, Mapping):
                finding_id = finding.get("finding_id")
                if isinstance(finding_id, str) and finding_id.strip():
                    unresolved_finding_refs.append(f"review_result_artifact:{review_id}#{finding_id}")

    blocking_conditions = [f"terminal_status:{result_artifact['status']}"]
    tpa_reason = result_artifact["tpa_decision"].get("reason")
    if isinstance(tpa_reason, str) and tpa_reason.strip():
        blocking_conditions.append(f"tpa_reason:{tpa_reason}")
    execution_error = result_artifact["pqx_execution"].get("error")
    if isinstance(execution_error, str) and execution_error.strip():
        blocking_conditions.append(f"pqx_error:{execution_error}")

    source_review_result_ref = result_artifact["post_fix_review"]["review_result_ref"]
    handoff = {
        "artifact_type": "review_operator_handoff_artifact",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.0.0",
        "handoff_id": f"roha:{result_artifact['result_id']}",
        "review_id": result_artifact["review_id"],
        "source_review_result_ref": source_review_result_ref,
        "source_review_fix_execution_result_ref": f"review_fix_execution_result_artifact:{result_artifact['result_id']}",
        "post_cycle_verdict": result_artifact["post_fix_review"]["verdict"],
        "handoff_reason": handoff_reason,
        "recommended_next_action": recommended_next_action,
        "blocking_conditions": blocking_conditions,
        "unresolved_finding_refs": unresolved_finding_refs,
        "target_scope": request_artifact["post_fix_review_request_artifact"]["scope"],
        "target_files": request_artifact["post_fix_review_request_artifact"]["changed_files"],
        "target_surface_refs": request_artifact["fix_slices"][0]["target_surface_refs"],
        "future_fix_cycle_permitted": True,
        "provenance": {
            "emitted_by_system": "RQX",
            "loop_execution_mode": "single_bounded_cycle",
            "auto_reentry_triggered": False,
        },
        "trace_linkage": {
            "request_ref": result_artifact["request_ref"],
            "fix_slice_ref": result_artifact["fix_slice_ref"],
            "tpa_artifact_ref": result_artifact["tpa_decision"]["tpa_artifact_ref"],
            "pqx_execution_ref": result_artifact["pqx_execution"]["execution_ref"],
        },
        "emitted_at": emitted_at,
    }
    validate_review_operator_handoff_artifact(handoff)
    return handoff


def _emit_result_bundle(
    request_artifact: Mapping[str, Any],
    result_artifact: dict[str, Any],
    *,
    output_dir: Path,
    review_result_artifact: Mapping[str, Any] | None = None,
    review_merge_readiness_artifact: Mapping[str, Any] | None = None,
    markdown_review_path: str | None = None,
) -> dict[str, Any]:
    unresolved_statuses = {
        "completed_fix_still_required",
        "completed_not_safe_to_merge",
        "blocked_by_tpa",
        "blocked_checkpoint_missing",
        "execution_failed",
    }
    emit_handoff = result_artifact["status"] in unresolved_statuses
    handoff_artifact: dict[str, Any] | None = None
    handoff_path: Path | None = None
    disposition_result: dict[str, Any] | None = None
    if emit_handoff:
        handoff_artifact = _build_operator_handoff_artifact(
            request_artifact,
            result_artifact,
            review_result_artifact=review_result_artifact,
            emitted_at=result_artifact["generated_at"],
        )
        handoff_path = output_dir / f"{result_artifact['review_id']}{OPERATOR_HANDOFF_FILE_SUFFIX}"
        handoff_path.write_text(json.dumps(handoff_artifact, indent=2) + "\n", encoding="utf-8")
        disposition_result = emit_review_handoff_disposition(handoff_artifact, output_dir=output_dir)
        result_artifact["operator_handoff_ref"] = (
            f"review_operator_handoff_artifact:{handoff_artifact['handoff_id']}"
        )
    else:
        result_artifact["operator_handoff_ref"] = None

    validate_review_fix_execution_result_artifact(result_artifact)
    result_path = output_dir / f"{result_artifact['review_id']}{RESULT_FILE_SUFFIX}"
    result_path.write_text(json.dumps(result_artifact, indent=2) + "\n", encoding="utf-8")

    response = {
        "review_fix_execution_result_artifact": result_artifact,
        "review_fix_execution_result_artifact_path": str(result_path),
    }
    if handoff_artifact is not None and handoff_path is not None:
        response["review_operator_handoff_artifact"] = handoff_artifact
        response["review_operator_handoff_artifact_path"] = str(handoff_path)
    if disposition_result is not None:
        response.update(disposition_result)
    if review_result_artifact is not None:
        response["post_fix_review_result_artifact"] = review_result_artifact
    if review_merge_readiness_artifact is not None:
        response["post_fix_review_merge_readiness_artifact"] = review_merge_readiness_artifact
    if markdown_review_path is not None:
        response["post_fix_markdown_review_path"] = markdown_review_path
    return response


def _tpa_gate_decision(tpa_slice_artifact: Mapping[str, Any]) -> tuple[str, str | None]:
    validate_artifact(dict(tpa_slice_artifact), "tpa_slice_artifact")
    if tpa_slice_artifact.get("phase") != "gate":
        raise ReviewFixExecutionLoopError("TPA artifact must be phase=gate for review fix execution")

    gate_artifact = tpa_slice_artifact.get("artifact")
    if not isinstance(gate_artifact, Mapping):
        raise ReviewFixExecutionLoopError("tpa_slice_artifact.artifact must be an object")

    if gate_artifact.get("artifact_kind") != "gate":
        raise ReviewFixExecutionLoopError("TPA gate artifact_kind is required")

    fail_reason = gate_artifact.get("fail_closed_reason")
    if isinstance(fail_reason, str) and fail_reason.strip():
        return "block", fail_reason

    if gate_artifact.get("promotion_ready") is not True:
        return "block", "tpa_promotion_not_ready"

    if gate_artifact.get("high_risk_unmitigated") is True:
        return "block", "tpa_high_risk_unmitigated"

    complexity_gate = gate_artifact.get("complexity_regression_gate")
    if not isinstance(complexity_gate, Mapping):
        raise ReviewFixExecutionLoopError("tpa gate artifact missing complexity_regression_gate")
    if complexity_gate.get("decision") not in {"allow", "warn"}:
        return "block", "tpa_complexity_regression_gate_blocked"

    simplicity_review = gate_artifact.get("simplicity_review")
    if not isinstance(simplicity_review, Mapping):
        raise ReviewFixExecutionLoopError("tpa gate artifact missing simplicity_review")
    if simplicity_review.get("decision") not in {"allow", "warn"}:
        return "block", "tpa_simplicity_review_blocked"

    return "allow", None


def _assert_tpa_gated_fix_flow(request_artifact: Mapping[str, Any], *, repo_root: Path) -> None:
    fix_slice = request_artifact["fix_slices"][0]
    source_review_result_ref = request_artifact["source_review_result_ref"]
    if fix_slice.get("review_result_ref") != source_review_result_ref:
        raise ReviewFixExecutionLoopError("review_fix_slice_artifact must match source_review_result_ref")

    tpa_slice_artifact = request_artifact["tpa_slice_artifact"]
    if tpa_slice_artifact.get("artifact_type") != "tpa_slice_artifact":
        raise ReviewFixExecutionLoopError("only tpa_slice_artifact may enter PQX fix execution")

    gate_artifact = tpa_slice_artifact.get("artifact")
    if not isinstance(gate_artifact, Mapping):
        raise ReviewFixExecutionLoopError("tpa_slice_artifact.artifact must be an object")

    review_signal_refs = gate_artifact.get("review_signal_refs")
    if not isinstance(review_signal_refs, list) or source_review_result_ref not in review_signal_refs:
        raise ReviewFixExecutionLoopError(
            "tpa gate must bind to source_review_result_ref before PQX execution"
        )
    validate_tpa_slice_authority(
        request_artifact=request_artifact,
        repo_root=repo_root,
    )


def _default_pqx_executor(request_artifact: Mapping[str, Any]) -> dict[str, Any]:
    runtime = request_artifact.get("pqx_runtime")
    if not isinstance(runtime, Mapping):
        raise ReviewFixExecutionLoopError(
            "pqx_runtime is required when using default PQX executor"
        )
    return run_wrapped_pqx_task(
        wrapper=request_artifact["pqx_task_wrapper"],
        roadmap_path=Path(str(runtime["roadmap_path"])),
        state_path=Path(str(runtime["state_path"])),
        runs_root=Path(str(runtime["runs_root"])),
        pqx_output_text=str(runtime["pqx_output_text"]),
    )


def run_review_fix_execution_cycle(
    request_artifact: dict[str, Any],
    *,
    output_dir: Path,
    repo_root: Path,
    review_docs_dir: Path,
    pqx_executor: Callable[[Mapping[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Execute exactly one RQX→TPA→PQX→RQX bounded cycle and emit terminal artifacts."""

    if "raw_prompt_text" in request_artifact or "review_markdown" in request_artifact:
        raise ReviewFixExecutionLoopError(
            "raw prompt text and review markdown are not executable governed inputs; provide fix_slices and pqx_task_wrapper only"
        )

    validate_review_fix_execution_request_artifact(request_artifact)
    _assert_tpa_gated_fix_flow(request_artifact, repo_root=repo_root)
    output_dir.mkdir(parents=True, exist_ok=True)

    request_id = str(request_artifact["request_id"])
    review_id = str(request_artifact["review_id"])
    fix_slice = request_artifact["fix_slices"][0]
    fix_slice_id = str(fix_slice["fix_slice_id"])

    checkpoint_required = bool(request_artifact["checkpoint_required"])
    checkpoint_ref = request_artifact.get("checkpoint_ref")
    if checkpoint_required and (not isinstance(checkpoint_ref, str) or not checkpoint_ref.strip()):
        result = {
            "artifact_type": "review_fix_execution_result_artifact",
            "artifact_version": "1.0.0",
            "schema_version": "1.0.0",
            "standards_version": "1.0.0",
            "result_id": f"rferes:{request_id}",
            "request_ref": f"review_fix_execution_request_artifact:{request_id}",
            "review_id": review_id,
            "fix_slice_ref": f"review_fix_slice_artifact:{fix_slice_id}",
            "loop_cycle_count": 1,
            "status": "blocked_checkpoint_missing",
            "tpa_decision": {
                "decision": "block",
                "tpa_artifact_ref": f"tpa_slice_artifact:{request_artifact['tpa_slice_artifact']['artifact_id']}",
                "phase": "gate",
                "reason": "checkpoint_required_missing",
            },
            "pqx_execution": {
                "attempted": False,
                "execution_ref": None,
                "status": None,
                "error": "checkpoint_required_missing",
            },
            "post_fix_review": {
                "attempted": False,
                "review_result_ref": None,
                "review_merge_readiness_ref": None,
                "markdown_review_path": None,
                "verdict": None,
            },
            "stopped": True,
            "generated_at": _utc_now(),
        }
        return _emit_result_bundle(request_artifact, result, output_dir=output_dir)

    tpa_decision, tpa_reason = _tpa_gate_decision(request_artifact["tpa_slice_artifact"])
    if tpa_decision != "allow":
        result = {
            "artifact_type": "review_fix_execution_result_artifact",
            "artifact_version": "1.0.0",
            "schema_version": "1.0.0",
            "standards_version": "1.0.0",
            "result_id": f"rferes:{request_id}",
            "request_ref": f"review_fix_execution_request_artifact:{request_id}",
            "review_id": review_id,
            "fix_slice_ref": f"review_fix_slice_artifact:{fix_slice_id}",
            "loop_cycle_count": 1,
            "status": "blocked_by_tpa",
            "tpa_decision": {
                "decision": "block",
                "tpa_artifact_ref": f"tpa_slice_artifact:{request_artifact['tpa_slice_artifact']['artifact_id']}",
                "phase": "gate",
                "reason": tpa_reason,
            },
            "pqx_execution": {
                "attempted": False,
                "execution_ref": None,
                "status": None,
                "error": tpa_reason,
            },
            "post_fix_review": {
                "attempted": False,
                "review_result_ref": None,
                "review_merge_readiness_ref": None,
                "markdown_review_path": None,
                "verdict": None,
            },
            "stopped": True,
            "generated_at": _utc_now(),
        }
        return _emit_result_bundle(request_artifact, result, output_dir=output_dir)

    executor = pqx_executor or _default_pqx_executor
    try:
        pqx_result = executor(request_artifact)
    except Exception as exc:
        result = {
            "artifact_type": "review_fix_execution_result_artifact",
            "artifact_version": "1.0.0",
            "schema_version": "1.0.0",
            "standards_version": "1.0.0",
            "result_id": f"rferes:{request_id}",
            "request_ref": f"review_fix_execution_request_artifact:{request_id}",
            "review_id": review_id,
            "fix_slice_ref": f"review_fix_slice_artifact:{fix_slice_id}",
            "loop_cycle_count": 1,
            "status": "execution_failed",
            "tpa_decision": {
                "decision": "allow",
                "tpa_artifact_ref": f"tpa_slice_artifact:{request_artifact['tpa_slice_artifact']['artifact_id']}",
                "phase": "gate",
                "reason": None,
            },
            "pqx_execution": {
                "attempted": True,
                "execution_ref": None,
                "status": "failed",
                "error": str(exc),
            },
            "post_fix_review": {
                "attempted": False,
                "review_result_ref": None,
                "review_merge_readiness_ref": None,
                "markdown_review_path": None,
                "verdict": None,
            },
            "stopped": True,
            "generated_at": _utc_now(),
        }
        return _emit_result_bundle(request_artifact, result, output_dir=output_dir)

    if not isinstance(pqx_result, Mapping):
        raise ReviewFixExecutionLoopError("PQX execution result must be an object")

    review_result = run_review_queue_executor(
        request_artifact["post_fix_review_request_artifact"],
        repo_root=repo_root,
        output_dir=output_dir,
        review_docs_dir=review_docs_dir,
    )
    post_verdict = review_result["review_result_artifact"]["verdict"]
    status = {
        "safe_to_merge": "completed_safe_to_merge",
        "fix_required": "completed_fix_still_required",
        "not_safe_to_merge": "completed_not_safe_to_merge",
    }[post_verdict]

    result = {
        "artifact_type": "review_fix_execution_result_artifact",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.0.0",
        "result_id": f"rferes:{request_id}",
        "request_ref": f"review_fix_execution_request_artifact:{request_id}",
        "review_id": review_id,
        "fix_slice_ref": f"review_fix_slice_artifact:{fix_slice_id}",
        "loop_cycle_count": 1,
        "status": status,
        "tpa_decision": {
            "decision": "allow",
            "tpa_artifact_ref": f"tpa_slice_artifact:{request_artifact['tpa_slice_artifact']['artifact_id']}",
            "phase": "gate",
            "reason": None,
        },
        "pqx_execution": {
            "attempted": True,
            "execution_ref": str(pqx_result.get("execution_ref") or pqx_result.get("slice_execution_record") or "exec:unknown"),
            "status": str(pqx_result.get("status") or "complete"),
            "error": None,
        },
        "post_fix_review": {
            "attempted": True,
            "review_result_ref": f"review_result_artifact:{review_result['review_result_artifact']['review_id']}",
            "review_merge_readiness_ref": f"review_merge_readiness_artifact:{review_result['review_merge_readiness_artifact']['review_id']}",
            "markdown_review_path": str(review_result["markdown_review_path"]),
            "verdict": post_verdict,
        },
        "stopped": True,
        "generated_at": _utc_now(),
    }
    return _emit_result_bundle(
        request_artifact,
        result,
        output_dir=output_dir,
        review_result_artifact=review_result["review_result_artifact"],
        review_merge_readiness_artifact=review_result["review_merge_readiness_artifact"],
        markdown_review_path=review_result["markdown_review_path"],
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one bounded RQX→TPA→PQX→RQX review-fix cycle.")
    parser.add_argument("--request", required=True, help="Path to review_fix_execution_request_artifact JSON.")
    parser.add_argument("--output-dir", default="artifacts/reviews", help="Directory for result artifacts.")
    parser.add_argument("--review-docs-dir", default="docs/reviews", help="Directory for markdown review artifacts.")
    parser.add_argument("--repo-root", default=".", help="Repository root for post-fix review inputs.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    request_path = Path(args.request)
    request = json.loads(request_path.read_text(encoding="utf-8"))
    result = run_review_fix_execution_cycle(
        request,
        output_dir=Path(args.output_dir),
        repo_root=Path(args.repo_root),
        review_docs_dir=Path(args.review_docs_dir),
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
