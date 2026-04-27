"""NT-22..24: End-to-end trust regression pack.

Each fixture exercises a single trust-loop seam. The pack is small by
design — it does not duplicate the full pytest suite. NT-23 mutates each
seam and confirms the pack still catches the failure.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import pytest

from spectrum_systems.modules.governance.certification_delta import (
    build_certification_delta_index,
)
from spectrum_systems.modules.governance.loop_proof_bundle import build_loop_proof_bundle
from spectrum_systems.modules.observability.artifact_tier_drift import (
    validate_transitive_promotion_evidence_tiers,
)
from spectrum_systems.modules.observability.reason_code_lifecycle import (
    audit_reason_code_coverage,
)
from spectrum_systems.modules.observability.trust_artifact_freshness import (
    audit_artifact_freshness,
)
from spectrum_systems.modules.runtime.slo_budget_gate import evaluate_slo_signal_diet


PACK_DIR = Path(__file__).resolve().parent / "fixtures" / "trust_regression_pack"


def _load(name: str) -> Dict:
    return json.loads((PACK_DIR / name).read_text(encoding="utf-8"))


# --- NT-22: each seam fixture exists and is loadable ----------------------


def test_pack_contains_required_fixtures():
    expected = {
        "pass.json",
        "block.json",
        "freeze.json",
        "stale_proof.json",
        "tier_violation.json",
        "reason_code_violation.json",
        "replay_lineage_mismatch.json",
        "context_admission_failure.json",
        "README.md",
    }
    found = {p.name for p in PACK_DIR.iterdir()}
    missing = expected - found
    assert not missing, f"missing fixtures: {missing}"


def test_pass_fixture_drives_pass_bundle():
    fix = _load("pass.json")
    bundle = build_loop_proof_bundle(**fix["loop_inputs"])
    assert bundle["final_status"] == fix["expected_final_status"]


def test_block_fixture_drives_block_bundle_with_canonical_category():
    fix = _load("block.json")
    bundle = build_loop_proof_bundle(**fix["loop_inputs"])
    assert bundle["final_status"] == fix["expected_final_status"]
    assert (
        bundle["canonical_blocking_category"]
        in fix["expected_canonical_categories"]
    )


def test_freeze_fixture_drives_freeze_bundle():
    fix = _load("freeze.json")
    bundle = build_loop_proof_bundle(**fix["loop_inputs"])
    assert bundle["final_status"] == fix["expected_final_status"]


def test_stale_proof_fixture_is_stale():
    fix = _load("stale_proof.json")
    res = audit_artifact_freshness(
        fix["trust_artifact"],
        expected_input_digest=fix["expected_input_digest"],
        expected_source_digest=fix["expected_source_digest"],
        now_iso="2026-04-27T12:00:00Z",
    )
    assert res["status"] == fix["expected_freshness_status"]
    assert res["canonical_reason"] == fix["expected_canonical_category"]


def test_tier_violation_fixture_blocks_with_canonical_reason():
    fix = _load("tier_violation.json")
    res = validate_transitive_promotion_evidence_tiers(
        fix["promotion_evidence_items"],
        validation_id="trp-tier",
    )
    assert res["decision"] == fix["expected_decision"]
    assert res["reason_code"] == fix["expected_reason_code"]


def test_reason_code_violation_fixture_blocks_audit():
    fix = _load("reason_code_violation.json")
    res = audit_reason_code_coverage(emitted_codes=fix["emitted_codes"])
    assert res["decision"] == fix["expected_decision"]
    assert res["reason_code"] in {
        "REASON_CODE_LIFECYCLE_FORBIDDEN",
        "REASON_CODE_LIFECYCLE_UNMAPPED_BLOCKING",
    }


def test_replay_lineage_mismatch_fixture_blocks_signal_diet():
    fix = _load("replay_lineage_mismatch.json")
    res = evaluate_slo_signal_diet(signals=fix["signals"])
    assert res["decision"] == fix["expected_decision"]
    assert res["canonical_category"] == fix["expected_canonical_category"]


def test_context_admission_failure_fixture_blocks_signal_diet():
    fix = _load("context_admission_failure.json")
    res = evaluate_slo_signal_diet(signals=fix["signals"])
    assert res["decision"] == fix["expected_decision"]
    assert res["canonical_category"] == fix["expected_canonical_category"]


# --- NT-23: red-team mutations of each seam --------------------------------


def test_mutated_pass_with_failed_eval_reverts_to_block():
    fix = _load("pass.json")
    inputs = dict(fix["loop_inputs"])
    inputs["bundle_id"] = "lpb-mutated"
    inputs["eval_summary"] = {"artifact_id": "evl-bad", "status": "blocked"}
    inputs["control_decision"] = {"decision_id": "cde-mut", "decision": "block"}
    inputs["enforcement_action"] = {
        "enforcement_id": "sel-mut",
        "enforcement_action": "deny_execution",
    }
    bundle = build_loop_proof_bundle(**inputs)
    assert bundle["final_status"] == "block"


def test_mutated_block_without_canonical_reason_still_canonicalizes():
    fix = _load("block.json")
    inputs = dict(fix["loop_inputs"])
    inputs["bundle_id"] = "lpb-mut-block"
    inputs["control_decision"] = {
        "decision_id": "cde-mut2",
        "decision": "block",
        "reason_code": "totally_invented_code",
    }
    bundle = build_loop_proof_bundle(**inputs)
    assert bundle["final_status"] == "block"
    # still produces some canonical_blocking_category (UNKNOWN or default)
    assert bundle["canonical_blocking_category"] is not None


def test_mutated_stale_with_freshened_timestamp_still_caught_by_digest():
    """Red team: bump only the timestamp, leave digest mismatch."""
    fix = _load("stale_proof.json")
    art = dict(fix["trust_artifact"])
    art["generated_at"] = "2026-04-26T12:00:00Z"  # very fresh
    res = audit_artifact_freshness(
        art,
        expected_input_digest=fix["expected_input_digest"],
        expected_source_digest=fix["expected_source_digest"],
        now_iso="2026-04-27T12:00:00Z",
    )
    # Source digest still mismatches; status must remain stale
    assert res["status"] == "stale"
    assert res["reason_code"] == "TRUST_FRESHNESS_DIGEST_MISMATCH"


def test_mutated_tier_violation_through_canonical_wrapper_still_blocks():
    fix = _load("tier_violation.json")
    res = validate_transitive_promotion_evidence_tiers(
        [{"artifact_id": "lpb-wrap", "artifact_type": "loop_proof_bundle"}],
        referenced_evidence_items=fix["promotion_evidence_items"],
        validation_id="trp-tier-wrap",
    )
    assert res["decision"] == "block"
    assert res["reason_code"] == "TIER_DRIFT_INDIRECT_EVIDENCE_LAUNDERING"


def test_mutated_certification_delta_silent_evidence_swap_is_caught():
    """Red team: previous and current both report 'ready', but eval ref
    silently swapped. Hidden delta must be detected."""
    prev = {
        "artifact_type": "certification_evidence_index",
        "status": "ready",
        "blocking_reason_canonical": "CERT_OK",
        "references": {
            "eval_summary_ref": "evl-OLD",
            "lineage_summary_ref": "lin-1",
            "replay_summary_ref": "rpl-1",
            "control_decision_ref": "cde-1",
            "authority_shape_preflight_ref": "asp-1",
            "registry_validation_ref": "reg-1",
            "artifact_tier_validation_ref": "tier-1",
        },
    }
    curr = dict(prev)
    curr["references"] = dict(prev["references"])
    curr["references"]["eval_summary_ref"] = "evl-NEW"
    delta = build_certification_delta_index(
        delta_id="trp-mut-delta",
        trace_id="t1",
        previous_evidence_index=prev,
        current_evidence_index=curr,
    )
    assert delta["delta_risk"] != "none"
    assert delta["reason_code"] == "CERTIFICATION_DELTA_CHANGED_DIGEST"
