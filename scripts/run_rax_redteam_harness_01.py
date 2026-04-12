#!/usr/bin/env python3
"""RAX-REDTEAM-HARNESS-01 adversarial harness execution.

Produces a deterministic forensic report over 28 attack scenarios.
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


def run_harness() -> dict[str, Any]:
    attacks: list[dict[str, Any]] = []

    def record(attack_id: int, name: str, blocked: bool, evidence: str, category: str) -> None:
        attacks.append({
            "attack_id": attack_id,
            "name": name,
            "blocked": blocked,
            "succeeded": not blocked,
            "category": category,
            "evidence": evidence,
        })

    # 01
    out = run_rax_eval_runner(
        run_id="redteam-01",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        trace_id="00000000-0000-4000-8000-000000000001",
        input_assurance=_input_ok(),
        output_assurance=_output_ok(),
        tests_passed=True,
        baseline_regression_detected=False,
        version_authority_aligned=True,
        omit_eval_types=["rax_trace_integrity"],
    )
    readiness = evaluate_rax_control_readiness(
        batch="RAX-EVAL-01",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        eval_summary=out["eval_summary"],
        eval_results=out["eval_results"],
        required_eval_coverage=out["required_eval_coverage"],
    )
    record(1, "tests_pass_but_no_required_evals", readiness["ready_for_control"] is False, str(out["required_eval_coverage"]), "test_authority")

    # 02
    tampered = copy.deepcopy(out["required_eval_coverage"])
    tampered["present_eval_types"] = [x for x in tampered["present_eval_types"] if x != "rax_owner_intent_alignment"]
    enf = enforce_required_rax_eval_coverage(eval_results=out["eval_results"], required_eval_coverage=tampered)
    record(2, "tests_pass_but_eval_summary_missing", enf["blocked"] is True, str(enf), "test_authority")

    # 03
    # No primitive enforces mandatory presence of readiness artifact before advancement.
    record(3, "tests_pass_but_control_readiness_missing", False, "No built-in gate enforces existence of control-readiness artifact.", "test_authority")

    # 04
    upstream = load_example("rax_upstream_input_envelope")
    upstream["intent"] = "todo todo todo todo"
    res = assure_rax_input(upstream, **_valid_input_assurance_kwargs(upstream))
    record(4, "schema_valid_but_semantically_empty_intent", res["passed"] is False, str(res), "semantic")

    # 05
    upstream = load_example("rax_upstream_input_envelope")
    upstream["owner"] = "PRG"
    upstream["intent"] = "Directly execute runtime entrypoint changes in production for this batch."
    res = assure_rax_input(upstream, **_valid_input_assurance_kwargs(upstream))
    record(5, "schema_valid_but_owner_intent_contradiction", res["passed"] is False, str(res), "semantic")

    # 06
    step = load_example("roadmap_step_contract")
    step["owner"] = "PRG"
    step["runtime_entrypoints"] = ["spectrum_systems.modules.runtime.rax_model:load_compact_roadmap_step"]
    step["target_modules"] = ["spectrum_systems/modules/runtime/rax_assurance.py"]
    res = assure_rax_output(step, repo_root=REPO_ROOT, policy=_load_policy())
    record(6, "schema_valid_but_wrong_target_modules", res["passed"] is False, str(res), "semantic")

    # 07
    step = load_example("roadmap_step_contract")
    step["runtime_entrypoints"] = ["spectrum_systems.modules.runtime.rax_model:load_compact_roadmap_step"]
    step["target_modules"] = [
        "spectrum_systems/modules/runtime/rax_assurance.py",
        "totally/irrelevant/module.py",
    ]
    res = assure_rax_output(step, repo_root=REPO_ROOT, policy=_load_policy())
    record(7, "over_expanded_output", res["passed"] is False, str(res), "semantic")

    # 08
    step = load_example("roadmap_step_contract")
    step["runtime_entrypoints"] = ["spectrum_systems.modules.runtime.rax_model:load_compact_roadmap_step"]
    step["acceptance_checks"] = [{"check_id": "schema_validation_passes", "description": "TODO maybe", "required": True}]
    res = assure_rax_output(step, repo_root=REPO_ROOT, policy=_load_policy())
    record(8, "meaningless_acceptance_checks", res["passed"] is False, str(res), "semantic")

    # 09
    step = load_example("roadmap_step_contract")
    step["runtime_entrypoints"] = ["spectrum_systems.modules.runtime.rax_model:load_compact_roadmap_step"]
    step["acceptance_checks"] = [{"check_id": "schema_validation_passes", "description": "This check documents formatting consistency across files only.", "required": True}]
    res = assure_rax_output(step, repo_root=REPO_ROOT, policy=_load_policy())
    record(9, "recognized_shape_but_non_behavioral_checks", res["passed"] is False, str(res), "semantic")

    # 10
    upstream = load_example("rax_upstream_input_envelope")
    kwargs = _valid_input_assurance_kwargs(upstream)
    kwargs["trace"] = None
    res = assure_rax_input(upstream, **kwargs)
    record(10, "missing_expansion_trace", res["passed"] is False, str(res), "trace")

    # 11
    upstream = load_example("rax_upstream_input_envelope")
    kwargs = _valid_input_assurance_kwargs(upstream)
    kwargs["trace"]["field_trace"] = kwargs["trace"]["field_trace"][:-1]
    res = assure_rax_input(upstream, **kwargs)
    record(11, "partial_trace_only", res["passed"] is False, str(res), "trace")

    # 12
    upstream = load_example("rax_upstream_input_envelope")
    kwargs = _valid_input_assurance_kwargs(upstream)
    kwargs["source_version_authority"] = {upstream["source_authority_ref"]: "9.9.9"}
    res = assure_rax_input(upstream, **kwargs)
    record(12, "source_version_drift", res["passed"] is False, str(res), "trace")

    # 13
    upstream = load_example("rax_upstream_input_envelope")
    upstream["source_version"] = "9.9.9"
    kwargs = _valid_input_assurance_kwargs(upstream)
    kwargs["source_version_authority"] = {upstream["source_authority_ref"]: "9.9.9"}
    res = assure_rax_input(upstream, **kwargs)
    record(13, "fake_authority_version_alignment", res["passed"] is False, str(res), "trace")

    # 14
    upstream = load_example("rax_upstream_input_envelope")
    upstream["depends_on"] = ["RAX-INTERFACE-24-00", " RAX-INTERFACE-24-00 "]
    res = assure_rax_input(upstream, **_valid_input_assurance_kwargs(upstream))
    record(14, "ambiguous_normalization_collapse", res["passed"] is False, str(res), "semantic")

    # 15
    upstream = load_example("rax_upstream_input_envelope")
    upstream["depends_on"] = ["MISSING-STEP-01", "RAX-INTERFACE-24-00"]
    res = assure_rax_input(upstream, **_valid_input_assurance_kwargs(upstream))
    record(15, "dependency_graph_corruption", res["passed"] is False, str(res), "semantic")

    # 16
    audit = build_rax_assurance_audit_record(
        roadmap_id="SYSTEM-ROADMAP-2026",
        step_id="RAX-INTERFACE-24-01",
        input_assurance={"passed": False, "details": ["semantic_intent_insufficient"], "failure_classification": "invalid_input", "stop_condition_triggered": True},
        output_assurance={"passed": True, "details": ["ok"], "failure_classification": "none", "stop_condition_triggered": False},
    )
    leak = any(k in audit for k in ("passed_steps", "status_updates"))
    record(16, "partial_success_leak", leak is False and audit["acceptance_decision"] != "accept_candidate", str(audit), "readiness")

    # 17
    out = run_rax_eval_runner(
        run_id="redteam-17",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        trace_id="00000000-0000-4000-8000-000000000017",
        input_assurance=_input_ok(),
        output_assurance=_output_ok(),
        tests_passed=True,
        baseline_regression_detected=False,
        version_authority_aligned=True,
        omit_eval_types=["rax_trace_integrity", "rax_owner_intent_alignment"],
    )
    forged_cov = {
        "required_eval_types": out["required_eval_coverage"]["required_eval_types"],
        "present_eval_types": out["required_eval_coverage"]["required_eval_types"],
        "missing_required_eval_types": [],
        "overall_result": "pass",
    }
    readiness = evaluate_rax_control_readiness(
        batch="RAX-EVAL-01", target_ref="roadmap_step_contract:RAX-INTERFACE-24-01", eval_summary=out["eval_summary"], eval_results=out["eval_results"], required_eval_coverage=forged_cov
    )
    record(17, "fake_readiness_from_partial_eval_set", readiness["ready_for_control"] is False, str(readiness), "readiness")

    # 18
    contradictory_results = [
        {
            "artifact_type": "eval_result",
            "schema_version": "1.0.0",
            "eval_case_id": "x:rax_input_semantic_sufficiency",
            "run_id": "x",
            "trace_id": "t",
            "result_status": "fail",
            "score": 0.0,
            "failure_modes": ["eval_type:rax_input_semantic_sufficiency", "semantic_intent_insufficient", "runner:rax_eval_runner:1.0.0"],
            "provenance_refs": ["roadmap_step_contract:RAX-INTERFACE-24-01"],
        }
    ]
    cov = {
        "required_eval_types": [
            "rax_input_semantic_sufficiency", "rax_owner_intent_alignment", "rax_normalization_integrity", "rax_output_semantic_alignment", "rax_acceptance_check_strength", "rax_trace_integrity", "rax_version_authority_alignment", "rax_regression_against_baseline", "rax_control_readiness"
        ],
        "present_eval_types": [
            "rax_input_semantic_sufficiency", "rax_owner_intent_alignment", "rax_normalization_integrity", "rax_output_semantic_alignment", "rax_acceptance_check_strength", "rax_trace_integrity", "rax_version_authority_alignment", "rax_regression_against_baseline", "rax_control_readiness"
        ],
        "missing_required_eval_types": [],
        "overall_result": "pass",
    }
    readiness = evaluate_rax_control_readiness(batch="RAX-EVAL-01", target_ref="roadmap_step_contract:RAX-INTERFACE-24-01", eval_summary={"artifact_type": "eval_summary", "schema_version": "1.0.0", "trace_id": "t", "eval_run_id": "x", "pass_rate": 1.0, "failure_rate": 0.0, "drift_rate": 0.0, "reproducibility_score": 1.0, "system_status": "healthy"}, eval_results=contradictory_results, required_eval_coverage=cov)
    record(18, "readiness_with_contradictory_signals", readiness["ready_for_control"] is False, str(readiness), "readiness")

    # 19
    audit = build_rax_assurance_audit_record(
        roadmap_id="SYSTEM-ROADMAP-2026",
        step_id="RAX-INTERFACE-24-01",
        input_assurance={"passed": False, "details": [], "failure_classification": "invalid_input", "stop_condition_triggered": True},
        output_assurance={"passed": True, "details": [], "failure_classification": "none", "stop_condition_triggered": False},
    )
    record(19, "readiness_without_counter_evidence_population", bool(audit["counter_evidence"]) is True, str(audit), "readiness")

    # 20
    audit = build_rax_assurance_audit_record(
        roadmap_id="SYSTEM-ROADMAP-2026",
        step_id="RAX-INTERFACE-24-01",
        input_assurance={"passed": False, "details": ["x"], "failure_classification": "invalid_input", "stop_condition_triggered": False},
        output_assurance={"passed": True, "details": ["y"], "failure_classification": "none", "stop_condition_triggered": False},
    )
    record(20, "stop_condition_forgery", audit["stop_condition_triggered"] is True, str(audit), "readiness")

    # 21
    upstream = load_example("rax_upstream_input_envelope")
    model = load_compact_roadmap_step(upstream)
    c1, t1 = expand_to_step_contract(model, policy=_load_policy(), policy_path=POLICY_PATH)
    c2, t2 = expand_to_step_contract(model, policy=_load_policy(), policy_path=POLICY_PATH)
    record(21, "same_input_different_output", c1 == c2 and t1 == t2, "deterministic output confirmed", "replay")

    # 22
    # No persisted replay baseline is consulted by runner; no freeze signal path exists.
    record(22, "same_input_same_tests_different_eval_signals", False, "Runner is stateless and performs no cross-run freeze/diff check.", "replay")

    # 23
    out = run_rax_eval_runner(
        run_id="redteam-23",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        trace_id="00000000-0000-4000-8000-000000000023",
        input_assurance=_input_ok(),
        output_assurance=_output_ok(),
        tests_passed=True,
        baseline_regression_detected=False,
        version_authority_aligned=True,
        omit_eval_types=["rax_control_readiness"],
    )
    enf = enforce_required_rax_eval_coverage(eval_results=out["eval_results"], required_eval_coverage=out["required_eval_coverage"])
    record(23, "missing_required_artifact_in_chain", enf["blocked"] is True, str(enf), "trace")

    # 24
    out = run_rax_eval_runner(
        run_id="redteam-24",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        trace_id="00000000-0000-4000-8000-000000000024",
        input_assurance=_input_ok(),
        output_assurance=_output_ok(),
        tests_passed=True,
        baseline_regression_detected=False,
        version_authority_aligned=True,
    )
    tampered_results = copy.deepcopy(out["eval_results"])
    for item in tampered_results:
        item["provenance_refs"] = ["unlinked://fake"]
    readiness = evaluate_rax_control_readiness(
        batch="RAX-EVAL-01",
        target_ref="roadmap_step_contract:RAX-INTERFACE-24-01",
        eval_summary=out["eval_summary"],
        eval_results=tampered_results,
        required_eval_coverage=out["required_eval_coverage"],
    )
    record(24, "artifact_present_but_not_trace_linked", readiness["ready_for_control"] is False, str(readiness), "trace")

    # 25
    # No lineage validator is part of readiness calculation.
    record(25, "artifact_present_but_not_lineage-valid", False, "No lineage validation hook in control readiness computation.", "trace")

    # 26
    upstream = load_example("rax_upstream_input_envelope")
    upstream["intent"] = "Runtime Entrypoint execution directively requested for batch run."
    upstream["owner"] = "PRG"
    res = assure_rax_input(upstream, **_valid_input_assurance_kwargs(upstream))
    record(26, "nested_variant_of_known_exploit", res["passed"] is False, str(res), "semantic")

    # 27
    upstream = load_example("rax_upstream_input_envelope")
    kwargs = _valid_input_assurance_kwargs(upstream)
    kwargs["trace"]["step_id"] = "OTHER-STEP"
    res = assure_rax_input(upstream, **kwargs)
    record(27, "cross_step_contamination_variant", res["passed"] is False, str(res), "trace")

    # 28
    step = load_example("roadmap_step_contract")
    step["runtime_entrypoints"] = ["spectrum_systems.modules.runtime.rax_model:load_compact_roadmap_step"]
    step["acceptance_checks"] = [{
        "check_id": "schema_validation_passes",
        "description": "This check must mention deterministic language while remaining non-operational and non-falsifiable by runtime behavior.",
        "required": True,
    }]
    res = assure_rax_output(step, repo_root=REPO_ROOT, policy=_load_policy())
    record(28, "adversarial_literal_variant_not_in_regression_tests", res["passed"] is False, str(res), "semantic")

    succeeded = [a["name"] for a in attacks if a["succeeded"]]
    blocked = [a["name"] for a in attacks if a["blocked"]]

    by_cat = lambda cat: [a["name"] for a in attacks if a["succeeded"] and a["category"] == cat]

    report = {
        "artifact_type": "rax_redteam_harness_report",
        "batch": "RAX-REDTEAM-HARNESS-01",
        "execution_mode": "FORENSIC ADVERSARIAL REVIEW WITH FAIL-FAST REPORTING",
        "attacks_attempted": [a["name"] for a in attacks],
        "attacks_blocked": blocked,
        "attacks_that_succeeded": succeeded,
        "test_authority_bypass_failures": by_cat("test_authority"),
        "semantic_failures": by_cat("semantic"),
        "trace_failures": by_cat("trace"),
        "readiness_failures": by_cat("readiness"),
        "replay_failures": by_cat("replay"),
        "partial_success_leaks": [a["name"] for a in attacks if a["name"] == "partial_success_leak" and a["succeeded"]],
        "control_readiness_bypass_possible": any(name in succeeded for name in ["fake_readiness_from_partial_eval_set", "readiness_with_contradictory_signals", "tests_pass_but_control_readiness_missing"]),
        "overall_verdict": "FAIL" if succeeded else "PASS",
        "strongest_blocked_attacks": [
            "tests_pass_but_no_required_evals",
            "missing_expansion_trace",
            "source_version_drift",
            "stop_condition_forgery",
            "same_input_different_output",
        ],
        "remaining_weak_seams": succeeded,
        "next_required_fixes": [
            "Make control-readiness artifact mandatory gate before any advancement decision.",
            "Bind source-version authority to immutable governed authority records; reject caller-supplied overrides.",
            "Require all target_modules and target_tests to satisfy owner prefix constraints (not any-of).",
            "Add dependency existence + state validation for depends_on graph integrity.",
            "Recompute required eval coverage from eval_results inside readiness; ignore forged summary signals.",
            "Add contradiction gate in readiness: any eval_result failure reason forces ready_for_control=false.",
            "Add provenance/trace-lineage validators into readiness computation.",
            "Add replay baseline store and cross-run inconsistency freeze policy.",
        ],
        "attack_results": attacks,
    }
    return report


def main() -> int:
    out_path = REPO_ROOT / "docs" / "reviews" / "rax_redteam_harness_report_01.json"
    report = run_harness()
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}")
    print(f"overall_verdict={report['overall_verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
