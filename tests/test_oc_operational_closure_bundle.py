"""OC-25..27: Operational closure bundle + final operator decision drill."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.governance.operational_closure_bundle import (
    OperationalClosureBundleError,
    build_operational_closure_bundle,
)
from spectrum_systems.modules.governance.closure_decision_packet import (
    build_closure_decision_packet,
)
from spectrum_systems.modules.governance.fast_trust_gate import (
    REQUIRED_SEAMS,
    build_fast_trust_gate_run_summary,
    load_fast_trust_gate_manifest,
)
from spectrum_systems.modules.governance.work_selection_signal import (
    build_work_selection_record,
)
from spectrum_systems.modules.observability.bottleneck_classifier import (
    classify_bottleneck,
)
from spectrum_systems.modules.observability.dashboard_truth_projection import (
    build_dashboard_truth_projection,
)
from spectrum_systems.modules.governance.proof_intake_index import (
    REQUIRED_PROOF_KINDS,
    build_proof_intake_index,
)


def _good_proof_intake():
    candidates = {
        kind: [
            {
                "artifact_id": f"{kind}-1",
                "producer_inputs": {"k": kind},
                "producer_input_digest": _digest({"k": kind}),
                "generated_at": "2026-04-28T11:00:00Z",
            }
        ]
        for kind in REQUIRED_PROOF_KINDS
    }
    return build_proof_intake_index(
        intake_id="pii-1",
        audit_timestamp="2026-04-28T11:00:00Z",
        candidates_by_kind=candidates,
    )


def _digest(payload):
    import hashlib
    import json

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _good_dashboard_projection():
    repo = {
        "current_status": "pass",
        "latest_proof_ref": "lpb-1",
        "owning_system": "GOV",
        "reason_code": "ALIGNED",
        "bottleneck_category": "none",
        "next_safe_action": "merge",
        "proof_digest": "deadbeef",
    }
    return build_dashboard_truth_projection(
        projection_id="dtp-1",
        audit_timestamp="2026-04-28T11:00:00Z",
        repo_truth=repo,
        dashboard_view=dict(repo),
    )


def _good_bottleneck():
    # Express "no current bottleneck" explicitly so the closure packet
    # treats this seam as non-blocking.
    return {
        "artifact_type": "bottleneck_classification",
        "schema_version": "1.0.0",
        "classification_id": "bc-1",
        "audit_timestamp": "2026-04-28T11:00:00Z",
        "category": "none",
        "owning_system": None,
        "reason_code": "BOTTLENECK_NONE",
        "evidence_artifact_ref": None,
        "confidence": "high",
        "ambiguous": False,
        "ambiguity_candidates": [],
        "next_safe_action": {"action": "warn", "rationale": "no bottleneck"},
        "non_authority_assertions": [
            "preparatory_only",
            "not_control_authority",
        ],
    }


def _good_fast_gate():
    manifest = load_fast_trust_gate_manifest()
    return build_fast_trust_gate_run_summary(
        run_id="ftgr-1",
        audit_timestamp="2026-04-28T11:00:00Z",
        manifest=manifest,
        seam_results=[{"seam": s, "status": "ok"} for s in REQUIRED_SEAMS],
    )


def _good_work_selection():
    return build_work_selection_record(
        record_id="wsr-1",
        audit_timestamp="2026-04-28T11:00:00Z",
        candidates=[
            {
                "work_item_id": "OC-NEXT-1",
                "justification_kind": "current_bottleneck",
                "evidence_ref": "bc-1",
            }
        ],
    )


def _good_closure_packet():
    return build_closure_decision_packet(
        packet_id="cdp-1",
        trace_id="t1",
        audit_timestamp="2026-04-28T11:00:00Z",
        proof_intake=_good_proof_intake(),
        bottleneck_classification=_good_bottleneck(),
        dashboard_projection=_good_dashboard_projection(),
        fast_trust_gate=_good_fast_gate(),
        certification_delta_proof={"delta_id": "cdp-d1", "status": "ready"},
        trust_regression_pack={"pack_id": "trp-1", "status": "pass"},
        lineage_chain={"lineage_id": "lin-1", "status": "ok"},
    )


def test_bundle_id_required():
    with pytest.raises(OperationalClosureBundleError):
        build_operational_closure_bundle(
            bundle_id="",
            audit_timestamp="2026-04-28T00:00:00Z",
        )


def test_pass_path_yields_pass_status_and_yes_answers():
    bundle = build_operational_closure_bundle(
        bundle_id="ocb-1",
        audit_timestamp="2026-04-28T11:00:00Z",
        proof_intake=_good_proof_intake(),
        bottleneck_classification=_good_bottleneck(),
        dashboard_projection=_good_dashboard_projection(),
        closure_packet=_good_closure_packet(),
        fast_trust_gate_run=_good_fast_gate(),
        work_selection_record=_good_work_selection(),
    )
    assert bundle["overall_status"] == "pass"
    q = bundle["operator_questions"]
    assert q["is_pass_block_freeze_or_unknown"] == "pass"
    assert q["dashboard_aligned_with_repo_truth"] == "yes"
    assert q["fast_trust_gate_sufficient"] == "yes"
    assert q["next_work_item_label"] == "OC-NEXT-1"


def test_no_inputs_yields_unknown():
    bundle = build_operational_closure_bundle(
        bundle_id="ocb-1",
        audit_timestamp="2026-04-28T11:00:00Z",
    )
    assert bundle["overall_status"] == "unknown"
    assert bundle["operator_questions"]["is_pass_block_freeze_or_unknown"] == "unknown"


# ---- OC-26 red team: operator decision drill ----


def test_operator_can_identify_block_action_from_bundle_alone():
    """Simulate an operator with only the bundle. The bundle's
    operator_questions and overall_status MUST be enough to identify
    that the next action is investigate / block."""
    bundle = build_operational_closure_bundle(
        bundle_id="ocb-block",
        audit_timestamp="2026-04-28T11:00:00Z",
        proof_intake=_good_proof_intake(),
        bottleneck_classification=classify_bottleneck(
            classification_id="bc-1",
            findings=[
                {
                    "category": "eval",
                    "reason_code": "BOTTLENECK_EVAL_FAILED",
                    "evidence_ref": "evl-1",
                }
            ],
        ),
        dashboard_projection=_good_dashboard_projection(),
        closure_packet=build_closure_decision_packet(
            packet_id="cdp-1",
            trace_id="t1",
            audit_timestamp="2026-04-28T11:00:00Z",
            proof_intake=_good_proof_intake(),
            bottleneck_classification=classify_bottleneck(
                classification_id="bc-1",
                findings=[
                    {
                        "category": "eval",
                        "reason_code": "BOTTLENECK_EVAL_FAILED",
                        "evidence_ref": "evl-1",
                    }
                ],
            ),
            dashboard_projection=_good_dashboard_projection(),
            fast_trust_gate=_good_fast_gate(),
            certification_delta_proof={"delta_id": "cdp-d1", "status": "ready"},
            trust_regression_pack={"pack_id": "trp-1", "status": "pass"},
            lineage_chain={"lineage_id": "lin-1", "status": "ok"},
        ),
        fast_trust_gate_run=_good_fast_gate(),
        work_selection_record=_good_work_selection(),
    )
    assert bundle["overall_status"] == "block"
    q = bundle["operator_questions"]
    assert q["current_bottleneck_label"] == "eval"
    assert q["owning_three_letter_system"] == "EVL"
    assert q["next_work_item_label"] is not None
    assert q["justifying_failure_or_signal"] in (
        "current_bottleneck",
        "bottleneck:eval",
    )


def test_operator_can_identify_freeze_from_bundle():
    bundle = build_operational_closure_bundle(
        bundle_id="ocb-freeze",
        audit_timestamp="2026-04-28T11:00:00Z",
        proof_intake=_good_proof_intake(),
        bottleneck_classification=classify_bottleneck(
            classification_id="bc-1",
            findings=[
                {"category": "slo", "reason_code": "BOTTLENECK_SLO_BURN"}
            ],
        ),
        dashboard_projection=_good_dashboard_projection(),
        closure_packet={"packet_id": "cdp-1", "packet_status": "freeze"},
        fast_trust_gate_run=_good_fast_gate(),
        work_selection_record=_good_work_selection(),
    )
    assert bundle["overall_status"] == "freeze"
    assert bundle["operator_questions"]["is_pass_block_freeze_or_unknown"] == "freeze"


def test_dashboard_drift_demotes_pass_to_block():
    """Even when the closure packet says ready_to_merge, if the
    dashboard alignment is drifted/missing/corrupt, the bundle MUST
    demote the overall_status."""
    bad_dash = build_dashboard_truth_projection(
        projection_id="dtp-bad",
        audit_timestamp="2026-04-28T11:00:00Z",
        repo_truth={
            "current_status": "pass",
            "latest_proof_ref": "lpb-1",
            "owning_system": "GOV",
            "reason_code": "X",
            "bottleneck_category": "none",
            "next_safe_action": "merge",
            "proof_digest": "AAAA",
        },
        dashboard_view={
            "current_status": "pass",
            "latest_proof_ref": "lpb-1",
            "owning_system": "GOV",
            "reason_code": "X",
            "bottleneck_category": "none",
            "next_safe_action": "merge",
            "proof_digest": "BBBB",  # mismatch
        },
    )
    bundle = build_operational_closure_bundle(
        bundle_id="ocb-dash",
        audit_timestamp="2026-04-28T11:00:00Z",
        proof_intake=_good_proof_intake(),
        bottleneck_classification=_good_bottleneck(),
        dashboard_projection=bad_dash,
        closure_packet={"packet_id": "cdp-1", "packet_status": "ready_to_merge"},
        fast_trust_gate_run=_good_fast_gate(),
        work_selection_record=_good_work_selection(),
    )
    assert bundle["overall_status"] == "block"
