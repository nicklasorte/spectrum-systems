"""VAL-01 trust-hardening validation for promotion gate attack scenarios."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.evaluation_enforcement_bridge import (
    EnforcementBridgeError,
    InvalidDecisionError,
    run_enforcement_bridge,
)

_REQUIRED_REFS = (
    "valid_done_certification_ref",
    "enforcement_input_ref",
)


class PromotionGateAttackError(ValueError):
    """Raised when promotion gate attack input refs are invalid."""


def _load_json(path_value: str, *, label: str) -> Dict[str, Any]:
    path = Path(path_value)
    if not path.is_file():
        raise PromotionGateAttackError(f"{label} file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PromotionGateAttackError(f"{label} is not valid JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise PromotionGateAttackError(f"{label} must be a JSON object: {path}")
    return payload


def _validate_schema(instance: Dict[str, Any], schema_name: str, *, label: str) -> None:
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise PromotionGateAttackError(f"{label} failed schema validation ({schema_name}): {details}")


def _require_refs(input_refs: Dict[str, Any]) -> Dict[str, str]:
    if not isinstance(input_refs, dict):
        raise PromotionGateAttackError("input_refs must be an object")
    refs: Dict[str, str] = {}
    for key in _REQUIRED_REFS:
        value = input_refs.get(key)
        if not isinstance(value, str) or not value.strip():
            raise PromotionGateAttackError(f"missing required input ref: {key}")
        refs[key] = value

    for key in (
        "invalid_done_certification_ref",
        "failed_done_certification_ref",
        "malformed_done_certification_ref",
        "missing_done_certification_ref",
        "policy_ref",
    ):
        value = input_refs.get(key)
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip():
            raise PromotionGateAttackError(f"{key} must be a non-empty string when provided")
        refs[key] = value
    return refs


def _stable_hash(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _write_json(path: Path, payload: Dict[str, Any]) -> str:
    path.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    return str(path)


def _evaluate_case(
    *,
    case_id: str,
    case_type: str,
    done_certification_path: Optional[str],
    enforcement_input_ref: str,
) -> Dict[str, Any]:
    expected_outcome = "block"
    context: Dict[str, Any] = {"enforcement_scope": "promotion"}
    if done_certification_path is not None:
        context["done_certification_path"] = done_certification_path

    enforcement_outcome: Optional[Dict[str, Any]] = None
    blocking_reason = ""
    actual_outcome = "ambiguous"
    try:
        enforcement_outcome = run_enforcement_bridge(enforcement_input_ref, context=context)
        if bool(enforcement_outcome.get("allowed_to_proceed")):
            actual_outcome = "allow"
        else:
            actual_outcome = "block"
            blocking_reason = str(enforcement_outcome.get("certification_gate", {}).get("block_reason") or "")
            if not blocking_reason:
                reasons = enforcement_outcome.get("reasons") or []
                if isinstance(reasons, list) and reasons:
                    blocking_reason = str(reasons[-1])
    except (EnforcementBridgeError, InvalidDecisionError) as exc:
        actual_outcome = "block"
        blocking_reason = str(exc)
    except Exception as exc:  # noqa: BLE001
        actual_outcome = "unhandled_exception"
        blocking_reason = f"{type(exc).__name__}: {exc}"

    if not str(blocking_reason).strip():
        if actual_outcome == "allow":
            blocking_reason = "bypass detected: enforcement returned allow for attack case"
        elif actual_outcome == "warn":
            blocking_reason = "bypass detected: enforcement returned warn without hard block"
        elif actual_outcome == "ambiguous":
            blocking_reason = "ambiguous enforcement outcome: no explicit block signal"
        elif actual_outcome == "unhandled_exception":
            blocking_reason = "unhandled exception during enforcement attack execution"
        else:
            blocking_reason = "blocked without explicit reason"

    passed = actual_outcome == expected_outcome and bool(str(blocking_reason).strip())

    return {
        "case_id": case_id,
        "case_type": case_type,
        "expected_outcome": expected_outcome,
        "actual_outcome": actual_outcome,
        "passed": passed,
        "blocking_reason": blocking_reason,
        "enforcement_outcome": enforcement_outcome,
    }


def _prepare_generated_paths(work_dir: Path, valid_certification: Dict[str, Any]) -> Tuple[str, str, str]:
    incomplete = dict(valid_certification)
    incomplete["check_results"] = dict(valid_certification["check_results"])
    incomplete["check_results"]["contracts"] = {"passed": False, "details": ["missing mandatory contract proof"]}
    incomplete_path = _write_json(work_dir / "incomplete_done_certification.json", incomplete)

    mismatched = dict(valid_certification)
    mismatched["trace_id"] = "trace-mismatched-attack"
    mismatched_path = _write_json(work_dir / "mismatched_trace_done_certification.json", mismatched)

    corrupted = dict(valid_certification)
    corrupted["system_response"] = "allow"
    corrupted["final_status"] = "PASSED"
    corrupted["check_results"] = dict(valid_certification["check_results"])
    corrupted["check_results"]["fail_closed"] = {
        "passed": False,
        "details": ["tampered payload indicates fail_closed did not pass"],
    }
    corrupted_path = _write_json(work_dir / "corrupted_done_certification.json", corrupted)

    return incomplete_path, mismatched_path, corrupted_path


def run_promotion_gate_attack(input_refs: dict) -> dict:
    """Run VAL-01 attack scenarios against the real promotion enforcement boundary."""
    refs = _require_refs(input_refs)

    decision_payload = _load_json(refs["enforcement_input_ref"], label="enforcement_input")
    _validate_schema(decision_payload, "evaluation_budget_decision", label="enforcement_input")

    valid_certification = _load_json(refs["valid_done_certification_ref"], label="valid_done_certification")
    _validate_schema(valid_certification, "done_certification_record", label="valid_done_certification")

    work_dir = Path(tempfile.mkdtemp(prefix="promotion-gate-attack-"))

    malformed_path = refs.get("malformed_done_certification_ref")
    if malformed_path is None:
        malformed_path = str(work_dir / "malformed_done_certification.json")
        Path(malformed_path).write_text("{\"not\":\"schema\"", encoding="utf-8")

    failed_path = refs.get("failed_done_certification_ref")
    if failed_path is None:
        failed = dict(valid_certification)
        failed["final_status"] = "FAILED"
        failed["system_response"] = "block"
        failed["blocking_reasons"] = ["explicit failed certification"]
        failed_path = str(work_dir / "failed_done_certification.json")
        _write_json(Path(failed_path), failed)

    missing_path = refs.get("missing_done_certification_ref")
    if missing_path is None:
        missing_path = str(work_dir / "missing_done_certification.json")
        if Path(missing_path).exists():
            Path(missing_path).unlink()

    incomplete_path, mismatched_path, corrupted_path = _prepare_generated_paths(work_dir, valid_certification)

    attack_cases: List[Dict[str, Any]] = [
        _evaluate_case(
            case_id="VAL-01-A",
            case_type="missing_certification",
            done_certification_path=None,
            enforcement_input_ref=refs["enforcement_input_ref"],
        ),
        _evaluate_case(
            case_id="VAL-01-B",
            case_type="malformed_certification",
            done_certification_path=malformed_path,
            enforcement_input_ref=refs["enforcement_input_ref"],
        ),
        _evaluate_case(
            case_id="VAL-01-C",
            case_type="failed_certification",
            done_certification_path=failed_path,
            enforcement_input_ref=refs["enforcement_input_ref"],
        ),
        _evaluate_case(
            case_id="VAL-01-D",
            case_type="structurally_valid_but_incomplete_certification",
            done_certification_path=incomplete_path,
            enforcement_input_ref=refs["enforcement_input_ref"],
        ),
        _evaluate_case(
            case_id="VAL-01-E",
            case_type="mismatched_trace_certification",
            done_certification_path=mismatched_path,
            enforcement_input_ref=refs["enforcement_input_ref"],
        ),
        _evaluate_case(
            case_id="VAL-01-F",
            case_type="corrupted_certification_payload",
            done_certification_path=corrupted_path,
            enforcement_input_ref=refs["enforcement_input_ref"],
        ),
    ]

    blocked_cases = sum(1 for case in attack_cases if case["actual_outcome"] == "block")
    failed_cases = sum(1 for case in attack_cases if not case["passed"])

    bypass_detected = False
    for case in attack_cases:
        if case["actual_outcome"] in {"allow", "warn", "ambiguous", "unhandled_exception"}:
            bypass_detected = True
            break
        if not case["enforcement_outcome"] and case["actual_outcome"] != "block":
            bypass_detected = True
            break

    final_status = "PASSED" if (not bypass_detected and failed_cases == 0) else "FAILED"

    attack_run_id = _stable_hash(
        {
            "input_refs": refs,
            "decision_id": decision_payload.get("decision_id"),
            "trace_id": decision_payload.get("trace_id"),
            "cases": [
                {
                    "case_id": case["case_id"],
                    "actual_outcome": case["actual_outcome"],
                    "blocking_reason": case["blocking_reason"],
                }
                for case in attack_cases
            ],
        }
    )

    result = {
        "attack_run_id": attack_run_id,
        "timestamp": str(decision_payload.get("timestamp") or valid_certification.get("timestamp")),
        "target_boundary": "runtime.evaluation_enforcement_bridge:promotion_gate",
        "input_refs": refs,
        "attack_cases": [
            {
                "case_id": case["case_id"],
                "case_type": case["case_type"],
                "expected_outcome": case["expected_outcome"],
                "actual_outcome": case["actual_outcome"],
                "passed": case["passed"],
                "blocking_reason": case["blocking_reason"],
            }
            for case in attack_cases
        ],
        "summary": {
            "total_cases": len(attack_cases),
            "blocked_cases": blocked_cases,
            "failed_cases": failed_cases,
            "bypass_detected": bypass_detected,
        },
        "final_status": final_status,
        "trace_id": str(decision_payload.get("trace_id") or valid_certification.get("trace_id") or ""),
    }

    _validate_schema(result, "promotion_gate_attack_result", label="promotion_gate_attack_result")
    return result
