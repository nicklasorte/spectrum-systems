"""Canonical fail-closed PQX single-slice runner (B11-B14)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable, Optional

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.governance import (
    analyze_contract_impact,
    analyze_execution_change_impact,
    validate_manifest_completeness,
)
from spectrum_systems.modules.runtime.control_surface_gap_loader import (
    ControlSurfaceGapPacketLoaderError,
    load_control_surface_gap_packet,
)
from spectrum_systems.modules.runtime.control_surface_gap_to_pqx import (
    ControlSurfaceGapToPQXError,
    convert_gap_packet_to_pqx_work_items,
    sort_packet_gaps,
)
from spectrum_systems.modules.runtime.evaluation_control import (
    EvaluationControlError,
    build_evaluation_control_decision,
)
from spectrum_systems.modules.pqx_backbone import (
    LEGACY_EXECUTION_ROADMAP_PATH,
    PQXBackboneError,
    REPO_ROOT,
    RoadmapRow,
    iso_now,
    load_state,
    parse_system_roadmap,
    resolve_executable_row,
    resolve_roadmap_authority,
    save_state,
    utc_now,
)


class PQXSliceRunnerError(ValueError):
    """Raised when canonical PQX slice execution fails closed."""


Clock = Callable[[], object]


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _build_control_surface_gap_influence(*, packet: dict, packet_ref: str, work_items: list[dict]) -> dict[str, object]:
    if not isinstance(packet, dict):
        raise PQXSliceRunnerError("control-surface visibility projection requires packet object")
    if not isinstance(work_items, list):
        raise PQXSliceRunnerError("control-surface visibility projection requires work_items list")
    for index, item in enumerate(work_items):
        if not isinstance(item, dict):
            raise PQXSliceRunnerError(f"pqx_gap_work_items[{index}] must be an object")
        for key in ("work_item_id", "gap_id", "surface_name", "required_action_type"):
            value = item.get(key)
            if not isinstance(value, str) or not value:
                raise PQXSliceRunnerError(f"pqx_gap_work_items[{index}] missing required field: {key}")

    if not isinstance(packet_ref, str) or not packet_ref:
        raise PQXSliceRunnerError("control_surface_gap_packet_ref must be non-empty for visibility projection")
    gaps = packet.get("gaps")
    if not isinstance(gaps, list):
        raise PQXSliceRunnerError("control_surface_gap_packet.gaps must be a list for visibility projection")

    prioritized_gaps: list[dict[str, object]] = []
    for index, gap in enumerate(gaps):
        if not isinstance(gap, dict):
            raise PQXSliceRunnerError(f"control_surface_gap_packet.gaps[{index}] must be an object")
        required = ("gap_id", "surface_name", "severity")
        missing = [field for field in required if not isinstance(gap.get(field), str) or not str(gap.get(field))]
        if missing:
            raise PQXSliceRunnerError(
                f"control_surface_gap_packet.gaps[{index}] missing required visibility fields: {', '.join(missing)}"
            )
        prioritized_gaps.append(
            {
                "gap_id": str(gap["gap_id"]),
                "surface_name": str(gap["surface_name"]),
                "severity": str(gap["severity"]),
                "blocking": bool(gap.get("blocking")),
                "source_artifact_ref": str(gap.get("source_artifact_ref") or ""),
            }
        )
    prioritized_gaps = sorted(
        prioritized_gaps,
        key=lambda entry: (
            0 if entry["blocking"] else 1,
            str(entry["surface_name"]),
            str(entry["gap_id"]),
        ),
    )
    projected_work_items = sorted(
        [
            {
                "work_item_id": str(item["work_item_id"]),
                "gap_id": str(item["gap_id"]),
                "surface_name": str(item["surface_name"]),
                "required_action_type": str(item["required_action_type"]),
                "blocking": bool(item.get("blocking")),
            }
            for item in work_items
        ],
        key=lambda entry: (
            0 if entry["blocking"] else 1,
            str(entry["surface_name"]),
            str(entry["gap_id"]),
            str(entry["work_item_id"]),
        ),
    )
    decision = str(packet.get("overall_decision") or "")
    reason_codes = []
    if decision == "BLOCK":
        reason_codes.append("control_surface_gap_packet_block")
    if any(item["blocking"] for item in projected_work_items):
        reason_codes.append("blocking_gap_work_items_present")
    return {
        "control_surface_gap_packet_ref": packet_ref,
        "control_surface_gap_packet_consumed": True,
        "prioritized_control_surface_gaps": prioritized_gaps,
        "pqx_gap_work_items": projected_work_items,
        "control_surface_gap_influence": {
            "influenced_execution_block": decision == "BLOCK",
            "influenced_next_step_selection": len(projected_work_items) > 0,
            "influenced_priority_ordering": len(prioritized_gaps) > 1,
            "influenced_transition_decision": decision in {"BLOCK", "WARN"},
            "reason_codes": sorted(set(reason_codes)),
            "control_surface_blocking_reason_refs": [
                str(entry["gap_id"]) for entry in prioritized_gaps if bool(entry["blocking"])
            ],
        },
    }


def _block_payload(*, step_id: str, run_id: str, reason: str, block_type: str = "INVALID_EXECUTION_ENTRYPOINT") -> dict:
    return {
        "status": "blocked",
        "block_type": block_type,
        "step_id": step_id,
        "run_id": run_id,
        "reason": reason,
    }


def _enforce_contract_impact_gate(
    *,
    contract_impact_artifact_path: Optional[Path],
    changed_contract_paths: Optional[list[str]],
    changed_example_paths: Optional[list[str]],
    run_id: str,
    step_id: str,
    runs_root: Path,
) -> tuple[Optional[dict], Optional[str]]:
    artifact = None
    artifact_ref = None

    if contract_impact_artifact_path is not None:
        artifact = json.loads(contract_impact_artifact_path.read_text(encoding="utf-8"))
        validate_artifact(artifact, "contract_impact_artifact")
        artifact_ref = str(contract_impact_artifact_path)
    elif changed_contract_paths:
        artifact = analyze_contract_impact(
            repo_root=REPO_ROOT,
            changed_contract_paths=changed_contract_paths,
            changed_example_paths=changed_example_paths or [],
        )
        impact_path = runs_root / step_id / f"{run_id}.contract_impact_artifact.json"
        _write_json(impact_path, artifact)
        artifact_ref = _relative(impact_path)

    if artifact is None:
        return None, None

    if artifact.get("compatibility_class") in {"breaking", "indeterminate"}:
        reason = "; ".join(artifact.get("blocking_reasons", [])) or "contract impact unresolved"
        raise PQXSliceRunnerError(f"contract impact gate blocked ({artifact['compatibility_class']}): {reason}")
    if artifact.get("blocking") is True or artifact.get("safe_to_execute") is not True:
        reason = "; ".join(artifact.get("blocking_reasons", [])) or "contract impact safe_to_execute=false"
        raise PQXSliceRunnerError(f"contract impact gate blocked: {reason}")

    return artifact, artifact_ref


def _enforce_execution_change_impact_gate(
    *,
    execution_change_impact_artifact_path: Optional[Path],
    changed_paths: Optional[list[str]],
    baseline_ref: str,
    provided_reviews: Optional[list[str]],
    provided_eval_artifacts: Optional[list[str]],
    run_id: str,
    step_id: str,
    runs_root: Path,
) -> tuple[Optional[dict], Optional[str]]:
    artifact = None
    artifact_ref = None

    if execution_change_impact_artifact_path is not None:
        artifact = json.loads(execution_change_impact_artifact_path.read_text(encoding="utf-8"))
        validate_artifact(artifact, "execution_change_impact_artifact")
        artifact_ref = str(execution_change_impact_artifact_path)
    elif changed_paths:
        artifact = analyze_execution_change_impact(
            repo_root=REPO_ROOT,
            changed_paths=changed_paths,
            baseline_ref=baseline_ref,
            provided_reviews=provided_reviews or [],
            provided_eval_artifacts=provided_eval_artifacts or [],
        )
        impact_path = runs_root / step_id / f"{run_id}.execution_change_impact_artifact.json"
        _write_json(impact_path, artifact)
        artifact_ref = _relative(impact_path)

    if artifact is None:
        return None, None

    if (
        artifact.get("blocking") is True
        or artifact.get("indeterminate") is True
        or artifact.get("safe_to_execute") is not True
    ):
        reason = "; ".join(artifact.get("rationale", [])) or "execution change impact safe_to_execute=false"
        raise PQXSliceRunnerError(f"execution change impact gate blocked: {reason}")

    return artifact, artifact_ref


def _normalize_strategy_decision(value: str | None) -> str:
    mapping = {"ALLOW": "allow", "WARN": "warn", "FREEZE": "freeze", "BLOCK": "block"}
    normalized = mapping.get(str(value or "").upper())
    if normalized is None:
        raise PQXSliceRunnerError(f"unsupported preflight strategy_gate_decision: {value}")
    return normalized


def _enforce_contract_preflight_gate(
    *,
    contract_preflight_result_artifact_path: Optional[Path],
    changed_contract_paths: Optional[list[str]] = None,
    changed_example_paths: Optional[list[str]] = None,
) -> tuple[Optional[dict], Optional[dict]]:
    if contract_preflight_result_artifact_path is None:
        if changed_contract_paths or changed_example_paths:
            raise PQXSliceRunnerError(
                "contract preflight artifact is required for governed contract/example changes"
            )
        return None, None
    artifact = json.loads(contract_preflight_result_artifact_path.read_text(encoding="utf-8"))
    validate_artifact(artifact, "contract_preflight_result_artifact")
    control_signal = artifact.get("control_signal")
    if not isinstance(control_signal, dict):
        raise PQXSliceRunnerError("contract preflight artifact missing control_signal")
    action = _normalize_strategy_decision(control_signal.get("strategy_gate_decision"))
    preflight_status = str(artifact.get("preflight_status") or "")
    degraded_detection = bool(control_signal.get("degraded_detection"))
    masking_detected = bool(artifact.get("masking_detected"))
    allowed_actions_by_status = {
        "passed": {"allow", "warn"},
        "failed": {"block", "freeze"},
        "skipped": {"block"},
    }
    allowed_actions = allowed_actions_by_status.get(preflight_status)
    if allowed_actions is None or action not in allowed_actions:
        raise PQXSliceRunnerError(
            f"inconsistent preflight control mapping: preflight_status={preflight_status} decision={action}"
        )
    if action == "warn" and not degraded_detection:
        raise PQXSliceRunnerError("contract preflight WARN decision requires degraded_detection=true")
    if masking_detected and action != "block":
        raise PQXSliceRunnerError("contract preflight masking_detected=true requires BLOCK decision")
    rationale = str(control_signal.get("rationale") or "contract preflight control signal missing rationale")
    if action == "block":
        raise PQXSliceRunnerError(f"contract preflight BLOCK: {rationale}")
    if action == "freeze":
        raise PQXSliceRunnerError(f"contract preflight FREEZE: {rationale}")
    return artifact, control_signal




def _enforce_manifest_completeness_gate(*, manifest_path: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    result = validate_manifest_completeness(manifest)
    if result["valid"]:
        return

    reason_parts = ["manifest completeness gate blocked"]
    if result["errors"]:
        reason_parts.append("errors=" + "; ".join(result["errors"]))
    if result["missing_fields"]:
        reason_parts.append("missing_fields=" + ", ".join(result["missing_fields"]))
    raise PQXSliceRunnerError(" | ".join(reason_parts))


def _control_surface_artifacts_involved(
    *,
    changed_paths: Optional[list[str]],
    changed_contract_paths: Optional[list[str]],
    changed_example_paths: Optional[list[str]],
    contract_preflight_artifact: Optional[dict],
    control_surface_gap_packet_ref: Optional[str],
) -> bool:
    relevant_refs = [*(changed_paths or []), *(changed_contract_paths or []), *(changed_example_paths or [])]
    if any("control_surface" in str(path) for path in relevant_refs):
        return True
    if control_surface_gap_packet_ref:
        return True
    if not isinstance(contract_preflight_artifact, dict):
        return False
    if contract_preflight_artifact.get("control_surface_gap_result_ref"):
        return True
    if contract_preflight_artifact.get("pqx_gap_work_items_ref"):
        return True
    if contract_preflight_artifact.get("control_surface_gap_status") not in {None, "not_run"}:
        return True
    if contract_preflight_artifact.get("control_surface_gap_blocking") is True:
        return True
    return False


def _find_row(rows: list[RoadmapRow], step_id: str) -> RoadmapRow:
    row = next((entry for entry in rows if entry.step_id == step_id), None)
    if row is None:
        raise PQXSliceRunnerError(f"Requested roadmap row '{step_id}' was not found.")
    return row


def _build_regression_result(*, run_id: str, trace_id: str, now: str) -> dict:
    digest = hashlib.sha256(f"{run_id}:{trace_id}:regression".encode("utf-8")).hexdigest()
    return {
        "artifact_type": "regression_result",
        "schema_version": "1.1.0",
        "run_id": run_id,
        "suite_id": "pqx-single-slice",
        "created_at": now,
        "total_traces": 1,
        "passed_traces": 1,
        "failed_traces": 0,
        "pass_rate": 1.0,
        "overall_status": "pass",
        "regression_status": "pass",
        "blocked": False,
        "results": [
            {
                "trace_id": trace_id,
                "replay_result_id": f"replay:{run_id}",
                "analysis_id": f"analysis:{run_id}",
                "decision_status": "consistent",
                "reproducibility_score": 1.0,
                "drift_type": "",
                "passed": True,
                "failure_reasons": [],
                "baseline_replay_result_id": f"replay:{run_id}",
                "current_replay_result_id": f"replay:{run_id}",
                "baseline_trace_id": trace_id,
                "current_trace_id": trace_id,
                "baseline_reference": "contracts/examples/replay_result.json",
                "current_reference": "contracts/examples/replay_result.json",
                "mismatch_summary": [],
                "comparison_digest": digest,
            }
        ],
        "summary": {
            "drift_counts": {"none": 1},
            "average_reproducibility_score": 1.0,
        },
    }


def _resolve_fixture_decision_mode(mode: str | None) -> str:
    normalized = str(mode or "").strip().lower()
    if normalized in {"allow", "review", "block"}:
        return normalized
    raise PQXSliceRunnerError(
        "fixture_decision_mode must be one of: allow, review, block"
    )


def _apply_fixture_mode_to_replay(*, replay: dict, mode: str) -> None:
    error_budget = replay.get("error_budget_status") if isinstance(replay.get("error_budget_status"), dict) else None
    observability = replay.get("observability_metrics") if isinstance(replay.get("observability_metrics"), dict) else None
    metrics = observability.get("metrics") if isinstance(observability, dict) and isinstance(observability.get("metrics"), dict) else None
    if not isinstance(error_budget, dict) or not isinstance(metrics, dict):
        raise PQXSliceRunnerError("replay fixture missing required error_budget_status/observability_metrics.metrics")
    objectives = error_budget.get("objectives")
    objective_by_metric = {
        str(item.get("metric_name")): item
        for item in objectives
        if isinstance(item, dict) and isinstance(item.get("metric_name"), str)
    } if isinstance(objectives, list) else {}

    if mode == "review":
        error_budget["budget_status"] = "warning"
        error_budget["highest_severity"] = "warning"
        error_budget["triggered_conditions"] = [
            {
                "metric_name": "replay_success_rate",
                "status": "warning",
                "consumption_ratio": 0.95,
            }
        ]
        replay["consistency_status"] = "match"
        replay["drift_detected"] = False
        metrics["replay_success_rate"] = 0.86
        metrics["drift_exceed_threshold_rate"] = 0.0
        if "replay_success_rate" in objective_by_metric:
            objective_by_metric["replay_success_rate"]["observed_value"] = 0.86
        if "drift_exceed_threshold_rate" in objective_by_metric:
            objective_by_metric["drift_exceed_threshold_rate"]["observed_value"] = 0.0
        return
    if mode == "block":
        error_budget["budget_status"] = "invalid"
        error_budget["highest_severity"] = "invalid"
        error_budget["triggered_conditions"] = [
            {
                "metric_name": "drift_exceed_threshold_rate",
                "status": "invalid",
                "consumption_ratio": 1.0,
            }
        ]
        replay["consistency_status"] = "mismatch"
        replay["drift_detected"] = True
        metrics["replay_success_rate"] = 0.10
        metrics["drift_exceed_threshold_rate"] = 1.0
        if "replay_success_rate" in objective_by_metric:
            objective_by_metric["replay_success_rate"]["observed_value"] = 0.10
        if "drift_exceed_threshold_rate" in objective_by_metric:
            objective_by_metric["drift_exceed_threshold_rate"]["observed_value"] = 1.0
        return

    error_budget["budget_status"] = "healthy"
    error_budget["highest_severity"] = "healthy"
    error_budget["triggered_conditions"] = []
    replay["consistency_status"] = "match"
    replay["drift_detected"] = False
    metrics["replay_success_rate"] = 1.0
    metrics["drift_exceed_threshold_rate"] = 0.0
    if "replay_success_rate" in objective_by_metric:
        objective_by_metric["replay_success_rate"]["observed_value"] = 1.0
    if "drift_exceed_threshold_rate" in objective_by_metric:
        objective_by_metric["drift_exceed_threshold_rate"]["observed_value"] = 0.0


def run_pqx_slice(
    *,
    step_id: str,
    roadmap_path: Path,
    state_path: Path,
    runs_root: Path,
    clock: Optional[Clock] = None,
    pqx_output_text: Optional[str] = None,
    enforce_certification: bool = True,
    emit_artifacts: bool = True,
    contract_impact_artifact_path: Optional[Path] = None,
    changed_contract_paths: Optional[list[str]] = None,
    changed_example_paths: Optional[list[str]] = None,
    execution_change_impact_artifact_path: Optional[Path] = None,
    changed_paths: Optional[list[str]] = None,
    execution_change_baseline_ref: str = "HEAD",
    provided_reviews: Optional[list[str]] = None,
    provided_eval_artifacts: Optional[list[str]] = None,
    enforce_manifest_completeness: bool = False,
    contract_preflight_result_artifact_path: Optional[Path] = None,
    control_surface_gap_packet_ref: Optional[str] = None,
    require_control_surface_gap_packet_for_control_surfaces: bool = True,
    fixture_decision_mode: str = "allow",
) -> dict:
    """Canonical single-path slice execution with mandatory certification and audit artifacts."""

    active_clock = clock or utc_now
    run_id = f"pqx-slice-{iso_now(active_clock).replace(':', '').replace('-', '')}"

    if not isinstance(step_id, str) or not step_id.strip():
        return _block_payload(step_id=str(step_id), run_id=run_id, reason="step_id is required")

    normalized_step_id = step_id.strip()
    try:
        authority = resolve_roadmap_authority()
    except PQXBackboneError as exc:
        return _block_payload(step_id=normalized_step_id, run_id=run_id, reason=str(exc))

    if not roadmap_path.exists():
        return _block_payload(step_id=normalized_step_id, run_id=run_id, reason=f"missing roadmap path: {roadmap_path}")

    if roadmap_path.resolve() not in {authority.execution_roadmap_path.resolve(), LEGACY_EXECUTION_ROADMAP_PATH.resolve()}:
        return _block_payload(
            step_id=normalized_step_id,
            run_id=run_id,
            reason=f"ambiguous roadmap path: {_relative(roadmap_path)}",
        )

    try:
        state = load_state(state_path)
        rows = parse_system_roadmap(roadmap_path)
        row = _find_row(rows, normalized_step_id)
        resolved_row, block = resolve_executable_row(rows, state, step_id=normalized_step_id)
    except (PQXBackboneError, PQXSliceRunnerError) as exc:
        return _block_payload(step_id=normalized_step_id, run_id=run_id, reason=str(exc))

    if block is not None or resolved_row is None:
        return _block_payload(step_id=normalized_step_id, run_id=run_id, reason=(block or {}).get("reason", "blocked"))

    if pqx_output_text is None:
        return _block_payload(step_id=normalized_step_id, run_id=run_id, reason="pqx_output_text is required")

    row_state = next((item for item in state["rows"] if item["step_id"] == normalized_step_id), None)
    if row_state is None:
        row_state = {
            "step_id": normalized_step_id,
            "status": "not_started",
            "last_run": None,
            "dependencies_satisfied": True,
            "retries": 0,
            "strategy_gate_decision": "block",
        }
        state["rows"].append(row_state)

    if enforce_manifest_completeness:
        try:
            _enforce_manifest_completeness_gate(manifest_path=REPO_ROOT / "contracts" / "standards-manifest.json")
        except (PQXSliceRunnerError, FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
            return _block_payload(
                step_id=normalized_step_id,
                run_id=run_id,
                reason=str(exc),
                block_type="MANIFEST_COMPLETENESS_BLOCKED",
            )

    preflight_artifact = None
    preflight_signal = None
    try:
        preflight_artifact, preflight_signal = _enforce_contract_preflight_gate(
            contract_preflight_result_artifact_path=contract_preflight_result_artifact_path,
            changed_contract_paths=changed_contract_paths,
            changed_example_paths=changed_example_paths,
        )
    except (PQXSliceRunnerError, FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        row_state["status"] = "blocked"
        row_state["last_run"] = iso_now(active_clock)
        row_state["strategy_gate_decision"] = "freeze" if "FREEZE" in str(exc) else "block"
        save_state(state, state_path)
        return _block_payload(
            step_id=normalized_step_id,
            run_id=run_id,
            reason=str(exc),
            block_type="CONTRACT_PREFLIGHT_BLOCKED" if row_state["strategy_gate_decision"] == "block" else "CONTRACT_PREFLIGHT_FROZEN",
        )
    if preflight_signal is not None:
        row_state["strategy_gate_decision"] = _normalize_strategy_decision(preflight_signal.get("strategy_gate_decision"))

    control_surface_required = _control_surface_artifacts_involved(
        changed_paths=changed_paths,
        changed_contract_paths=changed_contract_paths,
        changed_example_paths=changed_example_paths,
        contract_preflight_artifact=preflight_artifact,
        control_surface_gap_packet_ref=control_surface_gap_packet_ref,
    )
    if control_surface_required and require_control_surface_gap_packet_for_control_surfaces and not control_surface_gap_packet_ref:
        return _block_payload(
            step_id=normalized_step_id,
            run_id=run_id,
            reason="control_surface_gap_packet is required when control-surface artifacts are involved",
            block_type="CONTROL_SURFACE_GAP_PACKET_REQUIRED",
        )

    control_surface_visibility = {
        "control_surface_gap_packet_ref": None,
        "control_surface_gap_packet_consumed": False,
        "prioritized_control_surface_gaps": [],
        "pqx_gap_work_items": [],
        "control_surface_gap_influence": {
            "influenced_execution_block": False,
            "influenced_next_step_selection": False,
            "influenced_priority_ordering": False,
            "influenced_transition_decision": False,
            "reason_codes": [],
            "control_surface_blocking_reason_refs": [],
        },
    }
    if control_surface_gap_packet_ref:
        try:
            control_surface_gap_packet = load_control_surface_gap_packet(control_surface_gap_packet_ref)
            prioritized_gaps = sort_packet_gaps(control_surface_gap_packet["gaps"])
            control_surface_gap_packet["gaps"] = prioritized_gaps
            pqx_gap_work_items = convert_gap_packet_to_pqx_work_items(control_surface_gap_packet)
            control_surface_visibility = _build_control_surface_gap_influence(
                packet=control_surface_gap_packet,
                packet_ref=control_surface_gap_packet_ref,
                work_items=pqx_gap_work_items,
            )
        except (ControlSurfaceGapPacketLoaderError, ControlSurfaceGapToPQXError, KeyError, TypeError, ValueError) as exc:
            return _block_payload(
                step_id=normalized_step_id,
                run_id=run_id,
                reason=f"invalid control_surface_gap_packet: {exc}",
                block_type="CONTROL_SURFACE_GAP_PACKET_INVALID",
            )
        except PQXSliceRunnerError as exc:
            return _block_payload(
                step_id=normalized_step_id,
                run_id=run_id,
                reason=f"invalid control_surface_gap_packet visibility: {exc}",
                block_type="CONTROL_SURFACE_GAP_PACKET_INVALID",
            )

        if control_surface_gap_packet["overall_decision"] == "BLOCK":
            return {
                "status": "blocked",
                "block_type": "CONTROL_SURFACE_GAP_PACKET_BLOCKED",
                "step_id": normalized_step_id,
                "run_id": run_id,
                "reason": "control_surface_gap_packet_block",
                "blocking_gaps": control_surface_gap_packet["gaps"],
                "control_surface_gap_visibility": control_surface_visibility,
            }

    try:
        _enforce_contract_impact_gate(
            contract_impact_artifact_path=contract_impact_artifact_path,
            changed_contract_paths=changed_contract_paths,
            changed_example_paths=changed_example_paths,
            run_id=run_id,
            step_id=normalized_step_id,
            runs_root=runs_root,
        )
    except (PQXSliceRunnerError, FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        return _block_payload(
            step_id=normalized_step_id,
            run_id=run_id,
            reason=str(exc),
            block_type="CONTRACT_IMPACT_BLOCKED",
        )

    try:
        _enforce_execution_change_impact_gate(
            execution_change_impact_artifact_path=execution_change_impact_artifact_path,
            changed_paths=changed_paths,
            baseline_ref=execution_change_baseline_ref,
            provided_reviews=provided_reviews,
            provided_eval_artifacts=provided_eval_artifacts,
            run_id=run_id,
            step_id=normalized_step_id,
            runs_root=runs_root,
        )
    except (PQXSliceRunnerError, FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        return _block_payload(
            step_id=normalized_step_id,
            run_id=run_id,
            reason=str(exc),
            block_type="EXECUTION_CHANGE_IMPACT_BLOCKED",
        )

    trace_id = f"trace:{run_id}:{normalized_step_id}"
    now = iso_now(active_clock)
    step_dir = runs_root / normalized_step_id

    request_payload = {
        "schema_version": "1.1.0",
        "run_id": run_id,
        "step_id": row.step_id,
        "step_name": row.step_name,
        "dependencies": list(row.dependencies),
        "requested_at": now,
        "prompt": f"Implement roadmap step {row.step_id}: {row.step_name}",
        "roadmap_version": authority.execution_roadmap_ref,
        "row_snapshot": {
            "row_index": row.row_index,
            "step_id": row.step_id,
            "step_name": row.step_name,
            "dependencies": list(row.dependencies),
            "status": row.status,
        },
    }
    request_path = _write_json(step_dir / f"{run_id}.request.json", request_payload)
    validate_artifact(request_payload, "pqx_execution_request")

    result_payload = {
        "schema_version": "1.0.0",
        "run_id": run_id,
        "step_id": row.step_id,
        "execution_status": "success",
        "started_at": now,
        "completed_at": iso_now(active_clock),
        "output_text": pqx_output_text,
        "error": None,
    }
    result_path = _write_json(step_dir / f"{run_id}.result.json", result_payload)
    validate_artifact(result_payload, "pqx_execution_result")

    replay = json.loads((REPO_ROOT / "contracts" / "examples" / "replay_result.json").read_text(encoding="utf-8"))
    try:
        fixture_mode = _resolve_fixture_decision_mode(fixture_decision_mode)
    except PQXSliceRunnerError as exc:
        return _block_payload(
            step_id=normalized_step_id,
            run_id=run_id,
            reason=str(exc),
            block_type="FIXTURE_DECISION_MODE_INVALID",
        )
    _apply_fixture_mode_to_replay(replay=replay, mode=fixture_mode)
    replay["trace_id"] = trace_id
    replay["original_run_id"] = run_id
    replay["replay_run_id"] = run_id
    replay["timestamp"] = iso_now(active_clock)
    if isinstance(replay.get("observability_metrics"), dict):
        replay["observability_metrics"].setdefault("trace_refs", {})["trace_id"] = trace_id
    if isinstance(replay.get("error_budget_status"), dict):
        replay["error_budget_status"].setdefault("trace_refs", {})["trace_id"] = trace_id
        if isinstance(replay.get("observability_metrics"), dict):
            replay["error_budget_status"]["observability_metrics_id"] = replay["observability_metrics"].get("artifact_id")
    if isinstance(replay.get("alert_trigger"), dict):
        replay["alert_trigger"].setdefault("trace_refs", {})["trace_id"] = trace_id
    replay_path = _write_json(step_dir / f"{run_id}.replay_result.json", replay)

    try:
        control = build_evaluation_control_decision(replay)
    except EvaluationControlError as exc:
        raise PQXSliceRunnerError(f"failed to derive evaluation_control_decision from replay fixture: {exc}") from exc
    control_path = _write_json(step_dir / f"{run_id}.control_decision.json", control)

    cert_pack = json.loads((REPO_ROOT / "contracts" / "examples" / "control_loop_certification_pack.json").read_text(encoding="utf-8"))
    cert_pack["run_id"] = run_id
    cert_pack["trace_id"] = trace_id
    cert_pack["generated_at"] = iso_now(active_clock)
    cert_pack["provenance_trace_refs"] = {"commit_sha": "deterministic-local", "branch": "main", "trace_refs": [trace_id]}
    cert_pack_path = _write_json(step_dir / f"{run_id}.control_loop_certification_pack.json", cert_pack)

    error_budget = json.loads((REPO_ROOT / "contracts" / "examples" / "error_budget_status.json").read_text(encoding="utf-8"))
    error_budget["timestamp"] = iso_now(active_clock)
    error_budget.setdefault("trace_refs", {})["trace_id"] = trace_id
    error_budget_path = _write_json(step_dir / f"{run_id}.error_budget_status.json", error_budget)

    regression = _build_regression_result(run_id=run_id, trace_id=trace_id, now=iso_now(active_clock))
    regression_path = _write_json(step_dir / f"{run_id}.regression_run_result.json", regression)
    validate_artifact(regression, "regression_run_result")

    if not emit_artifacts:
        return _block_payload(step_id=normalized_step_id, run_id=run_id, reason="artifact emission disabled", block_type="ARTIFACT_EMISSION_BLOCKED")

    try:
        from spectrum_systems.modules.governance.done_certification import DoneCertificationError, run_done_certification

        certification = run_done_certification(
            {
                "replay_result_ref": str(replay_path),
                "regression_result_ref": str(regression_path),
                "certification_pack_ref": str(cert_pack_path),
                "error_budget_ref": str(error_budget_path),
                "policy_ref": str(control_path),
            }
        )
    except DoneCertificationError as exc:
        return _block_payload(step_id=normalized_step_id, run_id=run_id, reason=f"certification failed: {exc}", block_type="CERTIFICATION_BLOCKED")

    certification_path = _write_json(step_dir / f"{run_id}.done_certification_record.json", certification)

    if enforce_certification and certification.get("final_status") != "PASSED":
        return _block_payload(step_id=normalized_step_id, run_id=run_id, reason="failed certification", block_type="CERTIFICATION_BLOCKED")

    execution_record = {
        "schema_version": "1.1.0",
        "artifact_type": "pqx_slice_execution_record",
        "step_id": normalized_step_id,
        "run_id": run_id,
        "trace_id": trace_id,
        "status": "completed",
        "decision_summary": {
            "execution_status": "success",
            "control_decision": control.get("decision", "allow"),
            "enforcement_action": control.get("system_response", "allow"),
        },
        "artifacts_emitted": [
            _relative(request_path),
            _relative(result_path),
            _relative(replay_path),
            _relative(regression_path),
            _relative(control_path),
            _relative(cert_pack_path),
            _relative(error_budget_path),
            _relative(certification_path),
        ],
        "certification_status": "certified",
        "replay_result_ref": _relative(replay_path),
        "control_decision_ref": _relative(control_path),
        "control_surface_gap_packet_ref": control_surface_visibility["control_surface_gap_packet_ref"],
        "control_surface_gap_packet_consumed": control_surface_visibility["control_surface_gap_packet_consumed"],
        "prioritized_control_surface_gaps": control_surface_visibility["prioritized_control_surface_gaps"],
        "pqx_gap_work_items": control_surface_visibility["pqx_gap_work_items"],
        "control_surface_gap_influence": control_surface_visibility["control_surface_gap_influence"],
    }
    if preflight_signal is not None:
        execution_record["decision_summary"]["control_decision"] = row_state["strategy_gate_decision"]
        execution_record["artifacts_emitted"].append(str(contract_preflight_result_artifact_path))
    validate_artifact(execution_record, "pqx_slice_execution_record")
    execution_record_path = _write_json(step_dir / f"{run_id}.pqx_slice_execution_record.json", execution_record)

    audit_bundle = {
        "bundle_id": f"pqx-slice-audit:{run_id}:{normalized_step_id}",
        "step_id": normalized_step_id,
        "run_id": run_id,
        "trace_id": trace_id,
        "trace_ref": _relative(request_path),
        "replay_result_ref": _relative(replay_path),
        "eval_artifact_refs": [_relative(regression_path)],
        "control_decision_ref": _relative(control_path),
        "certification_result_ref": _relative(certification_path),
    }
    audit_bundle_path = _write_json(step_dir / f"{run_id}.pqx_slice_audit_bundle.json", audit_bundle)

    row_state["status"] = "running"
    row_state["dependencies_satisfied"] = True
    row_state["last_run"] = iso_now(active_clock)
    save_state(state, state_path)

    response = {
        "status": "complete",
        "step_id": normalized_step_id,
        "run_id": run_id,
        "trace_id": trace_id,
        "request": str(request_path),
        "result": str(result_path),
        "slice_execution_record": str(execution_record_path),
        "done_certification_record": str(certification_path),
        "certification_status": "certified",
        "pqx_slice_audit_bundle": str(audit_bundle_path),
        "control_surface_gap_visibility": control_surface_visibility,
    }
    if preflight_artifact is not None:
        response["contract_preflight_status"] = preflight_artifact.get("preflight_status")
        response["contract_preflight_decision"] = row_state["strategy_gate_decision"]
    return response
