"""Required-eval coverage registry loading and fail-closed enforcement (BATCH-S2)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class RequiredEvalCoverageError(Exception):
    """Raised when required eval coverage cannot be determined deterministically."""


_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_REGISTRY_PATH = _REPO_ROOT / "contracts" / "examples" / "required_eval_registry.json"

_ENF01_REQUIRED_EVALS = {
    "complexity_justification_valid",
    "core_loop_alignment_valid",
    "debuggability_valid",
}


def _validate(payload: dict[str, Any], schema_name: str) -> None:
    validator = Draft202012Validator(load_schema(schema_name), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.absolute_path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise RequiredEvalCoverageError(f"{schema_name} validation failed: {details}")


def _digest(prefix: str, payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"{prefix}-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:12].upper()}"


def _is_non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and any(isinstance(item, str) and item.strip() for item in value)


def _enf01_enforcement_from_eval_records(
    *,
    required_declared: list[str],
    result_by_id: dict[str, dict[str, Any]],
) -> tuple[str, str, str, list[str]]:
    if set(required_declared) != _ENF01_REQUIRED_EVALS:
        return "allow", "none", "complete", []

    blocking_reasons: list[str] = []
    freeze_reasons: list[str] = []

    complexity = result_by_id.get("complexity_justification_valid")
    complexity_record = complexity.get("complexity_justification_record") if isinstance(complexity, dict) else None
    if not isinstance(complexity_record, dict):
        blocking_reasons.append("missing required artifact: complexity_justification_record")
    else:
        if not _is_non_empty_text(complexity_record.get("failure_prevented")):
            blocking_reasons.append("complexity_justification_record.failure_prevented must be present")
        metric_present = _is_non_empty_text(complexity_record.get("measurable_metric")) or _is_non_empty_text(complexity_record.get("signal_improved"))
        if not metric_present:
            blocking_reasons.append("complexity_justification_record must include measurable_metric or signal_improved")
        if not _is_non_empty_text(complexity_record.get("why_not_existing_owner")):
            blocking_reasons.append("complexity_justification_record.why_not_existing_owner must be present")
        duplicate_of_system = complexity_record.get("duplicate_of_system")
        if isinstance(duplicate_of_system, str) and duplicate_of_system.strip():
            justification_status = str(complexity_record.get("justification_status") or "")
            if justification_status not in {"rejected", "blocked"}:
                blocking_reasons.append("duplicate ownership signal detected via complexity_justification_record.duplicate_of_system")

    loop = result_by_id.get("core_loop_alignment_valid")
    loop_record = loop.get("core_loop_alignment_record") if isinstance(loop, dict) else None
    if not isinstance(loop_record, dict):
        blocking_reasons.append("missing required artifact: core_loop_alignment_record")
    else:
        loop_mapping_status = str(loop_record.get("loop_mapping_status") or "").lower()
        if loop_mapping_status == "indeterminate":
            freeze_reasons.append("loop mapping is indeterminate")
        maps_to_stages = loop_record.get("maps_to_stages")
        if not isinstance(maps_to_stages, list) or not maps_to_stages:
            blocking_reasons.append("core_loop_alignment_record.maps_to_stages must be non-empty")
        strengthens_existing_loop = loop_record.get("strengthens_existing_loop")
        explicitly_acceptable = bool(loop_record.get("explicitly_acceptable"))
        if strengthens_existing_loop is not True and not explicitly_acceptable:
            blocking_reasons.append("core_loop_alignment_record must strengthen existing loop or be explicitly acceptable")
        introduces_parallel_loop = loop_record.get("introduces_parallel_loop")
        if introduces_parallel_loop is True:
            blocking_reasons.append("core_loop_alignment_record introduces parallel loop")
        score = loop_record.get("loop_impact_score")
        if not isinstance(score, (int, float)):
            blocking_reasons.append("core_loop_alignment_record.loop_impact_score must be numeric")
        elif float(score) < 0.6 or float(score) > 1.0:
            blocking_reasons.append("core_loop_alignment_record.loop_impact_score must be between 0.6 and 1.0")

    debug = result_by_id.get("debuggability_valid")
    debug_record = debug.get("debuggability_record") if isinstance(debug, dict) else None
    if not isinstance(debug_record, dict):
        blocking_reasons.append("missing required artifact: debuggability_record")
    else:
        if debug_record.get("trace_complete") is not True:
            blocking_reasons.append("debuggability_record.trace_complete must be true")
        if debug_record.get("lineage_complete") is not True:
            blocking_reasons.append("debuggability_record.lineage_complete must be true")
        if not _is_non_empty_list(debug_record.get("failure_modes_defined")):
            blocking_reasons.append("debuggability_record.failure_modes_defined must be non-empty")
        if debug_record.get("reason_codes_defined") is not True:
            blocking_reasons.append("debuggability_record.reason_codes_defined must be true")

        if debug_record.get("debug_expectations_clear") is False:
            freeze_reasons.append("replay/debug trace expectations are unclear for target surface")

        replay_expected = debug_record.get("replay_expected")
        replay_supported = debug_record.get("replay_supported")
        if replay_expected is True:
            if replay_supported is not True:
                if replay_supported is None:
                    freeze_reasons.append("debuggability evidence is incomplete for required replay support")
                else:
                    blocking_reasons.append("debuggability_record.replay_supported must be true when replay_expected is true")
        elif replay_expected is None:
            freeze_reasons.append("replay expectation is unclear for target surface")

    if blocking_reasons:
        return "block", "required_eval_failed", "incomplete", blocking_reasons
    if freeze_reasons:
        return "freeze", "indeterminate_required_eval", "indeterminate_blocking", freeze_reasons
    return "allow", "none", "complete", []


def load_required_eval_registry(path: str | Path | None = None) -> dict[str, Any]:
    registry_path = Path(path) if path is not None else _DEFAULT_REGISTRY_PATH
    if not registry_path.exists():
        raise RequiredEvalCoverageError(f"required eval registry not found: {registry_path}")
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RequiredEvalCoverageError("required eval registry must be a JSON object")
    _validate(payload, "required_eval_registry")
    return payload


def enforce_required_eval_coverage(
    *,
    artifact_family: str,
    eval_definitions: list[str],
    eval_results: list[dict[str, Any]],
    trace_id: str,
    run_id: str,
    created_at: str,
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not artifact_family:
        raise RequiredEvalCoverageError("artifact_family must be non-empty")
    if not trace_id or not run_id:
        raise RequiredEvalCoverageError("trace_id and run_id are required")

    reg = registry if registry is not None else load_required_eval_registry()
    if not isinstance(reg, dict):
        raise RequiredEvalCoverageError("registry must be an object")

    mapping = None
    for item in reg.get("mappings", []):
        if isinstance(item, dict) and item.get("artifact_family") == artifact_family:
            mapping = item
            break

    definition_set = {item for item in eval_definitions if isinstance(item, str) and item}
    result_by_id: dict[str, dict[str, Any]] = {}
    for row in eval_results:
        if not isinstance(row, dict):
            continue
        eval_id = row.get("eval_id") or row.get("eval_type")
        if isinstance(eval_id, str) and eval_id:
            result_by_id[eval_id] = row

    if mapping is None:
        required_declared: list[str] = []
        missing_defs: list[str] = []
        missing_results: list[str] = []
        indeterminate: list[str] = []
        completeness = "mapping_missing"
        decision = "block"
        reason_code = "missing_required_eval_mapping"
        blocking_reasons = [f"missing required eval mapping for artifact family: {artifact_family}"]
    else:
        required = [
            str(item.get("eval_id"))
            for item in mapping.get("required_evals", [])
            if isinstance(item, dict) and item.get("mandatory_for_progression") is True and isinstance(item.get("eval_id"), str)
        ]
        required_declared = sorted(set(required))
        missing_defs = sorted(eval_id for eval_id in required_declared if eval_id not in definition_set)
        missing_results = sorted(eval_id for eval_id in required_declared if eval_id not in result_by_id)
        indeterminate = sorted(
            eval_id
            for eval_id in required_declared
            if eval_id in result_by_id
            and (result_by_id[eval_id].get("passed") is None or str(result_by_id[eval_id].get("result_status", "")).lower() == "indeterminate")
        )
        failed = sorted(
            eval_id
            for eval_id in required_declared
            if eval_id in result_by_id
            and result_by_id[eval_id].get("passed") is False
        )

        blocking_reasons = []
        decision = "allow"
        reason_code = "none"
        completeness = "complete"
        if missing_defs:
            decision = "block"
            reason_code = "missing_required_eval_definition"
            completeness = "incomplete"
            blocking_reasons.append(f"missing required eval definition(s): {', '.join(missing_defs)}")
        elif missing_results:
            decision = "block"
            reason_code = "missing_required_eval_result"
            completeness = "incomplete"
            blocking_reasons.extend(
                [f"missing required judgment eval: {eval_id}" for eval_id in missing_results]
            )
        elif indeterminate:
            decision = "freeze"
            reason_code = "indeterminate_required_eval"
            completeness = "indeterminate_blocking"
            blocking_reasons.append(f"indeterminate required eval result(s): {', '.join(indeterminate)}")
        elif failed:
            decision = "block"
            reason_code = "required_eval_failed"
            completeness = "incomplete"
            blocking_reasons.extend(
                [f"failing required judgment eval: {eval_id}" for eval_id in failed]
            )
        else:
            enf01_decision, enf01_reason_code, enf01_completeness, enf01_reasons = _enf01_enforcement_from_eval_records(
                required_declared=required_declared,
                result_by_id=result_by_id,
            )
            decision = enf01_decision
            reason_code = enf01_reason_code
            completeness = enf01_completeness
            blocking_reasons = enf01_reasons

    signal_reason = {
        "none": "none",
        "missing_required_eval_mapping": "missing_mapping",
        "missing_required_eval_definition": "missing_definition",
        "missing_required_eval_result": "missing_result",
        "indeterminate_required_eval": "indeterminate_result",
        "required_eval_failed": "failed_required_eval",
    }[reason_code]

    coverage_registry_seed = {
        "artifact_family": artifact_family,
        "required_evals_declared": required_declared,
        "required_evals_present": sorted(eval_id for eval_id in required_declared if eval_id in result_by_id),
        "missing_eval_definitions": missing_defs,
        "missing_eval_results": missing_results,
        "indeterminate_required_evals": indeterminate,
        "coverage_completeness_status": completeness,
        "trace_id": trace_id,
        "run_id": run_id,
    }
    coverage_registry_id = _digest("ECR", coverage_registry_seed)

    coverage_registry = {
        "artifact_type": "eval_coverage_registry",
        "coverage_registry_id": coverage_registry_id,
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": str(reg.get("standards_version") or "unknown"),
        "artifact_family": artifact_family,
        "required_evals_declared": coverage_registry_seed["required_evals_declared"],
        "required_evals_present": coverage_registry_seed["required_evals_present"],
        "missing_eval_definitions": missing_defs,
        "missing_eval_results": missing_results,
        "indeterminate_required_evals": indeterminate,
        "coverage_completeness_status": completeness,
        "trace": {"trace_id": trace_id, "run_id": run_id},
        "created_at": created_at,
    }
    _validate(coverage_registry, "eval_coverage_registry")

    signal_seed = {
        "artifact_family": artifact_family,
        "decision": decision,
        "reason_code": reason_code,
        "coverage_registry_id": coverage_registry_id,
        "trace_id": trace_id,
        "run_id": run_id,
    }
    signal_id = _digest("ECS", signal_seed)
    coverage_signal = {
        "artifact_type": "eval_coverage_signal",
        "signal_id": signal_id,
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": str(reg.get("standards_version") or "unknown"),
        "artifact_family": artifact_family,
        "coverage_status": "complete" if decision == "allow" else decision,
        "block_reason": signal_reason,
        "coverage_registry_ref": f"eval_coverage_registry:{coverage_registry_id}",
        "trace": {"trace_id": trace_id, "run_id": run_id},
        "created_at": created_at,
    }
    _validate(coverage_signal, "eval_coverage_signal")

    enforcement_id = _digest("MRE", {**signal_seed, "signal_id": signal_id})
    enforcement = {
        "artifact_type": "missing_required_eval_enforcement",
        "enforcement_id": enforcement_id,
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": str(reg.get("standards_version") or "unknown"),
        "artifact_family": artifact_family,
        "decision": decision,
        "reason_code": reason_code,
        "blocking_reasons": blocking_reasons,
        "coverage_signal_ref": f"eval_coverage_signal:{signal_id}",
        "trace": {"trace_id": trace_id, "run_id": run_id},
        "created_at": created_at,
    }
    _validate(enforcement, "missing_required_eval_enforcement")

    return {
        "coverage_registry": coverage_registry,
        "coverage_signal": coverage_signal,
        "enforcement": enforcement,
    }
