"""Deterministic failure_record -> generated_eval_case transformation and admission checks."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List

from jsonschema import Draft202012Validator

from spectrum_systems.contracts import load_schema


def _canonical_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash_id(prefix: str, payload: Dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()[:16].upper()
    return f"{prefix}-{digest}"


def _as_nonempty_string(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text else default


def _sorted_unique_strings(items: Any) -> List[str]:
    if not isinstance(items, list):
        return []
    return sorted({str(item).strip() for item in items if str(item).strip()})


def _scenario_name(failure_type: str, reason_code: str) -> str:
    return f"{failure_type.lower()}__{reason_code.lower()}".replace(" ", "_")


def _expected_outcome(failure_type: str, reason_code: str) -> str:
    if failure_type.upper() == "BLOCK":
        return f"halt_with_reason_code:{reason_code}"
    if failure_type.upper() == "FREEZE":
        return f"pause_with_reason_code:{reason_code}"
    return f"fail_closed_with_reason_code:{reason_code}"


def generate_eval_case_from_failure_record(
    failure_record: Dict[str, Any],
    *,
    normalized_reason_code: str | None = None,
) -> Dict[str, Any]:
    """Transform a failure_record into a replayable generated_eval_case deterministically."""

    reason_code = _as_nonempty_string(failure_record.get("reason_code"), "unknown_failure")
    failure_type = _as_nonempty_string(failure_record.get("failure_type"), "UNKNOWN")
    trace_id = _as_nonempty_string(failure_record.get("trace_id"), "missing:trace_id")
    run_id = _as_nonempty_string(failure_record.get("run_id"), "missing:run_id")
    stage = _as_nonempty_string(failure_record.get("stage"), "unknown_stage")
    source_failure_artifact_id = _as_nonempty_string(
        failure_record.get("artifact_id"),
        _hash_id(
            "FAIL",
            {
                "trace_id": trace_id,
                "run_id": run_id,
                "stage": stage,
                "reason_code": reason_code,
                "failure_type": failure_type,
            },
        ),
    )

    missing_artifacts = _sorted_unique_strings(failure_record.get("missing_artifacts"))
    failed_evals = _sorted_unique_strings(failure_record.get("failed_evals"))

    normalized = _as_nonempty_string(normalized_reason_code)
    expected_reason_code = normalized or reason_code
    scenario_description = (
        f"Replay {failure_type} failure at stage {stage} and verify fail-closed reason_code linkage "
        f"to {expected_reason_code}."
    )

    input_conditions: Dict[str, Any] = {
        "stage": stage,
        "failure_type": failure_type,
        "missing_artifacts": missing_artifacts,
        "failed_evals": failed_evals,
    }

    seed = {
        "source_failure_artifact_id": source_failure_artifact_id,
        "trace_id": trace_id,
        "run_id": run_id,
        "reason_code": reason_code,
        "expected_reason_code": expected_reason_code,
        "input_conditions": input_conditions,
    }

    generated_eval_case = {
        "artifact_type": "generated_eval_case",
        "artifact_id": _hash_id("GEC", seed),
        "source_failure_artifact_id": source_failure_artifact_id,
        "trace_id": trace_id,
        "run_id": run_id,
        "reason_code": reason_code,
        "scenario_name": _scenario_name(failure_type, reason_code),
        "scenario_description": scenario_description,
        "input_conditions": input_conditions,
        "expected_outcome": _expected_outcome(failure_type, reason_code),
        "expected_reason_code": expected_reason_code,
        "replay_required": True,
        "determinism_requirements": [
            "canonical_json_hash_id",
            "bounded_expected_outcome",
            "reason_code_linked_to_source_failure",
            "fixture_replay_inputs_required",
        ],
        "created_at": _as_nonempty_string(failure_record.get("timestamp"), "1970-01-01T00:00:00Z"),
    }

    if normalized:
        generated_eval_case["reason_code_normalization"] = {
            "normalized_from_reason_code": reason_code,
            "normalized_to_reason_code": normalized,
        }

    Draft202012Validator(load_schema("generated_eval_case")).validate(generated_eval_case)
    return generated_eval_case


def admit_generated_eval_case(
    generated_eval_case: Dict[str, Any],
    *,
    source_failure_record: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Validate generated_eval_case for fail-closed admission."""

    denial_reasons: List[str] = []

    required_fields = [
        "artifact_type",
        "artifact_id",
        "source_failure_artifact_id",
        "trace_id",
        "run_id",
        "reason_code",
        "scenario_name",
        "scenario_description",
        "input_conditions",
        "expected_outcome",
        "expected_reason_code",
        "replay_required",
        "determinism_requirements",
        "created_at",
    ]

    for field in required_fields:
        value = generated_eval_case.get(field)
        if value in (None, ""):
            denial_reasons.append(f"missing_required_field:{field}")

    if generated_eval_case.get("artifact_type") != "generated_eval_case":
        denial_reasons.append("invalid_artifact_type")

    if not isinstance(generated_eval_case.get("determinism_requirements"), list) or not generated_eval_case.get(
        "determinism_requirements"
    ):
        denial_reasons.append("non_deterministic_eval_case")

    expected_outcome = _as_nonempty_string(generated_eval_case.get("expected_outcome"))
    if not expected_outcome:
        denial_reasons.append("missing_expected_outcome")

    reason_code = _as_nonempty_string(generated_eval_case.get("reason_code"))
    expected_reason_code = _as_nonempty_string(generated_eval_case.get("expected_reason_code"))

    normalization = generated_eval_case.get("reason_code_normalization")
    has_normalization = isinstance(normalization, dict) and _as_nonempty_string(
        normalization.get("normalized_from_reason_code")
    )
    if reason_code and expected_reason_code and reason_code != expected_reason_code and not has_normalization:
        denial_reasons.append("missing_reason_code_linkage")

    source_failure_artifact_id = _as_nonempty_string(generated_eval_case.get("source_failure_artifact_id"))
    if not source_failure_artifact_id:
        denial_reasons.append("missing_source_failure_artifact_id")

    input_conditions = generated_eval_case.get("input_conditions")
    if not isinstance(input_conditions, dict):
        denial_reasons.append("input_conditions_not_object")
        input_conditions = {}

    if generated_eval_case.get("replay_required") is True:
        stage = _as_nonempty_string(input_conditions.get("stage"))
        has_replay_material = bool(stage and (input_conditions.get("failed_evals") or input_conditions.get("missing_artifacts")))
        if not has_replay_material:
            denial_reasons.append("insufficient_replay_information")

    if isinstance(source_failure_record, dict):
        source_id = _as_nonempty_string(source_failure_record.get("artifact_id"))
        if source_id and source_id != source_failure_artifact_id:
            denial_reasons.append("source_failure_artifact_id_mismatch")

    admitted = len(denial_reasons) == 0

    admission_record = {
        "artifact_type": "generated_eval_admission_record",
        "artifact_id": _hash_id(
            "GEA",
            {
                "generated_eval_artifact_id": _as_nonempty_string(generated_eval_case.get("artifact_id"), "missing:artifact_id"),
                "source_failure_artifact_id": source_failure_artifact_id,
                "denial_reasons": sorted(denial_reasons),
            },
        ),
        "generated_eval_artifact_id": _as_nonempty_string(generated_eval_case.get("artifact_id"), "missing:artifact_id"),
        "source_failure_artifact_id": source_failure_artifact_id or "missing:source_failure_artifact_id",
        "admitted": admitted,
        "denial_reasons": sorted(set(denial_reasons)),
        "created_at": _as_nonempty_string(generated_eval_case.get("created_at"), "1970-01-01T00:00:00Z"),
    }

    Draft202012Validator(load_schema("generated_eval_admission_record")).validate(admission_record)
    return admission_record


def generate_and_admit_failure_eval(
    failure_record: Dict[str, Any],
    *,
    normalized_reason_code: str | None = None,
) -> Dict[str, Dict[str, Any]]:
    """Thin integration surface returning both generated eval case and admission output."""

    generated_eval_case = generate_eval_case_from_failure_record(
        failure_record,
        normalized_reason_code=normalized_reason_code,
    )
    admission = admit_generated_eval_case(generated_eval_case, source_failure_record=failure_record)
    return {
        "generated_eval_case": generated_eval_case,
        "generated_eval_admission_record": admission,
    }
