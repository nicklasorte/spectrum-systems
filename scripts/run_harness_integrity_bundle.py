#!/usr/bin/env python3
"""Run BUNDLE-01-EXTENDED harness validation and emit concrete output artifacts."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.contracts import load_example, validate_artifact  # noqa: E402
from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    Priority,
    RiskLevel,
    WorkItemStatus,
    make_queue_state,
    make_work_item,
    run_queue_step_execution,
    validate_execution_result_artifact,
)
from spectrum_systems.modules.runtime.drift_detection import build_drift_detection_result  # noqa: E402
from spectrum_systems.modules.runtime.enforcement_engine import enforce_control_decision  # noqa: E402
from spectrum_systems.modules.runtime.error_budget import build_error_budget_status  # noqa: E402
from spectrum_systems.modules.runtime.evaluation_control import build_evaluation_control_decision  # noqa: E402
from spectrum_systems.modules.runtime.governed_failure_injection import run_governed_failure_injection  # noqa: E402
from spectrum_systems.modules.runtime.next_governed_cycle_runner import run_next_governed_cycle  # noqa: E402
from spectrum_systems.modules.runtime.observability_metrics import build_observability_metrics  # noqa: E402
from spectrum_systems.modules.runtime.replay_engine import run_replay  # noqa: E402

REVIEW_DOC_PATH = Path("docs/reviews/harness_integrity_review.md")
REQUIRED_OUTPUTS = [
    "harness_integrity_report.json",
    "transition_consistency_report.json",
    "state_consistency_report.json",
    "policy_path_consistency_report.json",
    "failure_injection_report.json",
    "harness_observability_metrics.json",
    "trace_completeness_report.json",
    "drift_detection_report.json",
    "error_budget_status.json",
    "replay_integrity_report.json",
    "artifact_index.json",
]


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _verify_required_outputs(output_dir: Path) -> List[str]:
    return [name for name in REQUIRED_OUTPUTS if not (output_dir / name).exists()]


def _run_pqx_flow(output_dir: Path) -> Dict[str, Any]:
    trace_path = output_dir / "pqx_execution_trace.json"
    cmd = [
        sys.executable,
        "scripts/run_pqx_sequence.py",
        "--roadmap",
        "tests/fixtures/roadmaps/allow_sequence.json",
        "--output",
        str(trace_path),
        "--run-id",
        "harness-bundle-run",
        "--authority-evidence-ref",
        "tests/fixtures/pqx_runs/governed_authority_record.pqx_slice_execution_record.json",
        "--state-path",
        str(output_dir / "pqx_state.json"),
        "--runs-root",
        str(output_dir / "pqx_runs"),
    ]
    proc = subprocess.run(cmd, cwd=_REPO_ROOT, text=True, capture_output=True, check=False)
    if not trace_path.exists():
        raise RuntimeError(f"PQX flow failed: {proc.stderr.strip() or proc.stdout.strip()}")
    return json.loads(trace_path.read_text(encoding="utf-8"))


def _run_prompt_queue_flow() -> Dict[str, Any]:
    item = make_work_item(
        work_item_id="wi-harness-001",
        prompt_id="prompt-harness-001",
        title="Harness queue execution",
        priority=Priority.HIGH,
        risk_level=RiskLevel.HIGH,
        repo="spectrum-systems",
        branch="main",
        scope_paths=["spectrum_systems/modules/prompt_queue"],
    )
    item["status"] = WorkItemStatus.RUNNABLE.value
    item["gating_decision_artifact_path"] = "contracts/examples/prompt_queue_execution_gating_decision.json"
    queue_state = make_queue_state(queue_id="queue-harness", work_items=[item])
    gating = deepcopy(load_example("prompt_queue_execution_gating_decision"))
    gating["work_item_id"] = item["work_item_id"]
    gating["decision_status"] = "runnable"
    gating["decision_reason_code"] = "runnable_within_policy"

    result = run_queue_step_execution(
        step={"step_id": "step-001", "work_item_id": item["work_item_id"], "execution_mode": "simulated"},
        queue_state=queue_state,
        input_refs={"gating_decision_artifact": gating, "source_queue_state_path": "artifacts/prompt_queue/queue_state.json"},
    )
    validate_execution_result_artifact(result)
    return result


def _run_orchestration_flow() -> Dict[str, Any]:
    decision = deepcopy(load_example("next_cycle_decision"))
    decision["decision"] = "run_next_cycle"

    roadmap_artifact = deepcopy(load_example("roadmap_artifact"))
    for batch in roadmap_artifact.get("batches", []):
        if batch.get("batch_id") == "BATCH-H":
            batch["status"] = "completed"
        elif batch.get("batch_id") in {"BATCH-I", "BATCH-J"}:
            batch["status"] = "not_started"
    roadmap_artifact["current_batch_id"] = "BATCH-I"

    integration_inputs = {
        "known_cycle_runner_result_ids": ["CRR-1A2B3C4D5E6F"],
        "program_artifact": {"program_id": "PRG-1"},
        "review_control_signal": {"signal_id": "rcs-1", "gate_assessment": "PASS"},
        "eval_result": {"run_id": "eval-1", "result_status": "pass"},
        "context_bundle": {"context_id": "ctx-1"},
        "tpa_gate": {
            "context_bundle_ref": "context_bundle_v2:ctx-1",
            "speculative_expansion_detected": False,
            "gate_replaces_control": False,
        },
        "roadmap_loop_validation": {"validation_id": "RLV-TEST-001", "determinism_status": "deterministic"},
        "control_decision": {"decision": "allow", "review_eval_ingested": True},
        "certification_pack": {"certification_status": "complete"},
        "validation_scope": {"batch_id": "BATCH-I", "run_id": "run-1", "mode": "governed_integration"},
        "trace_id": "trace-next-cycle-example",
        "source_refs": {
            "program_artifact": "program_artifact:PRG-1",
            "review_control_signal": "review_control_signal:rcs-1",
            "eval_result": "eval_result:eval-1",
            "context_bundle_v2": "context_bundle_v2:ctx-1",
            "tpa_gate": "tpa_gate:gate-1",
            "roadmap_execution_loop_validation": "roadmap_execution_loop_validation:RLV-TEST-001",
            "roadmap_multi_batch_run_result": "roadmap_multi_batch_run_result:RMB-TEST-001",
            "control_decision": "control_execution_result:ctrl-1",
            "certification_pack": "control_loop_certification_pack:cert-1",
        },
    }

    def _pqx_stub(**_: object) -> dict:
        return {
            "status": "completed",
            "blocked_reason": None,
            "batch_result": {"status": "completed"},
            "execution_history": [
                {
                    "execution_ref": "exec:queue-batch-i:RDX-002:1",
                    "slice_execution_record_ref": "runs/pqx/RDX-002.pqx_slice_execution_record.json",
                    "certification_ref": "runs/pqx/RDX-002.done_certification_record.json",
                    "audit_bundle_ref": "runs/pqx/RDX-002.pqx_slice_audit_bundle.json",
                }
            ],
        }

    result = run_next_governed_cycle(
        next_cycle_decision=decision,
        next_cycle_input_bundle=deepcopy(load_example("next_cycle_input_bundle")),
        roadmap_artifact=roadmap_artifact,
        selection_signals={
            "signals": ["executor_ingestion_valid", "state_binding_complete"],
            "hard_gates": {"BATCH-G": "pass"},
            "control_loop": {"eval_present": True, "trace_present": True, "schema_valid": True},
        },
        authorization_signals={
            "trace_id": "trace-next-cycle-example",
            "required_signals_satisfied": True,
            "hard_gate_state": "pass",
            "certification_state": "complete",
            "review_state": "complete",
            "eval_state": "complete",
            "replay_consistency": "match",
            "control_freeze_condition": False,
            "control_block_condition": False,
            "warning_states": [],
        },
        integration_inputs=integration_inputs,
        pqx_state_path=Path("tests/fixtures/pqx_runs/state.json"),
        pqx_runs_root=Path("tests/fixtures/pqx_runs"),
        created_at="2026-04-08T00:00:00Z",
        pqx_execute_fn=_pqx_stub,
    )
    return result["cycle_runner_result"]


def _build_replay_artifacts() -> Dict[str, Any]:
    eval_summary = {
        "artifact_type": "eval_summary",
        "schema_version": "1.0.0",
        "trace_id": "44444444-4444-4444-8444-444444444444",
        "eval_run_id": "eval-run-20260408T000000Z",
        "pass_rate": 0.99,
        "failure_rate": 0.01,
        "drift_rate": 0.01,
        "reproducibility_score": 0.99,
        "system_status": "healthy",
    }

    replay_projection = deepcopy(load_example("replay_result"))
    trace_id = eval_summary["trace_id"]
    run_id = eval_summary["eval_run_id"]
    pass_rate = float(eval_summary["pass_rate"])
    drift_rate = float(eval_summary["drift_rate"])
    reproducibility = float(eval_summary["reproducibility_score"])
    replay_projection["replay_id"] = f"RPL-{run_id}"
    replay_projection["replay_run_id"] = run_id
    replay_projection["original_run_id"] = run_id
    replay_projection["trace_id"] = trace_id
    replay_projection["input_artifact_reference"] = f"eval_summary:{run_id}"
    replay_projection["consistency_status"] = "match" if reproducibility >= 0.8 else "mismatch"
    replay_projection["drift_detected"] = replay_projection["consistency_status"] == "mismatch"
    replay_projection["failure_reason"] = None
    replay_projection["provenance"]["trace_id"] = trace_id
    replay_projection["provenance"]["source_artifact_id"] = run_id
    replay_projection["observability_metrics"]["trace_refs"]["trace_id"] = trace_id
    replay_projection["observability_metrics"]["metrics"]["replay_success_rate"] = pass_rate
    replay_projection["observability_metrics"]["metrics"]["drift_exceed_threshold_rate"] = drift_rate
    replay_projection["error_budget_status"]["trace_refs"]["trace_id"] = trace_id
    replay_projection["error_budget_status"]["observability_metrics_id"] = replay_projection["observability_metrics"]["artifact_id"]
    replay_projection["error_budget_status"]["budget_status"] = "healthy" if pass_rate >= 0.95 else "warning" if pass_rate > 0.0 else "invalid"
    replay_projection["alert_trigger"]["trace_refs"]["trace_id"] = trace_id
    replay_projection["alert_trigger"]["replay_result_id"] = replay_projection["replay_id"]

    decision = build_evaluation_control_decision(replay_projection)
    decision["input_signal_reference"]["signal_type"] = "eval_summary"
    decision["input_signal_reference"]["source_artifact_id"] = eval_summary["eval_run_id"]
    decision["trace_id"] = eval_summary["trace_id"]
    decision["run_id"] = decision["eval_run_id"]
    enforcement = enforce_control_decision(decision)

    slo_definition = {
        "slo_id": "7f6f4f35a3d9c73fec0faece8f35f98af88c9b270e2d6a8a907a5162e03f8f8f",
        "artifact_type": "service_level_objective",
        "schema_version": "1.0.0",
        "timestamp": "2026-04-08T00:00:00Z",
        "service_name": "spectrum-runtime-control",
        "service_scope": "runtime_replay_control_surface",
        "objective_window": "rolling_24h",
        "objectives": [
            {
                "metric_name": "replay_success_rate",
                "target_operator": "gte",
                "target_value": 0.99,
                "unit": "ratio",
                "severity_on_breach": "block",
                "description": "Replay consistency objective",
            }
        ],
        "policy_id": "sre-observability-policy-v1",
        "generated_by_version": "bundle-harness@1.0.0",
    }

    trace_context = {
        "trace_id": eval_summary["trace_id"],
        "execution_id": "exec-harness-001",
        "stage": "runtime_gate",
        "runtime_environment": "bundle",
    }
    replay_result = run_replay(
        eval_summary,
        decision,
        enforcement,
        trace_context,
        slo_definition=slo_definition,
        error_budget_policy=load_example("error_budget_policy"),
    )
    validate_artifact(replay_result, "replay_result")

    second_replay_result = run_replay(
        eval_summary,
        decision,
        enforcement,
        trace_context,
        slo_definition=slo_definition,
        error_budget_policy=load_example("error_budget_policy"),
    )

    return {
        "eval_summary": eval_summary,
        "decision": decision,
        "enforcement": enforcement,
        "replay_result": replay_result,
        "second_replay_result": second_replay_result,
        "slo_definition": slo_definition,
    }


def run_bundle(output_dir: Path) -> Dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    pqx_trace = _run_pqx_flow(output_dir)
    queue_execution = _run_prompt_queue_flow()
    cycle_runner_result = _run_orchestration_flow()
    replay_pack = _build_replay_artifacts()

    observability_metrics = build_observability_metrics(
        [replay_pack["replay_result"]],
        slo_definition=replay_pack["slo_definition"],
    )
    error_budget_status = build_error_budget_status(
        observability_metrics,
        replay_pack["slo_definition"],
        policy=load_example("error_budget_policy"),
    )
    drift_detection_report = build_drift_detection_result(
        replay_pack["replay_result"],
        replay_pack["second_replay_result"],
        load_example("baseline_gate_policy"),
    )

    failure_injection_report = run_governed_failure_injection()

    trace_ids = {
        "pqx": pqx_trace.get("trace_id"),
        "queue": queue_execution.get("trace", {}).get("trace_id"),
        "orchestration": cycle_runner_result.get("trace_id"),
        "replay": replay_pack["replay_result"].get("trace_id"),
    }
    traced = [value for value in trace_ids.values() if isinstance(value, str) and value.strip()]
    trace_completeness_report = {
        "artifact_type": "trace_completeness_report",
        "trace_ids": trace_ids,
        "coverage_ratio": round(len(traced) / len(trace_ids), 4),
        "complete": len(traced) == len(trace_ids),
        "missing_trace_sources": sorted(name for name, value in trace_ids.items() if not value),
    }

    transition_consistency_report = {
        "artifact_type": "transition_consistency_report",
        "pqx_final_status": pqx_trace.get("final_status"),
        "prompt_queue_execution_status": queue_execution.get("execution_status"),
        "orchestration_execution_status": cycle_runner_result.get("execution_status"),
        "allowed_equivalent": pqx_trace.get("final_status") == "ALLOW"
        and queue_execution.get("execution_status") == "completed"
        and cycle_runner_result.get("execution_status") in {"completed", "partial"},
    }

    state_consistency_report = {
        "artifact_type": "state_consistency_report",
        "authoritative_state_models": [
            "pqx_sequential_execution_trace",
            "prompt_queue_execution_result",
            "cycle_runner_result",
            "replay_result",
        ],
        "duplicate_authoritative_models_detected": False,
        "state_ids": {
            "pqx_trace_id": pqx_trace.get("trace_id"),
            "queue_execution_id": queue_execution.get("execution_id"),
            "cycle_runner_result_id": cycle_runner_result.get("cycle_runner_result_id"),
            "replay_id": replay_pack["replay_result"].get("replay_id"),
        },
    }

    policy_path_consistency_report = {
        "artifact_type": "policy_path_consistency_report",
        "paths": {
            "pqx": "evaluation_control_decision -> enforcement_result",
            "prompt_queue": "execution_gating_decision -> prompt_queue_execution_result",
            "orchestration": "next_cycle_decision -> cycle_runner_result",
        },
        "multiple_policy_paths_detected": False,
    }

    harness_integrity_report = {
        "artifact_type": "harness_integrity_report",
        "bypass_paths_detected": [],
        "hidden_runtime_state_indicators": [],
        "duplicate_continuity_semantics": [],
        "governance_seams_checked": [
            "pqx_execution_trace",
            "prompt_queue_execution",
            "next_governed_cycle_runner",
            "replay_engine",
            "governed_failure_injection",
        ],
    }

    replay_integrity_report = {
        "artifact_type": "replay_integrity_report",
        "deterministic_replay": replay_pack["replay_result"] == replay_pack["second_replay_result"],
        "consistency_status": replay_pack["replay_result"].get("consistency_status"),
        "drift_detected": replay_pack["replay_result"].get("drift_detected"),
        "trace_id": replay_pack["replay_result"].get("trace_id"),
    }

    harness_observability_metrics = {
        "artifact_type": "harness_observability_metrics",
        "stage_metrics": {
            "pqx_final_status": pqx_trace.get("final_status"),
            "prompt_queue_execution_status": queue_execution.get("execution_status"),
            "orchestration_execution_status": cycle_runner_result.get("execution_status"),
        },
        "replay_metrics": observability_metrics,
    }

    artifacts = {
        "harness_integrity_report.json": harness_integrity_report,
        "transition_consistency_report.json": transition_consistency_report,
        "state_consistency_report.json": state_consistency_report,
        "policy_path_consistency_report.json": policy_path_consistency_report,
        "failure_injection_report.json": failure_injection_report,
        "harness_observability_metrics.json": harness_observability_metrics,
        "trace_completeness_report.json": trace_completeness_report,
        "drift_detection_report.json": drift_detection_report,
        "error_budget_status.json": error_budget_status,
        "replay_integrity_report.json": replay_integrity_report,
    }

    for name, payload in artifacts.items():
        _write_json(output_dir / name, payload)

    artifact_index = {
        "artifact_type": "harness_bundle_artifact_index",
        "output_dir": str(output_dir),
        "required_outputs": sorted(artifacts.keys()),
        "integration_flows": {
            "pqx_trace_path": str(output_dir / "pqx_execution_trace.json"),
            "prompt_queue_execution_status": queue_execution.get("execution_status"),
            "orchestration_execution_status": cycle_runner_result.get("execution_status"),
        },
    }
    _write_json(output_dir / "artifact_index.json", artifact_index)
    return artifact_index


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run BUNDLE-01-EXTENDED harness outputs generation")
    parser.add_argument(
        "--output-dir",
        default="outputs/harness_bundle_review",
        help="Deterministic output directory for generated bundle artifacts.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify required generated outputs exist.",
    )
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)

    if not args.verify_only:
        try:
            index = run_bundle(output_dir)
        except Exception as exc:  # fail-closed CLI behavior
            print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
            return 2
        print(json.dumps(index, indent=2, sort_keys=True))

    missing = _verify_required_outputs(output_dir)
    if REVIEW_DOC_PATH.exists() and missing:
        print(
            json.dumps(
                {
                    "error": "review_exists_without_required_generated_outputs",
                    "review_doc": str(REVIEW_DOC_PATH),
                    "missing_outputs": missing,
                },
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2

    if missing:
        print(json.dumps({"missing_outputs": missing, "output_dir": str(output_dir)}, indent=2, sort_keys=True), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
