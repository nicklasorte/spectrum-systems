"""CL-25: Core loop proof — compact, reference-only proof artifact.

Composes the validators in this directory into one deterministic proof
artifact for a pass / block / freeze scenario. The proof is non-owning;
it does not decide, gate, or enforce. Canonical authority remains with
AEX, PQX, EVL, TPA, CDE, SEL.

The proof carries:

  * one primary canonical reason (selected by primary_reason_policy);
  * supporting reasons preserved alongside;
  * artifact refs for every stage;
  * the 5 transitions with per-transition status;
  * lineage / replay refs where applicable;
  * the allowed next action;
  * the terminal status (``pass | block | freeze``).
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from spectrum_systems.modules.governance.core_loop_action_mapping import (
    REASON_OK as ACTION_OK,
    validate_action_for_decision,
)
from spectrum_systems.modules.governance.core_loop_admission_minimality import (
    REASON_OK as ADMISSION_OK,
    validate_admission_packet,
)
from spectrum_systems.modules.governance.core_loop_contract import (
    CANONICAL_STAGE_ORDER,
    CANONICAL_TRANSITIONS,
    REASON_HANDOFF_MISSING_FIELD,
    REASON_HANDOFF_MISSING_REF,
    build_default_core_loop_contract,
    validate_handoff,
)
from spectrum_systems.modules.governance.core_loop_decision_input_contract import (
    REASON_OK as DECISION_OK,
    validate_decision_inputs,
    validate_decision_outcome,
)
from spectrum_systems.modules.governance.core_loop_execution_envelope import (
    REASON_OK as EXECUTION_OK,
    validate_execution_envelope,
)
from spectrum_systems.modules.governance.core_loop_policy_input_contract import (
    REASON_OK as POLICY_OK,
    validate_policy_inputs,
    validate_policy_result,
)
from spectrum_systems.modules.governance.core_loop_primary_reason import (
    select_primary_reason,
)
from spectrum_systems.modules.governance.core_loop_required_eval_resolver import (
    REASON_OK as EVAL_OK,
    resolve_required_evals,
)


class CoreLoopProofError(ValueError):
    """Raised on programmer-misuse (missing required ids)."""


def _stage_record(
    stage: str,
    artifact_ref: Optional[str],
    status: str,
    reason_code: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "stage": stage,
        "owner": stage,
        "artifact_ref": artifact_ref or None,
        "status": status,
        "reason_code": reason_code,
    }


def _transition_record(
    from_stage: str,
    to_stage: str,
    status: str,
    reason_code: Optional[str] = None,
    missing_handoff_fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "from_stage": from_stage,
        "to_stage": to_stage,
        "status": status,
        "reason_code": reason_code,
        "missing_handoff_fields": list(missing_handoff_fields or ()),
    }


def build_core_loop_proof(
    *,
    proof_id: str,
    trace_id: str,
    audit_timestamp: str,
    run_id: str = "",
    admission_packet: Optional[Mapping[str, Any]] = None,
    execution_envelope: Optional[Mapping[str, Any]] = None,
    eval_resolution_inputs: Optional[Mapping[str, Any]] = None,
    eval_summary_ref: Optional[str] = None,
    policy_inputs: Optional[Mapping[str, Any]] = None,
    policy_result: Optional[Mapping[str, Any]] = None,
    decision_inputs: Optional[Mapping[str, Any]] = None,
    decision_outcome: Optional[Mapping[str, Any]] = None,
    sel_action: Optional[Mapping[str, Any]] = None,
    lineage_chain_ref: Optional[str] = None,
    replay_record_ref: Optional[str] = None,
    contract: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a deterministic core_loop_proof artifact from stage inputs."""
    if not isinstance(proof_id, str) or not proof_id.strip():
        raise CoreLoopProofError("proof_id must be a non-empty string")
    if not isinstance(trace_id, str) or not trace_id.strip():
        raise CoreLoopProofError("trace_id must be a non-empty string")
    if not isinstance(audit_timestamp, str) or not audit_timestamp.strip():
        raise CoreLoopProofError("audit_timestamp must be a non-empty string")

    if contract is None:
        contract = build_default_core_loop_contract()

    findings: List[Dict[str, Any]] = []

    # ── AEX
    aex_status = "ok"
    aex_reason: Optional[str] = None
    if admission_packet is None:
        aex_status, aex_reason = "missing", "ADMISSION_MISSING"
        findings.append(
            {
                "reason_code": "ADMISSION_MISSING",
                "stage": "AEX",
                "detail": "admission_packet not supplied",
            }
        )
    else:
        aex_result = validate_admission_packet(admission_packet)
        if not aex_result["ok"]:
            aex_status, aex_reason = "failed", aex_result["primary_reason"]
            for v in aex_result["violations"]:
                findings.append({**v, "stage": "AEX"})

    aex_ref = (
        admission_packet.get("aex_admission_ref")
        if isinstance(admission_packet, Mapping)
        else None
    )

    # ── PQX
    pqx_status = "ok"
    pqx_reason: Optional[str] = None
    if execution_envelope is None:
        pqx_status, pqx_reason = "missing", "EXECUTION_ENVELOPE_MISSING"
        findings.append(
            {
                "reason_code": "EXECUTION_ENVELOPE_MISSING",
                "stage": "PQX",
                "detail": "execution_envelope not supplied",
            }
        )
    else:
        pqx_result = validate_execution_envelope(
            execution_envelope,
            expected_run_id=run_id or None,
            expected_trace_id=trace_id,
        )
        if not pqx_result["ok"]:
            pqx_status, pqx_reason = "failed", pqx_result["primary_reason"]
            for v in pqx_result["violations"]:
                findings.append({**v, "stage": "PQX"})
    pqx_ref = (
        next(iter(execution_envelope.get("output_refs") or ()), None)
        if isinstance(execution_envelope, Mapping)
        else None
    )

    # ── EVL
    evl_status = "ok"
    evl_reason: Optional[str] = None
    if eval_resolution_inputs is None:
        evl_status, evl_reason = "missing", "EVAL_REQUIRED_MISSING"
        findings.append(
            {
                "reason_code": "EVAL_REQUIRED_MISSING",
                "stage": "EVL",
                "detail": "eval_resolution_inputs not supplied",
            }
        )
    else:
        resolution = resolve_required_evals(
            declared_catalog=eval_resolution_inputs.get("declared_catalog") or [],
            submitted_evals=eval_resolution_inputs.get("submitted_evals") or [],
        )
        if not resolution["ok"]:
            evl_status, evl_reason = "failed", resolution["primary_reason"]
            for v in resolution["violations"]:
                findings.append({**v, "stage": "EVL"})

    # ── TPA
    tpa_status = "ok"
    tpa_reason: Optional[str] = None
    if policy_inputs is None:
        tpa_status, tpa_reason = "missing", "POLICY_INPUT_MISSING"
        findings.append(
            {
                "reason_code": "POLICY_INPUT_MISSING",
                "stage": "TPA",
                "detail": "policy_inputs not supplied",
            }
        )
    else:
        tpa_inputs = validate_policy_inputs(policy_inputs)
        if not tpa_inputs["ok"]:
            tpa_status, tpa_reason = "failed", tpa_inputs["primary_reason"]
            for v in tpa_inputs["violations"]:
                findings.append({**v, "stage": "TPA"})

    if policy_result is None:
        if tpa_status == "ok":
            tpa_status, tpa_reason = "missing", "POLICY_RESULT_MISSING"
        findings.append(
            {
                "reason_code": "POLICY_RESULT_MISSING",
                "stage": "TPA",
                "detail": "policy_result not supplied",
            }
        )
    else:
        rr = validate_policy_result(policy_result)
        if not rr["ok"]:
            tpa_status, tpa_reason = "failed", rr["primary_reason"]
            for v in rr["violations"]:
                findings.append({**v, "stage": "TPA"})
    tpa_ref = (
        policy_result.get("tpa_policy_result_ref")
        if isinstance(policy_result, Mapping)
        else None
    )

    # ── CDE
    cde_status = "ok"
    cde_reason: Optional[str] = None
    if decision_inputs is None:
        cde_status, cde_reason = "missing", "DECISION_INPUT_MISSING_TPA"
        findings.append(
            {
                "reason_code": "DECISION_INPUT_MISSING_TPA",
                "stage": "CDE",
                "detail": "decision_inputs not supplied",
            }
        )
    else:
        dr = validate_decision_inputs(decision_inputs)
        if not dr["ok"]:
            cde_status, cde_reason = "failed", dr["primary_reason"]
            for v in dr["violations"]:
                findings.append({**v, "stage": "CDE"})

    if decision_outcome is None:
        if cde_status == "ok":
            cde_status, cde_reason = "missing", "DECISION_FREEZE_REQUIRED"
        findings.append(
            {
                "reason_code": "DECISION_FREEZE_REQUIRED",
                "stage": "CDE",
                "detail": "decision_outcome not supplied",
            }
        )
    else:
        oc = validate_decision_outcome(decision_outcome)
        if not oc["ok"]:
            cde_status, cde_reason = "failed", oc["primary_reason"]
            for v in oc["violations"]:
                findings.append({**v, "stage": "CDE"})
    cde_ref = (
        decision_outcome.get("cde_decision_ref")
        or decision_outcome.get("decision_id")
        if isinstance(decision_outcome, Mapping)
        else None
    )

    # ── SEL
    sel_status = "ok"
    sel_reason: Optional[str] = None
    if sel_action is None:
        sel_status, sel_reason = "missing", "ACTION_MUTATION_WITHOUT_ALLOW"
        findings.append(
            {
                "reason_code": "ACTION_MUTATION_WITHOUT_ALLOW",
                "stage": "SEL",
                "detail": "sel_action not supplied",
            }
        )
    elif isinstance(decision_outcome, Mapping):
        decision_value = decision_outcome.get("decision") or decision_outcome.get(
            "control_outcome"
        )
        action_value = sel_action.get("action") if isinstance(sel_action, Mapping) else None
        sr = validate_action_for_decision(
            decision=str(decision_value or ""),
            action=str(action_value or ""),
        )
        if not sr["ok"]:
            sel_status, sel_reason = "failed", sr["primary_reason"]
            for v in sr["violations"]:
                findings.append({**v, "stage": "SEL"})
    sel_ref = sel_action.get("sel_action_ref") if isinstance(sel_action, Mapping) else None

    # Stage records
    stages = {
        "AEX": _stage_record("AEX", aex_ref, aex_status, aex_reason),
        "PQX": _stage_record("PQX", pqx_ref, pqx_status, pqx_reason),
        "EVL": _stage_record(
            "EVL",
            eval_summary_ref,
            evl_status,
            evl_reason,
        ),
        "TPA": _stage_record("TPA", tpa_ref, tpa_status, tpa_reason),
        "CDE": _stage_record("CDE", cde_ref, cde_status, cde_reason),
        "SEL": _stage_record("SEL", sel_ref, sel_status, sel_reason),
    }

    # Transitions: for each canonical pair, mark ``failed`` if either
    # endpoint is non-ok or if the upstream stage's required_output_ref
    # is missing. This is what CL-02/CL-03 enforces — a corrupted handoff
    # cannot pass downstream.
    transitions: List[Dict[str, Any]] = []
    for from_stage, to_stage in CANONICAL_TRANSITIONS:
        upstream = stages[from_stage]["status"]
        downstream = stages[to_stage]["status"]
        # Build a cheap handoff payload for this transition from the
        # upstream stage's artifact_ref.
        upstream_ref = stages[from_stage]["artifact_ref"]
        handoff_fields = {
            "trace_id": trace_id,
            "run_id": run_id,
            "admission_class": (
                admission_packet.get("admission_class")
                if isinstance(admission_packet, Mapping)
                else None
            ),
            "execution_status": (
                execution_envelope.get("status")
                if isinstance(execution_envelope, Mapping)
                else None
            ),
            "eval_summary_status": stages["EVL"]["status"],
            "policy_result_status": (
                policy_result.get("policy_result_status")
                if isinstance(policy_result, Mapping)
                else None
            ),
            "control_outcome": (
                decision_outcome.get("decision")
                or decision_outcome.get("control_outcome")
                if isinstance(decision_outcome, Mapping)
                else None
            ),
        }
        input_refs = {
            "aex_admission_ref": aex_ref,
            "pqx_execution_envelope_ref": pqx_ref,
            "evl_eval_summary_ref": eval_summary_ref,
            "tpa_policy_input_ref": (
                policy_inputs.get("tpa_policy_input_ref")
                if isinstance(policy_inputs, Mapping)
                else None
            ),
            "tpa_policy_result_ref": tpa_ref,
            "cde_decision_input_ref": (
                decision_inputs.get("cde_decision_input_ref")
                if isinstance(decision_inputs, Mapping)
                else None
            ),
        }
        output_refs = {
            "aex_admission_ref": aex_ref,
            "pqx_execution_envelope_ref": pqx_ref,
            "evl_eval_summary_ref": eval_summary_ref,
            "tpa_policy_result_ref": tpa_ref,
            "cde_decision_ref": cde_ref,
        }
        ho = validate_handoff(
            contract,
            from_stage=from_stage,
            to_stage=to_stage,
            handoff_fields=handoff_fields,
            input_refs=input_refs,
            output_refs=output_refs,
        )
        missing_fields: List[str] = []
        if not ho["ok"]:
            for v in ho["violations"]:
                if v.get("reason_code") == REASON_HANDOFF_MISSING_FIELD:
                    f = v.get("field")
                    if isinstance(f, str):
                        missing_fields.append(f)
            findings.append(
                {
                    "reason_code": ho["primary_reason"],
                    "stage": from_stage,
                    "detail": f"{from_stage}->{to_stage}",
                }
            )
        if upstream != "ok" or downstream not in ("ok", "missing", "failed"):
            transitions.append(
                _transition_record(
                    from_stage,
                    to_stage,
                    "failed" if upstream != "ok" else "missing",
                    reason_code=ho["primary_reason"] if not ho["ok"] else None,
                    missing_handoff_fields=missing_fields,
                )
            )
        elif not ho["ok"]:
            transitions.append(
                _transition_record(
                    from_stage,
                    to_stage,
                    "failed",
                    reason_code=ho["primary_reason"],
                    missing_handoff_fields=missing_fields,
                )
            )
        else:
            transitions.append(_transition_record(from_stage, to_stage, "ok"))

    primary = select_primary_reason(candidate_findings=findings)

    any_failed = any(s["status"] != "ok" for s in stages.values())
    decision_value = (
        decision_outcome.get("decision") or decision_outcome.get("control_outcome")
        if isinstance(decision_outcome, Mapping)
        else None
    )
    if not any_failed and decision_value == "allow":
        terminal_status = "pass"
    elif decision_value == "freeze" or primary["primary_canonical_reason"] in (
        "DECISION_FREEZE_REQUIRED",
    ):
        terminal_status = "freeze"
    else:
        terminal_status = "block"

    trace_continuity_ok = all(t["status"] == "ok" for t in transitions)

    human_lines = [
        f"CORE LOOP PROOF — proof_id={proof_id} trace_id={trace_id}",
        f"terminal_status: {terminal_status}",
        f"primary_reason: {primary['primary_canonical_reason']}",
        f"source_stage: {primary['source_stage']}",
        f"next_allowed_action: {primary['next_allowed_action']}",
        "stages:",
    ]
    for s in CANONICAL_STAGE_ORDER:
        rec = stages[s]
        human_lines.append(
            f"  {s}: status={rec['status']} ref={rec['artifact_ref'] or '-'} reason={rec['reason_code'] or '-'}"
        )
    human_lines.append("transitions:")
    for t in transitions:
        human_lines.append(
            f"  {t['from_stage']}->{t['to_stage']}: status={t['status']} reason={t['reason_code'] or '-'}"
        )

    proof: Dict[str, Any] = {
        "artifact_type": "core_loop_proof",
        "schema_version": "1.0.0",
        "proof_id": proof_id,
        "trace_id": trace_id,
        "run_id": run_id,
        "audit_timestamp": audit_timestamp,
        "stages": stages,
        "transitions": transitions,
        "primary_reason": primary,
        "terminal_status": terminal_status,
        "lineage_chain_ref": lineage_chain_ref,
        "replay_record_ref": replay_record_ref,
        "trace_continuity_ok": trace_continuity_ok,
        "human_readable": "\n".join(human_lines),
        "non_authority_assertions": [
            "preparatory_only",
            "not_admission_authority",
            "not_execution_authority",
            "not_eval_authority",
            "not_policy_authority",
            "not_control_authority",
            "not_enforcement_authority",
        ],
    }
    return proof


__all__ = [
    "CoreLoopProofError",
    "build_core_loop_proof",
]
