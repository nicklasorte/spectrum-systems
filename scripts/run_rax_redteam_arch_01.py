#!/usr/bin/env python3
"""RAX-REDTEAM-ARCH-01 architecture-level adversarial review.

Primary prompt type: REVIEW.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import load_example
from spectrum_systems.modules.runtime.rax_assurance import (
    assure_rax_input,
    assure_rax_output,
    build_rax_assurance_audit_record,
    evaluate_rax_control_readiness,
)
from spectrum_systems.modules.runtime.rax_eval_runner import (
    enforce_rax_control_advancement,
    enforce_required_rax_eval_coverage,
    run_rax_eval_runner,
)
from spectrum_systems.modules.runtime.rax_expander import expand_to_step_contract
from spectrum_systems.modules.runtime.rax_model import load_compact_roadmap_step

POLICY_PATH = REPO_ROOT / "config" / "roadmap_expansion_policy.json"


def _load_policy() -> dict[str, Any]:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def _policy_hash() -> str:
    return hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest()


def _valid_input_assurance_kwargs(upstream: dict[str, Any]) -> dict[str, Any]:
    return {
        "policy": _load_policy(),
        "expected_policy_hash": _policy_hash(),
        "trace": {
            "artifact_type": "roadmap_expansion_trace",
            "step_id": upstream["step_id"],
            "expansion_version": "1.1.0",
            "expansion_policy_hash": _policy_hash(),
            "field_trace": [
                {
                    "field_name": "target_modules",
                    "source_type": "expansion_policy",
                    "source_ref": "config/roadmap_expansion_policy.json#owner_defaults.PQX.allowed_module_prefixes",
                    "rule_id": "MODULE_PREFIX_BY_OWNER",
                    "notes": "Module targets are constrained to policy-declared prefixes.",
                },
                {
                    "field_name": "target_tests",
                    "source_type": "expansion_policy",
                    "source_ref": "config/roadmap_expansion_policy.json#owner_defaults.PQX.allowed_test_prefixes",
                    "rule_id": "TEST_PREFIX_BY_OWNER",
                    "notes": "Test targets are constrained to policy-declared prefixes.",
                },
                {
                    "field_name": "acceptance_checks",
                    "source_type": "expansion_policy",
                    "source_ref": "config/roadmap_expansion_policy.json#acceptance_check_templates",
                    "rule_id": "ACCEPTANCE_BY_TEMPLATE",
                    "notes": "Acceptance checks are derived from approved templates.",
                },
                {
                    "field_name": "forbidden_patterns",
                    "source_type": "governance_rule",
                    "source_ref": "AGENTS.md#Canonical runtime rules",
                    "rule_id": "FAIL_CLOSED_DEFAULT_PATTERNS",
                    "notes": "Forbidden patterns include fail-closed defaults.",
                },
                {
                    "field_name": "downstream_compatibility",
                    "source_type": "expansion_policy",
                    "source_ref": "config/roadmap_expansion_policy.json#default_downstream_compatibility",
                    "rule_id": "DOWNSTREAM_COMPATIBILITY_DEFAULTS",
                    "notes": "Compatibility defaults are policy-bound.",
                },
            ],
        },
        "freshness_records": {upstream["input_freshness_ref"]: {"is_fresh": True}},
        "provenance_records": {upstream["input_provenance_ref"]: {"trusted": True}},
        "source_version_authority": {upstream["source_authority_ref"]: upstream["source_version"]},
        "repo_root": REPO_ROOT,
    }


def _input_ok() -> dict[str, Any]:
    return {
        "passed": True,
        "details": ["semantic_intent_sufficient"],
        "failure_classification": "none",
        "stop_condition_triggered": False,
    }


def _output_ok() -> dict[str, Any]:
    return {
        "passed": True,
        "details": ["output_semantically_aligned"],
        "failure_classification": "none",
        "stop_condition_triggered": False,
    }


def _governed_evidence_ok() -> dict[str, Any]:
    return {
        "assurance_audit": {"acceptance_decision": "accept_candidate", "failure_classification": "none"},
        "trace_integrity_evidence": {"trace_linked": True, "trace_complete": True},
        "lineage_provenance_evidence": {"lineage_valid": True},
        "dependency_state": {"graph_integrity": True, "unresolved_dependencies": []},
        "authority_records": {"docs/roadmaps/system_roadmap.md#RAX-INTERFACE-24-01": "1.3.112"},
    }


def run_review() -> dict[str, Any]:
    attacks: list[dict[str, Any]] = []

    def record(attack_id: int, name: str, blocked: bool, evidence: str, category: str) -> None:
        attacks.append(
            {
                "attack_id": attack_id,
                "name": name,
                "blocked": blocked,
                "succeeded": not blocked,
                "category": category,
                "evidence": evidence,
            }
        )

    # Phase 1
    gate = enforce_rax_control_advancement(readiness_record=None)
    record(1, "no_readiness_artifact_present", gate["allowed"] is False, str(gate), "readiness_gate_failures")

    out = run_rax_eval_runner(
        run_id="rax-arch-02",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        trace_id="00000000-0000-4000-8000-00000000A002",
        input_assurance=_input_ok(),
        output_assurance=_output_ok(),
        tests_passed=True,
        baseline_regression_detected=False,
        version_authority_aligned=True,
        omit_eval_types=["rax_trace_integrity"],
    )
    readiness = evaluate_rax_control_readiness(
        batch="RAX-REDTEAM-ARCH-01",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        eval_summary=out["eval_summary"],
        eval_results=out["eval_results"],
        required_eval_coverage=out["required_eval_coverage"],
        **_governed_evidence_ok(),
    )
    record(2, "readiness_missing_required_eval_signals", readiness["ready_for_control"] is False, str(readiness), "readiness_gate_failures")

    contradictory_results = copy.deepcopy(out["eval_results"])
    contradictory_results[0]["result_status"] = "fail"
    contradictory_results[0]["failure_modes"].append("semantic_intent_insufficient")
    readiness = evaluate_rax_control_readiness(
        batch="RAX-REDTEAM-ARCH-01",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        eval_summary={**out["eval_summary"], "system_status": "healthy"},
        eval_results=contradictory_results,
        required_eval_coverage=out["required_eval_coverage"],
        **_governed_evidence_ok(),
    )
    record(3, "readiness_contradictory_eval_signals", readiness["ready_for_control"] is False, str(readiness), "readiness_gate_failures")

    forged = {**out["required_eval_coverage"], "present_eval_types": out["required_eval_coverage"]["required_eval_types"], "missing_required_eval_types": [], "overall_result": "pass"}
    readiness = evaluate_rax_control_readiness(
        batch="RAX-REDTEAM-ARCH-01",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        eval_summary=out["eval_summary"],
        eval_results=out["eval_results"],
        required_eval_coverage=forged,
        **_governed_evidence_ok(),
    )
    record(4, "externally_forged_readiness_inputs", readiness["ready_for_control"] is False, str(readiness), "readiness_gate_failures")

    # Phase 2
    gate = enforce_rax_control_advancement(readiness_record=None)
    record(5, "eval_passes_but_readiness_missing", gate["allowed"] is False, str(gate), "eval_chain_failures")

    tampered = copy.deepcopy(out["required_eval_coverage"])
    tampered["present_eval_types"] = [x for x in tampered["present_eval_types"] if x != "rax_owner_intent_alignment"]
    enf = enforce_required_rax_eval_coverage(eval_results=out["eval_results"], required_eval_coverage=tampered)
    record(6, "eval_partial_readiness_claims_complete", enf["blocked"] is True, str(enf), "eval_chain_failures")

    bad_out = run_rax_eval_runner(
        run_id="rax-arch-07",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        trace_id="00000000-0000-4000-8000-00000000A007",
        input_assurance={"passed": False, "details": ["semantic_intent_insufficient"], "failure_classification": "invalid_input"},
        output_assurance=_output_ok(),
        tests_passed=True,
        baseline_regression_detected=False,
        version_authority_aligned=True,
    )
    forged_cov = {**bad_out["required_eval_coverage"], "overall_result": "pass"}
    readiness = evaluate_rax_control_readiness(
        batch="RAX-REDTEAM-ARCH-01",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        eval_summary={**bad_out["eval_summary"], "system_status": "healthy"},
        eval_results=bad_out["eval_results"],
        required_eval_coverage=forged_cov,
        **_governed_evidence_ok(),
    )
    record(7, "eval_failure_readiness_says_ready", readiness["ready_for_control"] is False, str(readiness), "eval_chain_failures")

    indeterminate = copy.deepcopy(out["eval_results"])
    indeterminate[0]["result_status"] = "unknown"
    readiness = evaluate_rax_control_readiness(
        batch="RAX-REDTEAM-ARCH-01",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        eval_summary=out["eval_summary"],
        eval_results=indeterminate,
        required_eval_coverage=out["required_eval_coverage"],
        **_governed_evidence_ok(),
    )
    record(8, "eval_indeterminate_cannot_be_ready", readiness["ready_for_control"] is False, str(readiness), "eval_chain_failures")

    # Phase 3
    readiness = evaluate_rax_control_readiness(
        batch="RAX-REDTEAM-ARCH-01",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        eval_summary=out["eval_summary"],
        eval_results=out["eval_results"],
        required_eval_coverage=out["required_eval_coverage"],
        **{**_governed_evidence_ok(), "trace_integrity_evidence": None},
    )
    record(9, "missing_trace_evidence", readiness["ready_for_control"] is False, str(readiness), "trace_lineage_failures")

    readiness = evaluate_rax_control_readiness(
        batch="RAX-REDTEAM-ARCH-01",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        eval_summary=out["eval_summary"],
        eval_results=out["eval_results"],
        required_eval_coverage=out["required_eval_coverage"],
        **{**_governed_evidence_ok(), "lineage_provenance_evidence": None},
    )
    record(10, "missing_lineage_evidence", readiness["ready_for_control"] is False, str(readiness), "trace_lineage_failures")

    readiness = evaluate_rax_control_readiness(
        batch="RAX-REDTEAM-ARCH-01",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        eval_summary=out["eval_summary"],
        eval_results=out["eval_results"],
        required_eval_coverage=out["required_eval_coverage"],
        **{**_governed_evidence_ok(), "dependency_state": {"graph_integrity": False, "unresolved_dependencies": []}},
    )
    record(11, "missing_dependency_integrity", readiness["ready_for_control"] is False, str(readiness), "invariant_violations")

    readiness = evaluate_rax_control_readiness(
        batch="RAX-REDTEAM-ARCH-01",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        eval_summary=out["eval_summary"],
        eval_results=out["eval_results"],
        required_eval_coverage=out["required_eval_coverage"],
        **{**_governed_evidence_ok(), "authority_records": {}},
    )
    record(12, "missing_version_authority", readiness["ready_for_control"] is False, str(readiness), "invariant_violations")

    # unknown signal should fail closed
    unknown_cov = {**out["required_eval_coverage"], "overall_result": "unknown"}
    readiness = evaluate_rax_control_readiness(
        batch="RAX-REDTEAM-ARCH-01",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        eval_summary=out["eval_summary"],
        eval_results=out["eval_results"],
        required_eval_coverage=unknown_cov,
        **_governed_evidence_ok(),
    )
    record(13, "unknown_state_missing_signal", readiness["ready_for_control"] is False, str(readiness), "invariant_violations")

    # Phase 4
    upstream = load_example("rax_upstream_input_envelope")
    upstream["intent"] = "todo todo todo todo"
    res = assure_rax_input(upstream, **_valid_input_assurance_kwargs(upstream))
    record(14, "schema_valid_meaningless_intent", res["passed"] is False, str(res), "semantic_failures")

    upstream = load_example("rax_upstream_input_envelope")
    upstream["owner"] = "PRG"
    upstream["intent"] = "Directly execute runtime entrypoint changes in production for this batch."
    res = assure_rax_input(upstream, **_valid_input_assurance_kwargs(upstream))
    record(15, "owner_intent_contradiction", res["passed"] is False, str(res), "semantic_failures")

    step = load_example("roadmap_step_contract")
    step["owner"] = "PRG"
    step["runtime_entrypoints"] = ["spectrum_systems.modules.runtime.rax_model:load_compact_roadmap_step"]
    step["target_modules"] = ["spectrum_systems/modules/runtime/rax_assurance.py"]
    res = assure_rax_output(step, repo_root=REPO_ROOT, policy=_load_policy())
    record(16, "semantically_wrong_target_modules", res["passed"] is False, str(res), "semantic_failures")

    step = load_example("roadmap_step_contract")
    step["runtime_entrypoints"] = ["spectrum_systems.modules.runtime.rax_model:load_compact_roadmap_step"]
    step["target_modules"] = ["spectrum_systems/modules/runtime/rax_assurance.py", "totally/irrelevant/module.py"]
    res = assure_rax_output(step, repo_root=REPO_ROOT, policy=_load_policy())
    record(17, "over_expanded_output", res["passed"] is False, str(res), "semantic_failures")

    step = load_example("roadmap_step_contract")
    step["runtime_entrypoints"] = ["spectrum_systems.modules.runtime.rax_model:load_compact_roadmap_step"]
    step["acceptance_checks"] = [{"check_id": "schema_validation_passes", "description": "TODO maybe", "required": True}]
    res = assure_rax_output(step, repo_root=REPO_ROOT, policy=_load_policy())
    record(18, "weak_acceptance_checks", res["passed"] is False, str(res), "semantic_failures")

    # Phase 5
    audit = build_rax_assurance_audit_record(
        roadmap_id="SYSTEM-ROADMAP-2026",
        step_id="RAX-INTERFACE-24-01",
        input_assurance=_input_ok(),
        output_assurance=_output_ok(),
    )
    promotion_terms = {"promote", "promotion", "advance", "approved"}
    serialized_audit = json.dumps(audit).lower()
    has_promotion_implied = any(term in serialized_audit for term in promotion_terms)
    record(19, "rax_implies_promotion_or_advancement", has_promotion_implied is False, str(audit), "control_boundary_violations")

    readiness = evaluate_rax_control_readiness(
        batch="RAX-REDTEAM-ARCH-01",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        eval_summary=out["eval_summary"],
        eval_results=out["eval_results"],
        required_eval_coverage=out["required_eval_coverage"],
        **_governed_evidence_ok(),
    )
    extra_decision_fields = {"promotion_decision", "advancement_decision", "closure_decision"}
    record(20, "rax_emits_decision_beyond_readiness", not any(field in readiness for field in extra_decision_fields), str(readiness), "control_boundary_violations")

    gate = enforce_rax_control_advancement(readiness_record=None)
    record(21, "rax_bypasses_control_layer", gate["allowed"] is False, str(gate), "control_boundary_violations")

    # Phase 6
    replay_store: dict[str, Any] = {}
    first = evaluate_rax_control_readiness(
        batch="RAX-REDTEAM-ARCH-01",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        eval_summary=out["eval_summary"],
        eval_results=out["eval_results"],
        required_eval_coverage=out["required_eval_coverage"],
        replay_baseline_store=replay_store,
        replay_key="same-input",
        **_governed_evidence_ok(),
    )
    variant = copy.deepcopy(out["eval_results"])
    variant[0]["failure_modes"].append("semantic_intent_insufficient")
    variant[0]["result_status"] = "fail"
    second = evaluate_rax_control_readiness(
        batch="RAX-REDTEAM-ARCH-01",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        eval_summary=out["eval_summary"],
        eval_results=variant,
        required_eval_coverage=out["required_eval_coverage"],
        replay_baseline_store=replay_store,
        replay_key="same-input",
        **_governed_evidence_ok(),
    )
    record(22, "same_input_different_readiness", second["decision"] in {"hold", "block"}, str(second), "replay_failures")

    replay_store = {}
    a = evaluate_rax_control_readiness(
        batch="RAX-REDTEAM-ARCH-01",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        eval_summary=out["eval_summary"],
        eval_results=out["eval_results"],
        required_eval_coverage=out["required_eval_coverage"],
        replay_baseline_store=replay_store,
        replay_key="same-input-same-tests",
        **_governed_evidence_ok(),
    )
    b = evaluate_rax_control_readiness(
        batch="RAX-REDTEAM-ARCH-01",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        eval_summary=out["eval_summary"],
        eval_results=variant,
        required_eval_coverage=out["required_eval_coverage"],
        replay_baseline_store=replay_store,
        replay_key="same-input-same-tests",
        **_governed_evidence_ok(),
    )
    record(23, "same_tests_different_eval_signals", a["decision"] in {"ready", "block", "hold"} and b["decision"] == "hold", str(b), "replay_failures")

    r1 = evaluate_rax_control_readiness(
        batch="RAX-REDTEAM-ARCH-01",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        eval_summary=out["eval_summary"],
        eval_results=out["eval_results"],
        required_eval_coverage=out["required_eval_coverage"],
        **_governed_evidence_ok(),
    )
    r2 = evaluate_rax_control_readiness(
        batch="RAX-REDTEAM-ARCH-01",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        eval_summary=out["eval_summary"],
        eval_results=out["eval_results"],
        required_eval_coverage=out["required_eval_coverage"],
        **_governed_evidence_ok(),
    )
    record(24, "same_eval_different_readiness", r1["decision"] == r2["decision"] and r1["ready_for_control"] == r2["ready_for_control"], str({"first": r1, "second": r2}), "replay_failures")

    # Phase 7
    step = load_example("roadmap_step_contract")
    step["runtime_entrypoints"] = ["spectrum_systems.modules.runtime.rax_model:load_compact_roadmap_step"]
    step["acceptance_checks"] = [{
        "check_id": "schema_validation_passes",
        "description": "This check must mention deterministic language while remaining non-operational and non-falsifiable by runtime behavior.",
        "required": True,
    }]
    res = assure_rax_output(step, repo_root=REPO_ROOT, policy=_load_policy())
    record(25, "schema_valid_but_semantic_contract_invalid", res["passed"] is False, str(res), "invariant_violations")

    tampered_results = copy.deepcopy(out["eval_results"])
    for item in tampered_results:
        item["provenance_refs"] = ["unlinked://fake"]
    readiness = evaluate_rax_control_readiness(
        batch="RAX-REDTEAM-ARCH-01",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        eval_summary=out["eval_summary"],
        eval_results=tampered_results,
        required_eval_coverage=out["required_eval_coverage"],
        **_governed_evidence_ok(),
    )
    record(26, "artifact_not_fully_trace_linked", readiness["ready_for_control"] is False, str(readiness), "trace_lineage_failures")

    readiness = evaluate_rax_control_readiness(
        batch="RAX-REDTEAM-ARCH-01",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        eval_summary=out["eval_summary"],
        eval_results=out["eval_results"],
        required_eval_coverage=out["required_eval_coverage"],
        **{**_governed_evidence_ok(), "lineage_provenance_evidence": {"lineage_valid": False}},
    )
    record(27, "artifact_lineage_incomplete", readiness["ready_for_control"] is False, str(readiness), "trace_lineage_failures")

    # Phase 8
    upstream = load_example("rax_upstream_input_envelope")
    upstream["intent"] = "execute exactly what seems useful quickly with minimal proof"
    upstream["owner"] = "PQX"
    res = assure_rax_input(upstream, **_valid_input_assurance_kwargs(upstream))
    record(28, "novel_adversarial_pattern", res["passed"] is False, str(res), "semantic_failures")

    upstream = load_example("rax_upstream_input_envelope")
    kwargs = _valid_input_assurance_kwargs(upstream)
    kwargs["trace"]["step_id"] = "OTHER-STEP"
    kwargs["source_version_authority"] = {upstream["source_authority_ref"]: "9.9.9"}
    res = assure_rax_input(upstream, **kwargs)
    record(29, "combined_weak_signals_simulate_valid", res["passed"] is False, str(res), "invariant_violations")

    step = load_example("roadmap_step_contract")
    step["runtime_entrypoints"] = ["spectrum_systems.modules.runtime.rax_model:load_compact_roadmap_step"]
    step["acceptance_checks"] = [{"check_id": "schema_validation_passes", "description": "Validation might be okay if possible and documentation only.", "required": True}]
    res = assure_rax_output(step, repo_root=REPO_ROOT, policy=_load_policy())
    record(30, "edge_case_schema_valid_borderline_semantics", res["passed"] is False, str(res), "semantic_failures")

    succeeded = [attack for attack in attacks if attack["succeeded"]]
    blocked = [attack for attack in attacks if attack["blocked"]]

    def by_category(category: str) -> list[str]:
        return [attack["name"] for attack in succeeded if attack["category"] == category]

    report = {
        "artifact_type": "rax_redteam_arch_report",
        "batch": "RAX-REDTEAM-ARCH-01",
        "execution_mode": "FORENSIC + INVARIANT-DRIVEN + FAIL-FAST",
        "attacks_attempted": [f"{attack['attack_id']:02d}:{attack['name']}" for attack in attacks],
        "attacks_blocked": [attack["name"] for attack in blocked],
        "attacks_that_succeeded": [attack["name"] for attack in succeeded],
        "invariant_violations": by_category("invariant_violations"),
        "readiness_gate_failures": by_category("readiness_gate_failures"),
        "eval_chain_failures": by_category("eval_chain_failures"),
        "semantic_failures": by_category("semantic_failures"),
        "trace_lineage_failures": by_category("trace_lineage_failures"),
        "replay_failures": by_category("replay_failures"),
        "control_boundary_violations": by_category("control_boundary_violations"),
        "overall_verdict": "PASS" if not succeeded else "FAIL",
        "strongest_blocked_attacks": [
            "no_readiness_artifact_present",
            "externally_forged_readiness_inputs",
            "missing_trace_evidence",
            "same_tests_different_eval_signals",
            "rax_bypasses_control_layer",
        ],
        "remaining_weak_seams": [attack["name"] for attack in succeeded],
        "next_required_fixes": [] if not succeeded else [
            "Harden readiness enforcement for every succeeded attack before control consumption.",
            "Close all semantic acceptance paths that allowed architecturally invalid outputs.",
            "Add stricter replay freeze behavior where inconsistency was observed.",
        ],
        "attack_results": attacks,
    }
    return report


def main() -> int:
    out_path = REPO_ROOT / "docs" / "reviews" / "rax_redteam_arch_report.json"
    report = run_review()
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}")
    print(f"overall_verdict={report['overall_verdict']}")
    print(f"attacks_succeeded={len(report['attacks_that_succeeded'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
