"""Canonical stage-contract loader and deterministic transition readiness evaluator."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from spectrum_systems.contracts import load_schema


@dataclass(frozen=True)
class StageTransitionReadinessResult:
    ready_to_advance: bool
    recommended_state: str
    reason_codes: tuple[str, ...]
    missing_inputs: tuple[str, ...]
    missing_outputs: tuple[str, ...]
    missing_evals: tuple[str, ...]
    failed_evals: tuple[str, ...]
    indeterminate_evals: tuple[str, ...]
    budget_failures: tuple[str, ...]
    trace_failures: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ready_to_advance": self.ready_to_advance,
            "recommended_state": self.recommended_state,
            "reason_codes": list(self.reason_codes),
            "missing_inputs": list(self.missing_inputs),
            "missing_outputs": list(self.missing_outputs),
            "missing_evals": list(self.missing_evals),
            "failed_evals": list(self.failed_evals),
            "indeterminate_evals": list(self.indeterminate_evals),
            "budget_failures": list(self.budget_failures),
            "trace_failures": list(self.trace_failures),
        }


def _schema_validator() -> Draft202012Validator:
    return Draft202012Validator(load_schema("stage_contract"))


def validate_stage_contract(payload: Mapping[str, Any]) -> None:
    errors = sorted(_schema_validator().iter_errors(dict(payload)), key=lambda e: str(list(e.absolute_path)))
    if errors:
        raise ValidationError("; ".join(error.message for error in errors))


def load_stage_contract(path: str | Path) -> dict[str, Any]:
    contract_path = Path(path)
    payload = json.loads(contract_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValidationError("stage contract payload must be a JSON object")
    validate_stage_contract(payload)
    return payload


def _count_by_type(entries: Mapping[str, int] | None) -> dict[str, int]:
    normalized: dict[str, int] = {}
    for artifact_type, count in (entries or {}).items():
        key = str(artifact_type)
        try:
            value = int(count)
        except (TypeError, ValueError):
            value = 0
        normalized[key] = max(0, value)
    return normalized


def _norm_eval_status(status: Any) -> str:
    return str(status or "").strip().lower()


def evaluate_stage_transition_readiness(
    *,
    contract_payload: Mapping[str, Any],
    present_input_artifacts: Mapping[str, int] | None,
    present_output_artifacts: Mapping[str, int] | None,
    eval_status_map: Mapping[str, str] | None,
    trace_complete: bool,
    policy_violation: bool,
    budget_status: Mapping[str, bool] | None,
) -> StageTransitionReadinessResult:
    validate_stage_contract(contract_payload)
    rules = dict(contract_payload.get("transition_rules") or {})

    missing_inputs: list[str] = []
    missing_outputs: list[str] = []
    missing_evals: list[str] = []
    failed_evals: list[str] = []
    indeterminate_evals: list[str] = []
    budget_failures: list[str] = []
    trace_failures: list[str] = []
    reason_codes: set[str] = set()

    inputs = _count_by_type(present_input_artifacts)
    outputs = _count_by_type(present_output_artifacts)

    if rules.get("advance_requires_all_required_inputs", True):
        for descriptor in contract_payload.get("inputs", []):
            if not isinstance(descriptor, dict):
                continue
            if descriptor.get("required") is not True:
                continue
            artifact_type = str(descriptor.get("artifact_type") or "")
            min_count = int(descriptor.get("min_count") or 1)
            if artifact_type and inputs.get(artifact_type, 0) < min_count:
                missing_inputs.append(artifact_type)
                reason_codes.add("STAGE_CONTRACT_REQUIRED_INPUT_MISSING")

    if rules.get("advance_requires_all_required_outputs", True):
        for descriptor in contract_payload.get("outputs_required", []):
            if not isinstance(descriptor, dict):
                continue
            artifact_type = str(descriptor.get("artifact_type") or "")
            min_count = int(descriptor.get("min_count") or 1)
            if artifact_type and outputs.get(artifact_type, 0) < min_count:
                missing_outputs.append(artifact_type)
                reason_codes.add("STAGE_CONTRACT_REQUIRED_OUTPUT_MISSING")

    if rules.get("advance_requires_all_required_evals", True):
        eval_status_map = dict(eval_status_map or {})
        indeterminate_behavior = str(rules.get("indeterminate_eval_behavior") or "freeze").lower()
        for eval_type in contract_payload.get("verification", {}).get("required_eval_types", []):
            status = _norm_eval_status(eval_status_map.get(str(eval_type)))
            if status in {"", "missing"}:
                missing_evals.append(str(eval_type))
                reason_codes.add("STAGE_CONTRACT_MISSING_REQUIRED_EVAL")
            elif status in {"fail", "failed"}:
                failed_evals.append(str(eval_type))
                reason_codes.add("STAGE_CONTRACT_REQUIRED_EVAL_FAILED")
            elif status in {"indeterminate", "unknown", "pending"}:
                reason_codes.add("STAGE_CONTRACT_REQUIRED_EVAL_INDETERMINATE")
                indeterminate_evals.append(str(eval_type))
                if indeterminate_behavior == "block":
                    failed_evals.append(str(eval_type))

    if rules.get("advance_requires_trace_completeness", True) and not trace_complete:
        trace_failures.append("trace_incomplete")
        reason_codes.add("STAGE_CONTRACT_TRACE_INCOMPLETE")

    if policy_violation:
        reason_codes.add("STAGE_CONTRACT_POLICY_VIOLATION")

    for budget_key, exhausted in sorted((budget_status or {}).items()):
        if exhausted:
            budget_failures.append(str(budget_key))
    if budget_failures:
        reason_codes.add("STAGE_CONTRACT_BUDGET_EXHAUSTED")

    indeterminate_behavior = str(rules.get("indeterminate_eval_behavior") or "freeze").lower()
    hard_block = bool(missing_inputs or missing_outputs or missing_evals or failed_evals or trace_failures or policy_violation)
    indeterminate_freeze = bool(indeterminate_evals) and indeterminate_behavior != "block" and not hard_block
    freeze_only = bool(budget_failures) and not hard_block

    if hard_block:
        recommended_state = "block"
        ready = False
    elif indeterminate_freeze:
        ready = False
        recommended_state = "freeze"
    elif freeze_only:
        ready = False
        budget_behavior = str(rules.get("budget_exhausted_behavior") or "freeze").lower()
        recommended_state = "block" if budget_behavior == "block" else "freeze"
    else:
        ready = True
        recommended_state = "advance"

    return StageTransitionReadinessResult(
        ready_to_advance=ready,
        recommended_state=recommended_state,
        reason_codes=tuple(sorted(reason_codes)),
        missing_inputs=tuple(sorted(set(missing_inputs))),
        missing_outputs=tuple(sorted(set(missing_outputs))),
        missing_evals=tuple(sorted(set(missing_evals))),
        failed_evals=tuple(sorted(set(failed_evals))),
        indeterminate_evals=tuple(sorted(set(indeterminate_evals))),
        budget_failures=tuple(sorted(set(budget_failures))),
        trace_failures=tuple(sorted(set(trace_failures))),
    )
