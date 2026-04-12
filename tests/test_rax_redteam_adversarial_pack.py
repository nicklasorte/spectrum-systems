from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.modules.runtime.rax_assurance import build_rax_assurance_audit_record, evaluate_rax_control_readiness
from spectrum_systems.modules.runtime.rax_eval_runner import run_rax_eval_runner

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "rax_adversarial_eval_pack.json"


def _load_pack() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _governed_evidence() -> dict:
    return {
        "assurance_audit": {"acceptance_decision": "accept_candidate", "failure_classification": "none"},
        "trace_integrity_evidence": {"trace_linked": True, "trace_complete": True},
        "lineage_provenance_evidence": {"lineage_valid": True, "lineage_chain_complete": True},
        "dependency_state": {"graph_integrity": True, "unresolved_dependencies": []},
        "authority_records": {"docs/roadmaps/system_roadmap.md#RAX-INTERFACE-24-01": "1.3.112"},
    }


def test_redteam_pack_covers_all_required_failure_classes() -> None:
    pack = _load_pack()
    classes = {case["failure_class"] for case in pack["cases"]}
    assert classes == {
        "semantic_drift",
        "readiness_inflation",
        "missing_weak_counter_evidence",
        "provenance_gaps",
        "replay_inconsistency",
        "policy_drift_mismatch",
        "feedback_loop_poisoning",
        "unknown_state_partial_signals",
    }


def test_redteam_pack_executes_serial_and_fails_closed() -> None:
    pack = _load_pack()

    for case in pack["cases"]:
        out = run_rax_eval_runner(
            run_id=case["run_id"],
            target_ref=pack["target_ref"],
            trace_id=case["trace_id"],
            input_assurance=case["input_assurance"],
            output_assurance=case["output_assurance"],
            tests_passed=case["tests_passed"],
            baseline_regression_detected=case["baseline_regression_detected"],
            version_authority_aligned=case["version_authority_aligned"],
            omit_eval_types=case.get("omit_eval_types"),
        )

        if case.get("expect_failure_candidate"):
            assert out["failure_pattern_records"]
            assert out["eval_case_candidates"]
            continue

        coverage = out["required_eval_coverage"]
        if case.get("tamper_required_coverage"):
            coverage = dict(coverage)
            coverage["required_eval_types"] = ["rax_control_readiness"]

        evidence = _governed_evidence()
        if "lineage_provenance_evidence" in case:
            evidence["lineage_provenance_evidence"] = case["lineage_provenance_evidence"]
        if case.get("drop_trace_integrity_evidence"):
            evidence.pop("trace_integrity_evidence")
        if case.get("replay_key_only"):
            evidence["replay_key"] = "same-input-identity"

        if case["failure_class"] == "missing_weak_counter_evidence":
            evidence["assurance_audit"] = build_rax_assurance_audit_record(
                roadmap_id="SYSTEM-ROADMAP-2026",
                step_id="RAX-INTERFACE-24-01",
                input_assurance=case["input_assurance"],
                output_assurance=case["output_assurance"],
            )

        readiness = evaluate_rax_control_readiness(
            batch=pack["batch"],
            target_ref=pack["target_ref"],
            eval_summary=out["eval_summary"],
            eval_results=out["eval_results"],
            required_eval_coverage=coverage,
            **evidence,
        )

        assert readiness["ready_for_control"] is False, case["case_id"]
        assert case["expected_blocking_reason"] in readiness["blocking_reasons"], case["case_id"]
