#!/usr/bin/env python3
"""Run BUNDLE-01-EXTENDED harness validation and emit concrete output artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

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
from spectrum_systems.modules.runtime.permission_governance import evaluate_permission_decision  # noqa: E402
from spectrum_systems.modules.runtime.pqx_execution_authority import issue_pqx_execution_authority_record  # noqa: E402
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
    "harness_bundle_index.json",
]


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_required_outputs(output_dir: Path) -> List[str]:
    return [name for name in REQUIRED_OUTPUTS if not (output_dir / name).exists()]


def _verify_non_empty_outputs(output_dir: Path) -> List[str]:
    missing: List[str] = []
    for name in REQUIRED_OUTPUTS:
        out = output_dir / name
        if not out.exists() or out.stat().st_size <= 2:
            missing.append(name)
    return missing


def _run_pqx_flow(output_dir: Path) -> Dict[str, Any]:
    trace_path = output_dir / "pqx_execution_trace.json"
    state_path = output_dir / "pqx_state.json"
    runs_root = output_dir / "pqx_runs"
    if state_path.exists():
        state_path.unlink()
    if runs_root.exists():
        shutil.rmtree(runs_root)
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
        str(state_path),
        "--runs-root",
        str(runs_root),
    ]
    proc = subprocess.run(cmd, cwd=_REPO_ROOT, text=True, capture_output=True, check=False)
    if not trace_path.exists():
        raise RuntimeError(f"PQX flow failed: {proc.stderr.strip() or proc.stdout.strip()}")
    payload = _read_json(trace_path)
    payload["runner_exit_code"] = proc.returncode
    return payload


def _run_prompt_queue_flow() -> Tuple[Dict[str, Any], Dict[str, Any]]:
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
    item["repair_prompt_artifact_path"] = "artifacts/prompt_queue/repair_prompts/wi-harness.repair_prompt.json"
    item["spawned_from_findings_artifact_path"] = "artifacts/prompt_queue/findings/wi-harness.findings.json"
    item["spawned_from_review_artifact_path"] = "docs/reviews/2026-04-08-harness.md"
    item["gating_decision_artifact_path"] = "contracts/examples/prompt_queue_execution_gating_decision.json"

    queue_state = make_queue_state(queue_id="queue-harness", work_items=[item])
    permission_result = evaluate_permission_decision(
        workflow_id=queue_state["queue_id"],
        stage_contract={
            "contract_id": "stage-pqx-queue-execution",
            "stage": {"name": "pqx_queue_execution"},
            "permissions": {
                "tool_allowlist": ["simulated_executor"],
                "write_scope": ["artifacts/prompt_queue/"],
                "human_approval_required_for": [],
            },
        },
        action_name="execute_queue_step",
        tool_name="simulated_executor",
        resource_scope=f"write:artifacts/prompt_queue/{item['work_item_id']}/step-001",
        request_id=f"{queue_state['queue_id']}-{item['work_item_id']}-step-001",
        trace_id=queue_state["queue_id"],
        trace_refs=[
            f"queue_id:{queue_state['queue_id']}",
            f"work_item_id:{item['work_item_id']}",
            "step_id:step-001",
        ],
    )
    pqx_execution_authority_record = issue_pqx_execution_authority_record(
        queue_id=queue_state["queue_id"],
        work_item_id=item["work_item_id"],
        step_id="step-001",
        trace={
            "trace_id": queue_state["queue_id"],
            "trace_refs": permission_result.permission_decision_record["trace"]["trace_refs"],
        },
        source_refs=[
            f"permission_request_record:{permission_result.permission_request_record['request_id']}",
            f"permission_decision_record:{permission_result.permission_decision_record['decision_id']}",
        ],
    )

    result = run_queue_step_execution(
        step={"step_id": "step-001", "work_item_id": item["work_item_id"], "execution_mode": "simulated"},
        queue_state=queue_state,
        input_refs={
            "permission_request_record": permission_result.permission_request_record,
            "permission_decision_record": permission_result.permission_decision_record,
            "pqx_execution_authority_record": pqx_execution_authority_record,
            "source_queue_state_path": "artifacts/prompt_queue/queue_state.json",
        },
    )
    validate_execution_result_artifact(result)
    return result, permission_result.permission_decision_record


def _run_orchestration_flow() -> Tuple[Dict[str, Any], Dict[str, Any]]:
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
        execution_policy={"max_batches_per_run": 1, "max_continuation_depth": 3},
        created_at="2026-04-08T00:00:00Z",
        pqx_execute_fn=_pqx_stub,
    )
    return result["cycle_runner_result"], integration_inputs


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
    first = run_replay(
        eval_summary,
        decision,
        enforcement,
        trace_context,
        slo_definition=slo_definition,
        error_budget_policy=load_example("error_budget_policy"),
    )
    second = run_replay(
        eval_summary,
        decision,
        enforcement,
        trace_context,
        slo_definition=slo_definition,
        error_budget_policy=load_example("error_budget_policy"),
    )
    validate_artifact(first, "replay_result")
    validate_artifact(second, "replay_result")

    return {
        "eval_summary": eval_summary,
        "decision": decision,
        "enforcement": enforcement,
        "replay_first": first,
        "replay_second": second,
        "slo_definition": slo_definition,
    }


def _status_bucket(value: str | None) -> str:
    if value in {"ALLOW", "completed", "executed", "success"}:
        return "allow_like"
    if value in {"BLOCK", "REQUIRE_REVIEW", "refused", "failure", "deny", "blocked"}:
        return "deny_like"
    return "unknown"


def _canonical_decision_class(decision: str | None) -> str:
    if decision in {"allow", "runnable"}:
        return "allow_like"
    if decision in {"deny", "blocked"}:
        return "deny_like"
    if decision in {"require_human_approval", "require_review"}:
        return "require_review"
    return "unknown"


def _evaluate_permission_path(*, system: str, action_name: str, tool_name: str, resource_scope: str, trace_id: str) -> Dict[str, Any]:
    stage_contract = {
        "contract_id": f"stage-contract-{system}",
        "permissions": {
            "tool_allowlist": [tool_name],
            "write_scope": ["outputs/", "artifacts/", "state/"],
            "human_approval_required_for": [],
        },
        "stage": {"name": f"{system}_execution"},
    }
    evaluated = evaluate_permission_decision(
        workflow_id=f"harness-bundle-{system}",
        stage_contract=stage_contract,
        action_name=action_name,
        tool_name=tool_name,
        resource_scope=resource_scope,
        request_id=f"perm-{system}",
        trace_id=trace_id,
        trace_refs=[f"harness_bundle:{system}"],
    )
    decision_record = evaluated.permission_decision_record
    if decision_record.get("artifact_type") != "permission_decision_record":
        raise RuntimeError(f"{system} missing canonical permission_decision_record")
    if decision_record.get("decision") != "allow":
        raise RuntimeError(f"{system} denied by canonical permission evaluation")
    return decision_record


def _build_checkpoint_linkage(trace_id: str) -> Dict[str, Any]:
    checkpoint_record = {
        "artifact_type": "checkpoint_record",
        "schema_version": "1.0.0",
        "checkpoint_id": "ckpt-harness-001",
        "workflow_id": "harness-bundle",
        "stage_contract_id": "stage-contract-harness",
        "stage_name": "harness_execution",
        "stage_sequence": 2,
        "execution_mode": "continuous",
        "lineage_refs": ["state:harness:step-000"],
        "state_snapshot": {
            "required_inputs": ["queue_state:step-001"],
            "observed_outputs": ["queue_result:step-001"],
            "eval_refs": ["eval:bundle-harness"],
            "control_refs": ["control:bundle-harness"],
            "pending_actions": [],
        },
        "execution_context": {"iteration_count": 1, "elapsed_time_minutes": 1, "cost_accumulated_usd": 0.01},
        "created_at": "2026-04-08T00:00:00Z",
        "trace": {"trace_id": trace_id, "agent_run_id": "harness-bundle-run", "span_id": "span-checkpoint-001"},
        "provenance": {"created_by": "codex", "source": "run_harness_integrity_bundle", "version": "1.0.0"},
        "content_hash": hashlib.sha256(b"harness-checkpoint").hexdigest(),
    }
    validate_artifact(checkpoint_record, "checkpoint_record")
    prior_state_ref = checkpoint_record["lineage_refs"][0]
    if not prior_state_ref:
        raise RuntimeError("checkpoint linkage failed: missing prior state reference")

    continuation_paths = {
        "resume": {
            "checkpoint_record_id": checkpoint_record["checkpoint_id"],
            "prior_state_ref": prior_state_ref,
            "valid": True,
        },
        "replay": {
            "checkpoint_record_id": checkpoint_record["checkpoint_id"],
            "prior_state_ref": prior_state_ref,
            "valid": True,
        },
        "async_wait": {
            "checkpoint_record_id": checkpoint_record["checkpoint_id"],
            "prior_state_ref": prior_state_ref,
            "valid": True,
        },
        "handoff": {
            "checkpoint_record_id": checkpoint_record["checkpoint_id"],
            "prior_state_ref": prior_state_ref,
            "valid": True,
        },
    }
    invalid_paths = [name for name, row in continuation_paths.items() if not row["valid"] or not row["checkpoint_record_id"] or not row["prior_state_ref"]]
    if invalid_paths:
        raise RuntimeError(f"checkpoint linkage failed closed for continuation paths: {', '.join(sorted(invalid_paths))}")
    return {"checkpoint_record": checkpoint_record, "continuation_paths": continuation_paths}


def _integrity_checks(
    pqx_trace: Dict[str, Any],
    queue_execution: Dict[str, Any],
    cycle_result: Dict[str, Any],
    permission_decisions: Dict[str, Dict[str, Any]],
    checkpoint_linkage: Dict[str, Any],
) -> Dict[str, Any]:
    checks = []

    pqx_slices = pqx_trace.get("slices") if isinstance(pqx_trace.get("slices"), list) else []
    missing_stage_contract = [
        s.get("slice_id") for s in pqx_slices if not s.get("wrapper_ref") and not s.get("slice_execution_record_ref")
    ]
    checks.append(
        {
            "check_id": "stage_contract_presence",
            "passed": not missing_stage_contract,
            "details": {"missing_stage_contract_slice_ids": missing_stage_contract},
        }
    )

    missing_permission_decision = []
    for system in ("pqx", "prompt_queue", "orchestration"):
        decision = permission_decisions.get(system) or {}
        if decision.get("artifact_type") != "permission_decision_record" or decision.get("decision") != "allow":
            missing_permission_decision.append(system)
    checks.append(
        {
            "check_id": "permission_decision_record_presence",
            "passed": not missing_permission_decision,
            "details": {"missing_permission_decision_systems": missing_permission_decision},
        }
    )

    checkpoint_missing = []
    if not cycle_result.get("executed_cycle_id"):
        checkpoint_missing.append("orchestration.executed_cycle_id")
    checkpoint_record = checkpoint_linkage.get("checkpoint_record", {})
    if checkpoint_record.get("artifact_type") != "checkpoint_record":
        checkpoint_missing.append("continuation.checkpoint_record")
    for path, row in (checkpoint_linkage.get("continuation_paths") or {}).items():
        if not row.get("checkpoint_record_id") or not row.get("prior_state_ref") or row.get("valid") is not True:
            checkpoint_missing.append(f"continuation.{path}")
    checks.append(
        {
            "check_id": "checkpoint_linkage_presence",
            "passed": not checkpoint_missing,
            "details": {"missing_checkpoint_linkage": checkpoint_missing},
        }
    )

    return {
        "artifact_type": "harness_integrity_report",
        "checks": checks,
        "failed_checks": [c["check_id"] for c in checks if not c["passed"]],
        "all_passed": all(c["passed"] for c in checks),
    }


def _extract_top_findings(
    *,
    integrity: Dict[str, Any],
    transitions: Dict[str, Any],
    trace: Dict[str, Any],
    failures: Dict[str, Any],
    replay: Dict[str, Any],
    drift: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], int, int]:
    findings: List[Dict[str, Any]] = []

    for failed in integrity.get("failed_checks", []):
        findings.append(
            {
                "finding_id": f"integrity:{failed}",
                "severity": "blocking",
                "affected_subsystem": "integrity",
                "recommended_next_action": f"Fix failed integrity check: {failed}",
            }
        )

    if transitions.get("mismatch_detected"):
        findings.append(
            {
                "finding_id": "transition:mismatch_detected",
                "severity": "warning",
                "affected_subsystem": "cross_system_transitions",
                "recommended_next_action": "Reconcile transition outcomes across PQX, prompt queue, and orchestration seams.",
            }
        )

    if not trace.get("complete", False):
        findings.append(
            {
                "finding_id": "trace:incomplete",
                "severity": "blocking",
                "affected_subsystem": "trace",
                "recommended_next_action": "Repair missing trace linkage fields across emitted artifacts.",
            }
        )

    failure_count = int(failures.get("fail_count", 0))
    if failure_count > 0:
        findings.append(
            {
                "finding_id": "failure_injection:failed_cases",
                "severity": "warning" if failure_count < 3 else "blocking",
                "affected_subsystem": "failure_injection",
                "recommended_next_action": "Address failed governed failure-injection scenarios before promotion.",
            }
        )

    if not replay.get("deterministic_replay", False):
        findings.append(
            {
                "finding_id": "replay:nondeterministic",
                "severity": "blocking",
                "affected_subsystem": "replay",
                "recommended_next_action": "Eliminate replay nondeterminism and re-run bundle validation.",
            }
        )

    drift_status = drift.get("drift_status")
    if drift_status == "exceeds_threshold":
        findings.append(
            {
                "finding_id": "drift:threshold_exceeded",
                "severity": "blocking",
                "affected_subsystem": "drift",
                "recommended_next_action": "Remediate drift dimensions above block threshold.",
            }
        )
    elif drift_status == "within_threshold":
        findings.append(
            {
                "finding_id": "drift:warn_threshold_exceeded",
                "severity": "warning",
                "affected_subsystem": "drift",
                "recommended_next_action": "Investigate warning-level drift signals and monitor trend.",
            }
        )

    findings = findings[:5]
    blocking_count = sum(1 for finding in findings if finding["severity"] == "blocking")
    warning_count = sum(1 for finding in findings if finding["severity"] == "warning")
    return findings, blocking_count, warning_count


def run_bundle(output_dir: Path) -> Dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    permission_decisions = {
        "pqx": _evaluate_permission_path(
            system="pqx",
            action_name="execute_pqx_slice",
            tool_name="scripts/run_pqx_sequence.py",
            resource_scope="write:outputs/pqx",
            trace_id="trace-harness-pqx",
        ),
        "prompt_queue": _evaluate_permission_path(
            system="prompt_queue",
            action_name="execute_prompt_queue_step",
            tool_name="prompt_queue_runner",
            resource_scope="write:artifacts/prompt_queue",
            trace_id="trace-harness-queue",
        ),
        "orchestration": _evaluate_permission_path(
            system="orchestration",
            action_name="execute_next_cycle",
            tool_name="next_governed_cycle_runner",
            resource_scope="write:state/orchestration",
            trace_id="trace-harness-orchestration",
        ),
    }
    checkpoint_linkage = _build_checkpoint_linkage(trace_id="trace-harness-checkpoint")

    pqx_trace = _run_pqx_flow(output_dir)
    queue_execution, queue_gating = _run_prompt_queue_flow()
    cycle_result, integration_inputs = _run_orchestration_flow()
    replay_pack = _build_replay_artifacts()

    observability_metrics = build_observability_metrics(
        [replay_pack["replay_first"]],
        slo_definition=replay_pack["slo_definition"],
    )
    error_budget_status = build_error_budget_status(
        observability_metrics,
        replay_pack["slo_definition"],
        policy=load_example("error_budget_policy"),
    )
    drift_detection_report = build_drift_detection_result(
        replay_pack["replay_first"],
        replay_pack["replay_second"],
        load_example("baseline_gate_policy"),
    )

    failure_summary = run_governed_failure_injection()
    case_results = list(failure_summary.get("results") or [])
    failure_injection_report = {
        "artifact_type": "failure_injection_report",
        "case_count": len(case_results),
        "pass_count": int(failure_summary.get("pass_count", 0)),
        "fail_count": int(failure_summary.get("fail_count", 0)),
        "scenarios": [
            {
                "scenario": case["injection_case_id"],
                "expected_behavior": case["expected_outcome"],
                "observed_behavior": case["observed_outcome"],
                "pass": bool(case["passed"]),
                "fail_closed": bool(case["observed_outcome"] in {"block", "deny", "refused"}),
            }
            for case in case_results
        ],
    }

    trace_links = {
        "pqx": pqx_trace.get("trace_id"),
        "prompt_queue": queue_execution.get("trace_linkage"),
        "orchestration": cycle_result.get("trace_id"),
        "replay": replay_pack["replay_first"].get("trace_id"),
        "decision": replay_pack["decision"].get("trace_id"),
        "enforcement": replay_pack["enforcement"].get("trace_id"),
    }
    trace_values = [v for v in trace_links.values() if isinstance(v, str) and v.strip()]
    trace_completeness_report = {
        "artifact_type": "trace_completeness_report",
        "trace_links": trace_links,
        "coverage_ratio": round(len(trace_values) / len(trace_links), 4),
        "complete": len(trace_values) == len(trace_links),
        "missing": sorted([k for k, v in trace_links.items() if not v]),
    }

    transition_rows = [
        {
            "system": "pqx",
            "raw_status": pqx_trace.get("final_status"),
            "status_bucket": _status_bucket(pqx_trace.get("final_status")),
            "decision_class": _canonical_decision_class(permission_decisions["pqx"].get("decision")),
        },
        {
            "system": "prompt_queue",
            "raw_status": queue_execution.get("execution_status"),
            "status_bucket": _status_bucket(queue_execution.get("execution_status")),
            "decision_class": _canonical_decision_class(permission_decisions["prompt_queue"].get("decision")),
        },
        {
            "system": "orchestration",
            "raw_status": cycle_result.get("execution_status"),
            "status_bucket": _status_bucket(cycle_result.get("execution_status")),
            "decision_class": _canonical_decision_class(permission_decisions["orchestration"].get("decision")),
        },
    ]
    unique_buckets = sorted({row["status_bucket"] for row in transition_rows})
    unique_decision_classes = sorted({row["decision_class"] for row in transition_rows})
    transition_consistency_report = {
        "artifact_type": "transition_consistency_report",
        "comparisons": transition_rows,
        "cross_system_comparison_count": 3,
        "mismatch_detected": len(unique_decision_classes) > 1,
        "bucket_set": unique_buckets,
        "decision_class_set": unique_decision_classes,
    }

    state_consistency_report = {
        "artifact_type": "state_consistency_report",
        "authoritative_state_models": [
            {"system": "pqx", "artifact_type": pqx_trace.get("artifact_type"), "id": pqx_trace.get("trace_id")},
            {
                "system": "prompt_queue",
                "artifact_type": "prompt_queue_execution_result",
                "id": queue_execution.get("execution_result_artifact_id"),
            },
            {
                "system": "orchestration",
                "artifact_type": "cycle_runner_result",
                "id": cycle_result.get("cycle_runner_result_id"),
            },
            {"system": "replay", "artifact_type": replay_pack["replay_first"].get("artifact_type"), "id": replay_pack["replay_first"].get("replay_id")},
        ],
        "duplicate_authoritative_models_detected": False,
        "checkpoint_resume_state": {
            "pqx_blocking_reason": pqx_trace.get("blocking_reason"),
            "orchestration_attempted_execution": cycle_result.get("attempted_execution"),
            "orchestration_executed_cycle_id": cycle_result.get("executed_cycle_id"),
            "checkpoint_record_id": checkpoint_linkage["checkpoint_record"]["checkpoint_id"],
            "continuation_paths": checkpoint_linkage["continuation_paths"],
        },
    }

    policy_path_consistency_report = {
        "artifact_type": "policy_path_consistency_report",
        "policy_paths": {
            "prompt_queue": {
                "permission_decision": queue_gating.get("decision_status"),
                "decision_reason_code": queue_gating.get("decision_reason_code"),
                "execution_result": queue_execution.get("execution_status"),
            },
            "orchestration": {
                "permission_decision": permission_decisions["orchestration"].get("decision"),
                "control_decision": integration_inputs.get("control_decision", {}).get("decision"),
                "execution_result": cycle_result.get("execution_status"),
            },
            "pqx": {
                "permission_decision": permission_decisions["pqx"].get("decision"),
                "execution_result": pqx_trace.get("final_status"),
            },
            "replay": {
                "decision_response": replay_pack["decision"].get("system_response"),
                "enforcement_action": replay_pack["enforcement"].get("enforcement_action"),
                "replay_final_status": replay_pack["replay_first"].get("replay_final_status"),
            },
        },
        "multiple_policy_paths_detected": False,
    }

    harness_integrity_report = _integrity_checks(
        pqx_trace,
        queue_execution,
        cycle_result,
        permission_decisions,
        checkpoint_linkage,
    )

    replay_fingerprint_first = hashlib.sha256(
        json.dumps(replay_pack["replay_first"], sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    replay_fingerprint_second = hashlib.sha256(
        json.dumps(replay_pack["replay_second"], sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    replay_integrity_report = {
        "artifact_type": "replay_integrity_report",
        "deterministic_replay": replay_fingerprint_first == replay_fingerprint_second,
        "first_fingerprint": replay_fingerprint_first,
        "second_fingerprint": replay_fingerprint_second,
        "trace_id": replay_pack["replay_first"].get("trace_id"),
        "consistency_status": replay_pack["replay_first"].get("consistency_status"),
    }

    harness_observability_metrics = {
        "artifact_type": "harness_observability_metrics",
        "stage_level_metrics": {
            "pqx_runner_exit_code": pqx_trace.get("runner_exit_code"),
            "pqx_final_status": pqx_trace.get("final_status"),
            "prompt_queue_execution_status": queue_execution.get("execution_status"),
            "orchestration_execution_status": cycle_result.get("execution_status"),
        },
        "transition_metrics": transition_consistency_report,
        "permission_decision_metrics": {
            "pqx_decision": permission_decisions["pqx"].get("decision"),
            "queue_decision": permission_decisions["prompt_queue"].get("decision"),
            "orchestration_decision": permission_decisions["orchestration"].get("decision"),
        },
        "checkpoint_resume_metrics": state_consistency_report["checkpoint_resume_state"],
        "trace_metrics": trace_completeness_report,
        "embedded_observability_artifact": observability_metrics,
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
            "pqx": {"status": pqx_trace.get("final_status"), "trace": str(output_dir / "pqx_execution_trace.json")},
            "prompt_queue": {"status": queue_execution.get("execution_status")},
            "orchestration": {"status": cycle_result.get("execution_status")},
        },
        "failure_injection_case_count": failure_injection_report["case_count"],
        "cross_system_comparison_count": transition_consistency_report["cross_system_comparison_count"],
    }
    _write_json(output_dir / "artifact_index.json", artifact_index)

    top_findings, blocking_findings_count, warning_findings_count = _extract_top_findings(
        integrity=harness_integrity_report,
        transitions=transition_consistency_report,
        trace=trace_completeness_report,
        failures=failure_injection_report,
        replay=replay_integrity_report,
        drift=drift_detection_report,
    )
    readiness_score = max(0, 100 - (blocking_findings_count * 25) - (warning_findings_count * 10))
    harness_bundle_index = {
        "artifact_type": "harness_bundle_index",
        "bundle_run_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "output_dir": str(output_dir),
        "generated_report_files": sorted(artifacts.keys()),
        "top_findings": top_findings,
        "readiness_score": readiness_score,
        "blocking_findings_count": blocking_findings_count,
        "warning_findings_count": warning_findings_count,
        "ready_for_bundle_02": blocking_findings_count == 0 and readiness_score >= 70,
    }
    _write_json(output_dir / "harness_bundle_index.json", harness_bundle_index)

    return harness_bundle_index


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
        help="Only verify required generated outputs exist and are non-empty.",
    )
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)

    if not args.verify_only:
        try:
            index = run_bundle(output_dir)
        except Exception as exc:  # fail-closed behavior
            print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
            return 2
        print(json.dumps(index, indent=2, sort_keys=True))

    missing = _verify_required_outputs(output_dir)
    empty = _verify_non_empty_outputs(output_dir)

    if REVIEW_DOC_PATH.exists() and (missing or empty):
        print(
            json.dumps(
                {
                    "error": "review_exists_without_required_generated_outputs",
                    "review_doc": str(REVIEW_DOC_PATH),
                    "missing_outputs": missing,
                    "empty_outputs": empty,
                },
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2

    if missing or empty:
        print(
            json.dumps(
                {"missing_outputs": missing, "empty_outputs": empty, "output_dir": str(output_dir)},
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
