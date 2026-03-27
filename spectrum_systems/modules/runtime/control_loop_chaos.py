"""Deterministic chaos scenario runner for the evaluation control loop (SF-12)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.control_loop import (
    ControlLoopError,
    build_trace_context_from_replay_artifact,
    run_control_loop,
)
from spectrum_systems.modules.runtime.evaluation_control import EvaluationControlError
from spectrum_systems.utils.artifact_envelope import build_artifact_envelope

SCHEMA_VERSION = "1.0.0"


def _validate(instance: dict[str, Any], schema_name: str) -> None:
    Draft202012Validator(load_schema(schema_name), format_checker=FormatChecker()).validate(instance)


class ControlLoopChaosError(Exception):
    """Raised when chaos scenario definitions are invalid."""


@dataclass(frozen=True)
class ScenarioExpectation:
    scenario_id: str
    expected_status: str
    expected_response: str
    expected_decision: str
    expected_reasons: list[str]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _normalize_reasons(*, rationale_code: str | None, triggered_signals: list[Any] | None) -> list[str]:
    reasons: list[str] = []
    if isinstance(rationale_code, str) and rationale_code:
        reasons.append(rationale_code)
    if isinstance(triggered_signals, list):
        reasons.extend(str(item) for item in triggered_signals if str(item))
    return sorted(set(reasons))


def _validate_scenario_shape(scenario: dict[str, Any]) -> None:
    required = ("scenario_id", "description", "expected_status", "expected_response", "expected_decision")
    missing = [field for field in required if field not in scenario]
    if missing:
        raise ControlLoopChaosError(f"scenario missing required fields {missing}: {scenario}")
    expected_decision = scenario.get("expected_decision")
    if expected_decision not in {"allow", "deny", "require_review"}:
        raise ControlLoopChaosError(
            f"scenario '{scenario.get('scenario_id')}' has invalid expected_decision: {expected_decision!r}"
        )


def load_scenarios(path: Path) -> list[dict[str, Any]]:
    payload = _load_json(path)
    if not isinstance(payload, list):
        raise ControlLoopChaosError("scenario file must contain a JSON array")

    seen_ids: set[str] = set()
    scenarios: list[dict[str, Any]] = []
    for entry in payload:
        if not isinstance(entry, dict):
            raise ControlLoopChaosError("every scenario must be a JSON object")
        _validate_scenario_shape(entry)
        scenario_id = str(entry["scenario_id"]).strip()
        if not scenario_id:
            raise ControlLoopChaosError("scenario_id must be non-empty")
        if scenario_id in seen_ids:
            raise ControlLoopChaosError(f"duplicate scenario_id: {scenario_id}")
        seen_ids.add(scenario_id)
        scenarios.append(entry)
    return scenarios


def _evaluate_once(artifact: Any) -> dict[str, Any]:
    try:
        trace_context = build_trace_context_from_replay_artifact(
            artifact,
            base_context={"trigger": "control_loop_chaos"},
        )
        result = run_control_loop(artifact, trace_context)
        decision = result["evaluation_control_decision"]
        actual_status = decision.get("system_status")
        actual_response = decision.get("system_response")
        actual_decision = decision.get("decision")
        if actual_status not in {"healthy", "warning", "exhausted", "blocked"}:
            raise ValueError("control loop returned invalid status")
        if actual_response not in {"allow", "warn", "freeze", "block"}:
            raise ValueError("control loop returned invalid response")
        if actual_decision not in {"allow", "deny", "require_review"}:
            raise ValueError("control loop returned invalid decision")
        return {
            "actual_status": actual_status,
            "actual_response": actual_response,
            "actual_decision": actual_decision,
            "reasons": _normalize_reasons(
                rationale_code=decision.get("rationale_code"),
                triggered_signals=decision.get("triggered_signals"),
            ),
            "decision_id": decision.get("decision_id"),
            "error": None,
        }
    except (ControlLoopError, EvaluationControlError, ValueError, TypeError, KeyError, AttributeError, Exception) as exc:
        return {
            "actual_status": "blocked",
            "actual_response": "block",
            "actual_decision": "deny",
            "reasons": ["control_loop_error"],
            "decision_id": None,
            "error": str(exc),
        }


def _build_expectation(scenario: dict[str, Any]) -> ScenarioExpectation:
    expected_reasons_raw = scenario.get("expected_reasons") or []
    if not isinstance(expected_reasons_raw, list):
        raise ControlLoopChaosError(
            f"scenario '{scenario['scenario_id']}' expected_reasons must be an array"
        )
    return ScenarioExpectation(
        scenario_id=str(scenario["scenario_id"]),
        expected_status=str(scenario["expected_status"]),
        expected_response=str(scenario["expected_response"]),
        expected_decision=str(scenario["expected_decision"]),
        expected_reasons=[str(item) for item in expected_reasons_raw if str(item)],
    )


def _is_match(expectation: ScenarioExpectation, actual: dict[str, Any]) -> tuple[bool, list[str]]:
    mismatches: list[str] = []
    if actual["actual_status"] != expectation.expected_status:
        mismatches.append("status")
    if actual["actual_response"] != expectation.expected_response:
        mismatches.append("response")
    if actual["actual_decision"] != expectation.expected_decision:
        mismatches.append("decision")

    actual_reasons = set(actual.get("reasons") or [])
    expected_reasons = set(expectation.expected_reasons)
    if actual_reasons != expected_reasons:
        mismatches.append("reasons")

    return not mismatches, mismatches


def run_chaos_scenarios(
    *,
    scenarios: list[dict[str, Any]],
    chaos_run_id: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    run_id = chaos_run_id or f"chaos-{hashlib.sha256(json.dumps(scenarios, sort_keys=True).encode('utf-8')).hexdigest()[:12]}"
    run_timestamp = timestamp or _utc_now()

    scenario_results: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []

    for scenario in scenarios:
        expectation = _build_expectation(scenario)
        actual = _evaluate_once(scenario.get("artifact"))

        deterministic_match = True
        deterministic_details: str | None = None
        if bool(scenario.get("check_repeatability", True)):
            second = _evaluate_once(scenario.get("artifact"))
            deterministic_match = (
                actual["actual_status"] == second["actual_status"]
                and actual["actual_response"] == second["actual_response"]
                and actual["actual_decision"] == second["actual_decision"]
                and actual["reasons"] == second["reasons"]
                and actual.get("decision_id") == second.get("decision_id")
            )
            if not deterministic_match:
                deterministic_details = (
                    f"first={actual['actual_status']}/{actual['actual_response']}/{actual['actual_decision']} "
                    f"second={second['actual_status']}/{second['actual_response']}/{second['actual_decision']}"
                )

        matched, mismatch_fields = _is_match(expectation, actual)
        if not deterministic_match:
            matched = False
            mismatch_fields = [*mismatch_fields, "determinism"]

        notes = str(scenario.get("notes") or "")
        if actual.get("error"):
            notes = f"{notes}; error={actual['error']}" if notes else f"error={actual['error']}"
        if deterministic_details:
            notes = (
                f"{notes}; repeatability_mismatch={deterministic_details}"
                if notes
                else f"repeatability_mismatch={deterministic_details}"
            )

        scenario_result = {
            "scenario_id": expectation.scenario_id,
            "category": str(scenario.get("category") or "uncategorized"),
            "description": str(scenario.get("description") or ""),
            "expected_status": expectation.expected_status,
            "actual_status": actual["actual_status"],
            "expected_response": expectation.expected_response,
            "actual_response": actual["actual_response"],
            "expected_decision": expectation.expected_decision,
            "actual_decision": actual["actual_decision"],
            "matched": matched,
            "mismatch_fields": mismatch_fields,
            "reasons": actual["reasons"],
            "notes": notes,
        }
        scenario_results.append(scenario_result)

        if not matched:
            mismatches.append(
                {
                    "scenario_id": expectation.scenario_id,
                    "mismatch_fields": mismatch_fields,
                    "expected_status": expectation.expected_status,
                    "actual_status": actual["actual_status"],
                    "expected_response": expectation.expected_response,
                    "actual_response": actual["actual_response"],
                    "expected_decision": expectation.expected_decision,
                    "actual_decision": actual["actual_decision"],
                    "expected_reasons": expectation.expected_reasons,
                    "actual_reasons": actual["reasons"],
                    "notes": notes,
                }
            )

    pass_count = sum(1 for item in scenario_results if item["matched"])
    fail_count = len(scenario_results) - pass_count

    envelope = build_artifact_envelope(
        artifact_id=run_id,
        timestamp=run_timestamp,
        schema_version=SCHEMA_VERSION,
        primary_trace_ref=run_id,
        related_trace_refs=[],
    )
    summary = {
        "artifact_type": "evaluation_control_chaos_summary",
        **envelope,
        "chaos_run_id": run_id,
        "scenario_count": len(scenario_results),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "mismatches": mismatches,
        "scenario_results": scenario_results,
    }
    _validate(summary, "evaluation_control_chaos_summary")
    return summary


def run_chaos_scenarios_from_file(*, scenarios_path: Path, output_path: Path) -> dict[str, Any]:
    scenarios = load_scenarios(scenarios_path)
    summary = run_chaos_scenarios(scenarios=scenarios)
    _write_json(output_path, summary)
    return summary
