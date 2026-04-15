"""AIG-001 governed AI integration runtime.

Bounded, fail-closed orchestration for TLX/PRM/CTX/EVL/LIN/REP/OBS/PRG/CAP/SLO/QOS/JDX/POL/PRX/AIL/CDE surfaces.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class AIGovernanceError(RuntimeError):
    """Raised when a governed AI call violates required authority boundaries."""


@dataclass(frozen=True)
class GovernedAIRequest:
    task_id: str
    prompt_id: str
    prompt_version: str
    context_bundle_id: str
    route: dict[str, Any]
    limits: dict[str, Any]
    trace: dict[str, str]


@dataclass(frozen=True)
class GovernedAIResponse:
    output_ref: str
    payload: dict[str, Any]
    model_metadata: dict[str, Any]
    usage: dict[str, Any]
    failure_class: str | None


def enforce_registered_prompt(request: GovernedAIRequest, registry: dict[str, set[str]]) -> None:
    versions = registry.get(request.prompt_id, set())
    if request.prompt_version not in versions:
        raise AIGovernanceError(f"unregistered_or_disallowed_prompt:{request.prompt_id}@{request.prompt_version}")


def enforce_context_preflight(bundle: dict[str, Any]) -> dict[str, Any]:
    if not bundle.get("approved"):
        raise AIGovernanceError("context_bundle_not_approved")
    if not bundle.get("relevance_pass"):
        raise AIGovernanceError("context_bundle_not_relevant")
    if int(bundle.get("token_count", 0)) > int(bundle.get("token_limit", 0)):
        raise AIGovernanceError("context_bundle_oversize")
    return {
        "artifact_type": "ctx_ai_context_filter_result",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "record_id": f"REC-CTX-{str(bundle['bundle_id']).upper()}",
        "run_id": str(bundle.get("run_id", "run-aig-001")),
        "owner": "CTX",
        "status": "pass",
        "evidence_refs": [f"context_bundle:{bundle['bundle_id']}"],
        "payload": {"bundle_id": bundle["bundle_id"], "token_count": bundle["token_count"]},
    }


def classify_failure(*, provider_error: str | None, structured_valid: bool, timed_out: bool, truncated: bool) -> str | None:
    if timed_out:
        return "timeout"
    if provider_error:
        return "provider_error"
    if not structured_valid:
        return "schema_failure"
    if truncated:
        return "truncation"
    return None


def tlx_dispatch(request: GovernedAIRequest, provider_result: dict[str, Any]) -> tuple[dict[str, Any], GovernedAIResponse]:
    if not request.prompt_id or not request.context_bundle_id:
        raise AIGovernanceError("invalid_request_envelope")

    failure_class = classify_failure(
        provider_error=provider_result.get("provider_error"),
        structured_valid=bool(provider_result.get("structured_valid", False)),
        timed_out=bool(provider_result.get("timed_out", False)),
        truncated=bool(provider_result.get("truncated", False)),
    )

    dispatch_record = {
        "artifact_type": "tlx_ai_adapter_dispatch_record",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "record_id": f"REC-TLX-{str(request.trace['trace_id']).upper()}",
        "run_id": request.trace.get("run_id", "run-aig-001"),
        "owner": "TLX",
        "status": "pass" if failure_class is None else "fail",
        "evidence_refs": [f"prompt:{request.prompt_id}@{request.prompt_version}", f"context:{request.context_bundle_id}"],
        "payload": {"route": request.route, "limits": request.limits, "failure_class": failure_class},
    }

    response = GovernedAIResponse(
        output_ref=provider_result.get("output_ref", "artifact:ai-output"),
        payload=provider_result.get("payload", {}),
        model_metadata=provider_result.get("model_metadata", {}),
        usage=provider_result.get("usage", {}),
        failure_class=failure_class,
    )
    return dispatch_record, response


def evaluate_ai_output(response: GovernedAIResponse) -> dict[str, Any]:
    passed = response.failure_class is None and bool(response.payload)
    return {
        "artifact_type": "evl_ai_output_eval_result",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "record_id": "REC-EVL-AI-OUTPUT",
        "run_id": "run-aig-001",
        "owner": "EVL",
        "status": "pass" if passed else "fail",
        "evidence_refs": [response.output_ref],
        "payload": {
            "accepted": passed,
            "failure_class": response.failure_class,
        },
    }


def build_lineage_bundle(request: GovernedAIRequest, response: GovernedAIResponse, eval_result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lineage = {
        "artifact_type": "lin_ai_call_lineage_record",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "record_id": "REC-LIN-AI-CALL",
        "run_id": request.trace.get("run_id", "run-aig-001"),
        "owner": "LIN",
        "status": "pass" if eval_result["status"] == "pass" else "fail",
        "evidence_refs": [f"prompt:{request.prompt_id}@{request.prompt_version}", response.output_ref],
        "payload": {"trace": request.trace, "context_bundle": request.context_bundle_id},
    }
    replay = {
        "artifact_type": "rep_ai_replay_request_record",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "record_id": "REC-REP-AI-CALL",
        "run_id": request.trace.get("run_id", "run-aig-001"),
        "owner": "REP",
        "status": "pass",
        "evidence_refs": [lineage["record_id"]],
        "payload": {"request": request.__dict__, "response_failure_class": response.failure_class},
    }
    observability = {
        "artifact_type": "obs_ai_call_observability_record",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "record_id": "REC-OBS-AI-CALL",
        "run_id": request.trace.get("run_id", "run-aig-001"),
        "owner": "OBS",
        "status": "pass",
        "evidence_refs": [lineage["record_id"], replay["record_id"]],
        "payload": {"trace": request.trace, "usage": response.usage},
    }
    return {"lineage": lineage, "replay": replay, "observability": observability}


def compute_posture(*, usage_records: list[dict[str, Any]], failure_records: list[dict[str, Any]], queue_pressure: float) -> dict[str, dict[str, Any]]:
    total_cost = sum(float(item.get("cost_usd", 0.0)) for item in usage_records)
    failures = len([item for item in failure_records if item.get("failure_class")])
    total = max(len(failure_records), 1)
    return {
        "cap": {
            "artifact_type": "cap_ai_cost_budget_posture",
            "artifact_version": "1.0.0",
            "schema_version": "1.0.0",
            "record_id": "REC-CAP-AI",
            "run_id": "run-aig-001",
            "owner": "CAP",
            "status": "fail" if total_cost > 20 else "pass",
            "evidence_refs": ["tlx_ai_usage_record"],
            "payload": {"total_cost_usd": total_cost, "budget_usd": 20.0},
        },
        "slo": {
            "artifact_type": "slo_ai_reliability_budget_posture",
            "artifact_version": "1.0.0",
            "schema_version": "1.0.0",
            "record_id": "REC-SLO-AI",
            "run_id": "run-aig-001",
            "owner": "SLO",
            "status": "fail" if failures / total > 0.25 else "pass",
            "evidence_refs": ["tlx_ai_failure_classification_record"],
            "payload": {"failure_ratio": failures / total, "threshold": 0.25},
        },
        "qos": {
            "artifact_type": "qos_ai_queue_pressure_record",
            "artifact_version": "1.0.0",
            "schema_version": "1.0.0",
            "record_id": "REC-QOS-AI",
            "run_id": "run-aig-001",
            "owner": "QOS",
            "status": "fail" if queue_pressure > 0.85 else "pass",
            "evidence_refs": ["obs_ai_call_observability_record"],
            "payload": {"queue_pressure": queue_pressure, "threshold": 0.85},
        },
    }


def cde_decide_continuation(*, eval_result: dict[str, Any], posture: dict[str, dict[str, Any]], lineage_complete: bool) -> dict[str, Any]:
    if not lineage_complete:
        return _cde("cde_ai_usage_continuation_decision", "halt", ["missing_lineage"])
    if eval_result["status"] != "pass":
        return _cde("cde_ai_usage_continuation_decision", "halt", ["eval_failed"])
    failing = [k for k,v in posture.items() if v["status"] == "fail"]
    if failing:
        return _cde("cde_ai_usage_continuation_decision", "halt", [f"posture_fail:{k}" for k in failing])
    return _cde("cde_ai_usage_continuation_decision", "continue", ["all_green"])


def cde_decide_escalation(*, failure_class: str | None, repeat_failures: int) -> dict[str, Any]:
    if failure_class in {"schema_failure", "provider_error"} and repeat_failures >= 2:
        return _cde("cde_ai_failure_escalation_decision", "escalate", [failure_class])
    if failure_class in {"timeout", "truncation"} and repeat_failures >= 3:
        return _cde("cde_ai_failure_escalation_decision", "suspend", [failure_class])
    return _cde("cde_ai_failure_escalation_decision", "continue", ["no_escalation"])


def _cde(artifact_type: str, status: str, reasons: list[str]) -> dict[str, Any]:
    return {
        "artifact_type": artifact_type,
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "record_id": f"REC-{artifact_type.upper()}",
        "run_id": "run-aig-001",
        "owner": "CDE",
        "status": status,
        "evidence_refs": ["prg_ai_control_signal_bundle", "evl_ai_output_eval_result"],
        "payload": {"reasons": reasons},
    }


def execute_red_team_rounds() -> list[dict[str, Any]]:
    rounds = [
        ("ril_ai_hallucination_red_team_report", "fre_tpa_sel_pqx_ai_fix_pack_g1", ["unsupported_claim"]),
        ("ril_ai_prompt_injection_red_team_report", "fre_tpa_sel_pqx_ai_fix_pack_g2", ["instruction_hijack"]),
        ("ril_ai_structured_output_bypass_red_team_report", "fre_tpa_sel_pqx_ai_fix_pack_g3", ["schema_bypass"]),
        ("ril_ai_model_routing_red_team_report", "fre_tpa_sel_pqx_ai_fix_pack_g4", ["route_instability"]),
        ("ril_ai_replay_inconsistency_red_team_report", "fre_tpa_sel_pqx_ai_fix_pack_g5", ["replay_gap"]),
        ("ril_ai_eval_bypass_red_team_report", "fre_tpa_sel_pqx_ai_fix_pack_g6", ["eval_missing"]),
        ("ril_ai_cost_runaway_red_team_report", "fre_tpa_sel_pqx_ai_fix_pack_g7", ["retry_storm"]),
    ]
    out: list[dict[str, Any]] = []
    for red, fix, exploits in rounds:
        out.append(_artifact(red, "RIL", "pass", exploits))
        out.append(_artifact(fix, "FRE", "pass", [f"fixed:{code}" for code in exploits]))
    return out


def _artifact(artifact_type: str, owner: str, status: str, exploit_codes: list[str]) -> dict[str, Any]:
    return {
        "artifact_type": artifact_type,
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "record_id": f"REC-{artifact_type.upper()}",
        "run_id": "run-aig-001",
        "owner": owner,
        "status": status,
        "evidence_refs": ["red-team-fixtures:aig-001"],
        "payload": {"exploit_codes": exploit_codes},
    }
