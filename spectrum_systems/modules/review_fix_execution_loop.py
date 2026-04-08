"""RQX-B2 one-cycle review-fix execution loop with mandatory TPA gating before PQX."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema, validate_artifact
from spectrum_systems.modules.review_queue_executor import run_review_queue_executor
from spectrum_systems.modules.runtime.codex_to_pqx_task_wrapper import run_wrapped_pqx_task

REQUEST_FILE_SUFFIX = "_review_fix_execution_request_artifact.json"
RESULT_FILE_SUFFIX = "_review_fix_execution_result_artifact.json"


class ReviewFixExecutionLoopError(ValueError):
    """Raised when the one-cycle review-fix loop must fail closed."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
        validate_review_fix_execution_result_artifact(result)
        result_path = output_dir / f"{review_id}{RESULT_FILE_SUFFIX}"
        result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return {
            "review_fix_execution_result_artifact": result,
            "review_fix_execution_result_artifact_path": str(result_path),
        }

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
        validate_review_fix_execution_result_artifact(result)
        result_path = output_dir / f"{review_id}{RESULT_FILE_SUFFIX}"
        result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return {
            "review_fix_execution_result_artifact": result,
            "review_fix_execution_result_artifact_path": str(result_path),
        }

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
        validate_review_fix_execution_result_artifact(result)
        result_path = output_dir / f"{review_id}{RESULT_FILE_SUFFIX}"
        result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return {
            "review_fix_execution_result_artifact": result,
            "review_fix_execution_result_artifact_path": str(result_path),
        }

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
    validate_review_fix_execution_result_artifact(result)

    result_path = output_dir / f"{review_id}{RESULT_FILE_SUFFIX}"
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    return {
        "review_fix_execution_result_artifact": result,
        "review_fix_execution_result_artifact_path": str(result_path),
        "post_fix_review_result_artifact": review_result["review_result_artifact"],
        "post_fix_review_merge_readiness_artifact": review_result["review_merge_readiness_artifact"],
        "post_fix_markdown_review_path": review_result["markdown_review_path"],
    }


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
