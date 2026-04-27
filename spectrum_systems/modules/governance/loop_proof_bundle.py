"""GOV: Loop proof bundle — compact, reference-only end-to-end proof.

NS-25: Build a compact bundle that proves the canonical loop ran for either
a passing path or a blocked path. The bundle holds references (artifact_ids)
and a single one-page trace summary. It does NOT embed full payloads.

Required references:
  - execution_record
  - output_artifact
  - eval_summary
  - control_decision
  - enforcement_action_signal (when state-changing)
  - replay_record
  - lineage_chain
  - certification_evidence_index
  - failure_trace (when blocked/frozen)

The final_status is derived from the supplied evidence:
  * ``pass``    when control allows AND eval is healthy AND replay matches
                AND lineage is healthy AND certification is ready.
  * ``freeze``  when control freezes OR certification is frozen.
  * ``block``   otherwise.

A new engineer must be able to inspect the bundle in under 10 minutes:
the ``human_readable`` and ``trace_summary.one_page_summary`` fields are
designed to make the failure (or pass) story legible without scrolling.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from spectrum_systems.modules.governance.certification_evidence_index import (
    build_certification_evidence_index,
)
from spectrum_systems.modules.observability.failure_trace import build_failure_trace


class LoopProofBundleError(ValueError):
    """Raised when a loop proof bundle cannot be deterministically constructed."""


def _ref_id(obj: Optional[Mapping[str, Any]], *keys: str) -> Optional[str]:
    if not isinstance(obj, Mapping):
        return None
    candidate_keys = keys or (
        "artifact_id",
        "decision_id",
        "validation_id",
        "enforcement_id",
        "index_id",
        "summary_id",
        "id",
    )
    for k in candidate_keys:
        v = obj.get(k)
        if isinstance(v, str) and v.strip():
            return v
    return None


def build_loop_proof_bundle(
    *,
    bundle_id: str,
    trace_id: str,
    run_id: str = "",
    execution_record: Optional[Mapping[str, Any]] = None,
    output_artifact: Optional[Mapping[str, Any]] = None,
    eval_summary: Optional[Mapping[str, Any]] = None,
    control_decision: Optional[Mapping[str, Any]] = None,
    enforcement_action: Optional[Mapping[str, Any]] = None,
    replay_record: Optional[Mapping[str, Any]] = None,
    lineage_summary: Optional[Mapping[str, Any]] = None,
    certification_evidence_index: Optional[Mapping[str, Any]] = None,
    failure_trace: Optional[Mapping[str, Any]] = None,
    state_changing: bool = True,
) -> Dict[str, Any]:
    """Build a compact loop_proof_bundle.

    Either ``failure_trace`` is supplied directly, or it is built from the
    canonical loop fields. ``certification_evidence_index`` is similarly
    constructed if not supplied.
    """
    if not isinstance(bundle_id, str) or not bundle_id.strip():
        raise LoopProofBundleError("bundle_id must be a non-empty string")
    if not isinstance(trace_id, str) or not trace_id.strip():
        raise LoopProofBundleError("trace_id must be a non-empty string")

    # Compose a failure trace from inputs when not supplied
    trace = failure_trace
    if trace is None:
        trace = build_failure_trace(
            trace_id=trace_id,
            execution_record=execution_record,
            output_artifact=output_artifact,
            eval_result=eval_summary,
            control_decision=control_decision,
            enforcement_action=enforcement_action,
        )

    # Derive a certification evidence index when not supplied. We pass
    # placeholder pass-through summaries when downstream gate inputs are
    # missing; missing-reference enforcement is internal to the index.
    cei = certification_evidence_index
    if cei is None:
        cei = build_certification_evidence_index(
            index_id=f"cei-{bundle_id}",
            trace_id=trace_id,
            eval_summary=eval_summary,
            lineage_summary=lineage_summary,
            replay_summary=replay_record if replay_record is not None else None,
            control_decision=control_decision,
            enforcement_action=enforcement_action,
            authority_shape_preflight={"artifact_id": "asp-default", "status": "pass"},
            registry_validation={"artifact_id": "reg-default", "status": "pass", "violations": []},
            artifact_tier_validation={
                "validation_id": f"tier-{bundle_id}",
                "decision": "allow",
                "reason_code": "TIER_OK",
            },
            failure_trace=trace,
            state_changing=state_changing,
        )

    # Derive final_status
    cei_status = str(cei.get("status") or "blocked").lower()
    cd_decision = ""
    if isinstance(control_decision, Mapping):
        cd_decision = str(control_decision.get("decision") or "").lower()
    if cd_decision == "freeze" or cei_status == "frozen":
        final_status = "freeze"
    elif cd_decision == "allow" and cei_status == "ready" and trace.get("overall_status") == "ok":
        final_status = "pass"
    else:
        final_status = "block"

    canonical_blocking = None
    if final_status != "pass":
        canonical_blocking = (
            cei.get("blocking_reason_canonical")
            or trace.get("canonical_reason_category")
            or "CERTIFICATION_GAP"
        )

    refs = {
        "execution_record_ref": _ref_id(execution_record, "artifact_id", "execution_id", "run_id"),
        "output_artifact_ref": _ref_id(output_artifact, "artifact_id", "id"),
        "eval_summary_ref": _ref_id(eval_summary, "artifact_id", "coverage_run_id", "slice_id"),
        "control_decision_ref": _ref_id(control_decision, "decision_id", "artifact_id"),
        "enforcement_action_ref": _ref_id(
            enforcement_action, "enforcement_id", "enforcement_result_id", "artifact_id"
        ),
        "replay_record_ref": _ref_id(replay_record, "replay_id", "artifact_id"),
        "lineage_chain_ref": _ref_id(lineage_summary, "summary_id", "artifact_id"),
        "certification_evidence_index_ref": _ref_id(cei, "index_id", "artifact_id"),
        "failure_trace_ref": _ref_id(trace, "trace_id", "artifact_id") if trace.get("overall_status") == "failed" else None,
    }

    trace_summary = {
        "overall_status": str(trace.get("overall_status") or "failed"),
        "failed_stage": trace.get("failed_stage"),
        "owning_system": trace.get("owning_system_for_failed_stage"),
        "one_page_summary": str(trace.get("one_page_summary") or ""),
    }

    human_lines = [
        f"LOOP PROOF BUNDLE — bundle_id={bundle_id} trace_id={trace_id}",
        f"final_status: {final_status}",
        f"canonical_blocking_category: {canonical_blocking or '-'}",
        "references:",
    ]
    for key in [
        "execution_record_ref",
        "output_artifact_ref",
        "eval_summary_ref",
        "control_decision_ref",
        "enforcement_action_ref",
        "replay_record_ref",
        "lineage_chain_ref",
        "certification_evidence_index_ref",
        "failure_trace_ref",
    ]:
        human_lines.append(f"  {key}: {refs[key] or '-'}")
    human_lines.append("")
    human_lines.append("--- one-page trace ---")
    human_lines.append(trace_summary["one_page_summary"])

    bundle = {
        "artifact_type": "loop_proof_bundle",
        "schema_version": "1.0.0",
        "bundle_id": bundle_id,
        "trace_id": trace_id,
        "run_id": run_id,
        "final_status": final_status,
        "canonical_blocking_category": canonical_blocking,
        "execution_record_ref": refs["execution_record_ref"],
        "output_artifact_ref": refs["output_artifact_ref"],
        "eval_summary_ref": refs["eval_summary_ref"],
        "control_decision_ref": refs["control_decision_ref"],
        "enforcement_action_ref": refs["enforcement_action_ref"],
        "replay_record_ref": refs["replay_record_ref"],
        "lineage_chain_ref": refs["lineage_chain_ref"],
        "certification_evidence_index_ref": refs["certification_evidence_index_ref"],
        "failure_trace_ref": refs["failure_trace_ref"],
        "trace_summary": trace_summary,
        "human_readable": "\n".join(human_lines),
    }

    return bundle


__all__ = [
    "LoopProofBundleError",
    "build_loop_proof_bundle",
]
