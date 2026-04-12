"""SEL orchestration runner for real CDE artifact consumption and SEL chain emission."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.sel_enforcement_foundation import (
    SELEnforcementError,
    build_enforcement_action_record,
    build_enforcement_bundle,
    build_enforcement_conflict_record,
    build_enforcement_effectiveness_record,
    build_enforcement_readiness,
    build_enforcement_result_record,
    evaluate_enforcement_action,
    validate_enforcement_replay,
    verify_sel_boundary_inputs,
)


class SELOrchestrationRunnerError(ValueError):
    """Raised when SEL orchestration fails closed."""


_REQUIRED_INPUT_FILES = {
    "continuation_decision_record.json": "continuation_decision_record",
    "decision_bundle.json": "decision_bundle",
    "decision_evidence_pack.json": "decision_evidence_pack",
}


_REQUIRED_CHAIN = (
    "enforcement_action_record",
    "enforcement_eval_result",
    "enforcement_readiness_record",
    "enforcement_conflict_record",
    "enforcement_result_record",
    "enforcement_bundle",
)


def _digest(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SELOrchestrationRunnerError(f"failed to read {path}: {exc}") from exc


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_sel_orchestration(*, cde_bundle_dir: Path, output_dir: Path, observed_outcome: str | None = None, observed_outcome_ref: str | None = None) -> dict[str, Any]:
    loaded: dict[str, dict[str, Any]] = {}
    for filename, artifact_type in _REQUIRED_INPUT_FILES.items():
        file_path = cde_bundle_dir / filename
        if not file_path.exists():
            raise SELOrchestrationRunnerError(f"missing required CDE input: {file_path}")
        payload = _load_json(file_path)
        validate_artifact(payload, artifact_type)
        loaded[artifact_type] = payload

    decision_record = loaded["continuation_decision_record"]
    decision_bundle = loaded["decision_bundle"]
    evidence_bundle = loaded["decision_evidence_pack"]

    if decision_record.get("trace_id") != decision_bundle.get("trace_id") or decision_record.get("trace_id") != evidence_bundle.get("trace_id"):
        raise SELOrchestrationRunnerError("trace_id mismatch across CDE artifacts")

    try:
        verify_sel_boundary_inputs(
            decision_record=decision_record,
            decision_bundle=decision_bundle,
            evidence_bundle=evidence_bundle,
        )
        action_record = build_enforcement_action_record(
            decision_record=decision_record,
            decision_bundle=decision_bundle,
            evidence_refs=list(evidence_bundle.get("evidence_refs", [])) or [f"decision_evidence_pack:{evidence_bundle['evidence_pack_id']}"],
        )
        eval_result = evaluate_enforcement_action(
            decision_record=decision_record,
            action_record=action_record,
            evidence_bundle=evidence_bundle,
        )
        readiness_record = build_enforcement_readiness(
            decision_record=decision_record,
            action_record=action_record,
            eval_result=eval_result,
        )
        conflict_record = build_enforcement_conflict_record(
            decision_record=decision_record,
            action_record=action_record,
            eval_result=eval_result,
        )
        result_record = build_enforcement_result_record(
            decision_record=decision_record,
            action_record=action_record,
            eval_result=eval_result,
            readiness_record=readiness_record,
            conflict_record=conflict_record,
        )
        enforcement_bundle = build_enforcement_bundle(
            action_record=action_record,
            result_record=result_record,
            eval_result=eval_result,
            readiness_record=readiness_record,
            conflict_record=conflict_record,
        )
    except (SELEnforcementError, KeyError) as exc:
        raise SELOrchestrationRunnerError(f"SEL orchestration failed closed: {exc}") from exc

    artifacts = {
        "enforcement_action_record": action_record,
        "enforcement_eval_result": eval_result,
        "enforcement_readiness_record": readiness_record,
        "enforcement_conflict_record": conflict_record,
        "enforcement_result_record": result_record,
        "enforcement_bundle": enforcement_bundle,
    }

    if observed_outcome is not None and observed_outcome_ref is not None:
        artifacts["enforcement_effectiveness_record"] = build_enforcement_effectiveness_record(
            decision_record=decision_record,
            action_record=action_record,
            result_record=result_record,
            observed_outcome=observed_outcome,
            observed_outcome_ref=observed_outcome_ref,
        )

    for artifact_type, artifact in artifacts.items():
        _write_json(output_dir / f"{artifact_type}.json", artifact)

    replay = validate_enforcement_replay(
        decision_record=decision_record,
        action_record=action_record,
        first_result=result_record,
        replay_result=copy.deepcopy(result_record),
        evidence_refs=list(action_record.get("evidence_refs", [])),
    )
    _write_json(output_dir / "enforcement_replay_validation.json", replay)

    chain_validation = validate_sel_artifact_chain(output_dir=output_dir, trace_id=str(decision_record["trace_id"]))
    _write_json(output_dir / "sel_artifact_chain_validation.json", chain_validation)

    return {
        "status": "completed",
        "trace_id": decision_record["trace_id"],
        "output_dir": str(output_dir),
        "replay_validation": replay,
        "artifact_chain_validation": chain_validation,
        "artifacts": sorted(artifacts.keys()),
    }


def validate_sel_artifact_chain(*, output_dir: Path, trace_id: str) -> dict[str, Any]:
    loaded: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    failures: list[str] = []

    for artifact_type in _REQUIRED_CHAIN:
        path = output_dir / f"{artifact_type}.json"
        if not path.exists():
            missing.append(artifact_type)
            continue
        artifact = _load_json(path)
        try:
            validate_artifact(artifact, artifact_type)
        except Exception as exc:
            failures.append(f"{artifact_type}_schema_invalid:{exc}")
        loaded[artifact_type] = artifact

    if missing:
        failures.append(f"missing_required_artifacts:{','.join(sorted(missing))}")

    if loaded:
        trace_mismatches = sorted(
            artifact_type for artifact_type, artifact in loaded.items() if artifact.get("trace_id") != trace_id
        )
        if trace_mismatches:
            failures.append(f"trace_mismatch:{','.join(trace_mismatches)}")

    action = loaded.get("enforcement_action_record", {})
    eval_result = loaded.get("enforcement_eval_result", {})
    readiness = loaded.get("enforcement_readiness_record", {})
    result = loaded.get("enforcement_result_record", {})
    bundle = loaded.get("enforcement_bundle", {})

    expected_refs = {
        "enforcement_action_record_ref": f"enforcement_action_record:{action.get('action_id')}",
        "enforcement_eval_result_ref": f"enforcement_eval_result:{eval_result.get('eval_id')}",
        "enforcement_readiness_record_ref": f"enforcement_readiness_record:{readiness.get('readiness_id')}",
        "enforcement_result_record_ref": f"enforcement_result_record:{result.get('result_id')}",
    }

    if result and result.get("enforcement_action_record_ref") != expected_refs["enforcement_action_record_ref"]:
        failures.append("lineage_broken:result_action_ref")
    if result and result.get("enforcement_eval_result_ref") != expected_refs["enforcement_eval_result_ref"]:
        failures.append("lineage_broken:result_eval_ref")
    if bundle and bundle.get("enforcement_action_record_ref") != expected_refs["enforcement_action_record_ref"]:
        failures.append("lineage_broken:bundle_action_ref")
    if bundle and bundle.get("enforcement_result_record_ref") != expected_refs["enforcement_result_record_ref"]:
        failures.append("lineage_broken:bundle_result_ref")

    status = "passed" if not failures else "failed"
    record = {
        "artifact_type": "validation_result_record",
        "validation_result_id": f"sel-chain-{_digest([trace_id, sorted(_REQUIRED_CHAIN), sorted(failures)])[:16]}",
        "attempt_id": f"sel-attempt-{_digest([trace_id, output_dir.as_posix()])[:12]}",
        "admission_ref": "sel_orchestration_runner:artifact_chain",
        "trace_id": trace_id,
        "workflow_equivalent": "sel_orchestration_runner",
        "validation_target": {"type": "repo_branch", "value": output_dir.as_posix()},
        "validation_scope": "narrow",
        "validation_path": "sel_artifact_chain",
        "commands": [
            {
                "command": "validate_sel_artifact_chain",
                "exit_code": 0 if status == "passed" else 1,
                "stdout_excerpt": "SEL artifact chain validated",
                "stderr_excerpt": "" if status == "passed" else "; ".join(failures),
            }
        ],
        "status": status,
        "blocking_reason": None if status == "passed" else "sel_artifact_chain_invalid",
        "failure_summary": None if status == "passed" else "; ".join(failures),
        "passed": status == "passed",
        "enforcement_owner": "SEL",
        "emitted_at": "2026-04-12T00:00:00Z",
    }
    validate_artifact(record, "validation_result_record")
    return record


def run_sel_replay_gate(*, output_dir: Path, decision_record: Mapping[str, Any], action_record: Mapping[str, Any]) -> dict[str, Any]:
    result = _load_json(output_dir / "enforcement_result_record.json")
    replay_source = _load_json(output_dir / "enforcement_replay_validation.json")
    replay = validate_enforcement_replay(
        decision_record=decision_record,
        action_record=action_record,
        first_result=result,
        replay_result=copy.deepcopy(result),
        evidence_refs=list(action_record.get("evidence_refs", [])),
    )
    if replay_source.get("result") != "pass":
        raise SELOrchestrationRunnerError("existing replay evidence already failed")
    if replay.get("result") != "pass":
        raise SELOrchestrationRunnerError("replay gate mismatch detected")
    return replay
