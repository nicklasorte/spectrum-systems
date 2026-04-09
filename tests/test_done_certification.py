"""Tests for DONE-01 deterministic fail-closed done certification gate."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from spectrum_systems.modules.governance.done_certification import (
    DoneCertificationError,
    run_done_certification,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_EXAMPLES = _REPO_ROOT / "contracts" / "examples"


def _load_example(name: str) -> Dict[str, Any]:
    return json.loads((_EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))


def _regression_result_pass() -> Dict[str, Any]:
    return {
        "blocked": False,
        "regression_status": "pass",
        "schema_version": "1.1.0",
        "artifact_type": "regression_result",
        "run_id": "reg-run-001",
        "suite_id": "suite-001",
        "created_at": "2026-03-28T00:00:00Z",
        "total_traces": 1,
        "passed_traces": 1,
        "failed_traces": 0,
        "pass_rate": 1.0,
        "overall_status": "pass",
        "results": [
            {
                "trace_id": "trace-001",
                "replay_result_id": "replay-001",
                "analysis_id": "analysis-001",
                "decision_status": "consistent",
                "reproducibility_score": 1.0,
                "drift_type": "",
                "passed": True,
                "failure_reasons": [],
                "baseline_replay_result_id": "base-001",
                "current_replay_result_id": "cur-001",
                "baseline_trace_id": "trace-001",
                "current_trace_id": "trace-001",
                "baseline_reference": "replay_result:base-001",
                "current_reference": "replay_result:cur-001",
                "mismatch_summary": [],
                "comparison_digest": "a" * 64,
            }
        ],
        "summary": {"drift_counts": {}, "average_reproducibility_score": 1.0},
    }


def _write_json(path: Path, payload: Dict[str, Any]) -> str:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def _write_inputs(tmp_path: Path) -> Dict[str, str]:
    replay = _load_example("replay_result")
    replay["consistency_status"] = "match"
    replay["drift_detected"] = False
    replay["failure_reason"] = None
    trace_id = "6d4fcac1-1af6-4fca-9e35-6e7d0fa7d4aa"
    replay["trace_id"] = trace_id
    run_id = replay["replay_run_id"]

    regression = _regression_result_pass()
    regression["run_id"] = run_id
    regression["results"][0]["trace_id"] = trace_id
    regression["results"][0]["baseline_trace_id"] = trace_id
    regression["results"][0]["current_trace_id"] = trace_id
    certification_pack = _load_example("control_loop_certification_pack")
    certification_pack["run_id"] = run_id
    certification_pack["decision"] = "pass"
    certification_pack["certification_status"] = "certified"
    certification_pack["provenance_trace_refs"]["trace_refs"] = [trace_id]

    error_budget = _load_example("error_budget_status")
    error_budget["budget_status"] = "healthy"
    error_budget["trace_refs"]["trace_id"] = trace_id

    control_decision = _load_example("evaluation_control_decision")
    control_decision["run_id"] = run_id
    control_decision["system_status"] = "healthy"
    control_decision["system_response"] = "allow"
    control_decision["decision"] = "allow"
    control_decision["trace_id"] = trace_id

    failure_injection = _load_example("governed_failure_injection_summary")
    failure_injection["fail_count"] = 0
    failure_injection["pass_count"] = failure_injection["case_count"]
    failure_injection["trace_refs"]["primary"] = trace_id
    failure_injection["trace_refs"]["related"] = []
    for result in failure_injection["results"]:
        result["passed"] = True
        result["expected_outcome"] = "block"
        result["observed_outcome"] = "block"
        result["invariant_violations"] = []
        result["trace_refs"]["primary"] = trace_id
        result["trace_refs"]["related"] = []

    repo_review_snapshot = _load_example("repo_review_snapshot")
    repo_review_snapshot["trace_linkage"]["trace_id"] = trace_id
    repo_review_snapshot["findings_summary"] = {
        "redundancy_findings": 0,
        "drift_findings": 0,
        "eval_coverage_gaps": 0,
        "control_bypass_findings": 0,
    }
    repo_health_eval_summary = _load_example("eval_summary")
    repo_health_eval_summary["trace_id"] = trace_id
    repo_health_eval_summary["system_status"] = "healthy"

    return {
        "replay_result_ref": _write_json(tmp_path / "replay.json", replay),
        "regression_result_ref": _write_json(tmp_path / "regression.json", regression),
        "certification_pack_ref": _write_json(tmp_path / "certification_pack.json", certification_pack),
        "error_budget_ref": _write_json(tmp_path / "error_budget.json", error_budget),
        "policy_ref": _write_json(tmp_path / "policy.json", control_decision),
        "repo_review_snapshot_ref": _write_json(tmp_path / "repo_review_snapshot.json", repo_review_snapshot),
        "repo_health_eval_summary_ref": _write_json(tmp_path / "repo_health_eval_summary.json", repo_health_eval_summary),
        "enforcement_result_ref": _write_json(
            tmp_path / "enforcement.json",
            {
                "artifact_type": "enforcement_result",
                "schema_version": "1.1.0",
                "enforcement_result_id": "enf-001",
                "timestamp": "2026-03-28T00:00:00Z",
                "trace_id": trace_id,
                "run_id": run_id,
                "input_decision_reference": "ecd-001",
                "enforcement_action": "allow_execution",
                "final_status": "allow",
                "rationale_code": "allow_authorized",
                "fail_closed": False,
                "enforcement_path": "baf_single_path",
                "provenance": {
                    "source_artifact_type": "evaluation_control_decision",
                    "source_artifact_id": control_decision["decision_id"],
                },
            },
        ),
        "eval_coverage_summary_ref": _write_json(
            tmp_path / "coverage.json",
            {
                "artifact_type": "eval_coverage_summary",
                "schema_version": "1.1.0",
                "id": "coverage-001",
                "coverage_run_id": run_id,
                "timestamp": "2026-03-28T00:00:00Z",
                "trace_refs": {"primary": trace_id, "related": []},
                "dataset_refs": ["contracts/examples/eval_case_dataset.json"],
                "total_eval_cases": 1,
                "covered_slices": ["runtime_guardrails"],
                "uncovered_required_slices": [],
                "slice_case_counts": {"runtime_guardrails": 1},
                "risk_weighted_coverage_score": 1.0,
                "coverage_gaps": [],
            },
        ),
        "trust_spine_evidence_cohesion_result_ref": _write_json(
            tmp_path / "trust_spine_evidence_cohesion_result.json",
            {
                "artifact_type": "trust_spine_evidence_cohesion_result",
                "schema_version": "1.0.0",
                "deterministic_cohesion_id": "tsec-aaaaaaaaaaaaaaaa",
                "overall_decision": "ALLOW",
                "evaluated_surfaces": [
                    "control_surface_manifest",
                    "control_surface_enforcement_result",
                    "control_surface_obedience_result",
                    "trust_spine_invariant_result",
                    "done_certification_record",
                ],
                "artifact_refs": {
                    "manifest_ref": "outputs/control_surface_manifest/control_surface_manifest.json",
                    "enforcement_result_ref": "outputs/control_surface_enforcement/control_surface_enforcement_result.json",
                    "obedience_result_ref": "outputs/control_surface_obedience/control_surface_obedience_result.json",
                    "invariant_result_ref": "outputs/trust_spine_invariants/trust_spine_invariant_result.json",
                    "done_certification_ref": "outputs/done_certification/done_certification_record.json",
                },
                "contradiction_categories": [],
                "blocking_reasons": [],
                "missing_required_evidence_refs": [],
                "mismatched_artifact_references": [],
                "inconsistent_truth_context_fields": [],
                "trace": {
                    "producer": "spectrum_systems.modules.runtime.trust_spine_evidence_cohesion",
                    "policy_ref": "CON-033.trust_spine_evidence_cohesion.v1",
                },
            },
        ),
        "failure_injection_ref": _write_json(tmp_path / "failure_injection.json", failure_injection),
    }




def _attach_valid_tpa_refs(refs: Dict[str, str], tmp_path: Path, *, step_id: str = "AI-01") -> Dict[str, str]:
    plan = {
        "artifact_kind": "plan",
        "execution_mode": "feature_build",
        "files_touched": ["spectrum_systems/modules/runtime/pqx_sequence_runner.py"],
        "seams_reused": ["pqx_sequence_runner.execute_sequence_run"],
        "abstraction_intent": "reuse_existing",
        "context_bundle_ref": "context_bundle_v2:ctx2-abc123abc123abcd",
        "known_risk_refs": ["risk_register:risk-high-1"],
        "prior_failure_pattern_refs": ["failure_pattern:unused-helper-regression"],
        "modules_affected": ["spectrum_systems/modules/runtime/pqx_sequence_runner.py"],
        "improvement_objective": "Prevent known context-linked failures while keeping TPA bounded.",
        "context_rationale": "Recent failures show repeated helper/indirection regressions.",
        "constraints_acknowledged": {"build_small": True, "no_redesign": True},
    }
    build_signals = {
        "files_changed_count": 1,
        "lines_added": 22,
        "lines_removed": 8,
        "net_line_delta": 14,
        "functions_added_count": 2,
        "functions_removed_count": 0,
        "helpers_added_count": 1,
        "helpers_removed_count": 0,
        "wrappers_collapsed_count": 0,
        "deletions_count": 0,
        "public_surface_delta_count": 1,
        "approximate_max_nesting_delta": 1,
        "approximate_branching_delta": 1,
        "abstraction_added_count": 1,
        "abstraction_removed_count": 0,
    }
    simplify_signals = {
        "files_changed_count": 1,
        "lines_added": 10,
        "lines_removed": 18,
        "net_line_delta": -8,
        "functions_added_count": 1,
        "functions_removed_count": 1,
        "helpers_added_count": 0,
        "helpers_removed_count": 1,
        "wrappers_collapsed_count": 1,
        "deletions_count": 1,
        "public_surface_delta_count": 0,
        "approximate_max_nesting_delta": -1,
        "approximate_branching_delta": -1,
        "abstraction_added_count": 0,
        "abstraction_removed_count": 1,
    }
    build = {
        "artifact_kind": "build",
        "files_touched": ["spectrum_systems/modules/runtime/pqx_sequence_runner.py"],
        "new_layers": 0,
        "unused_helpers": [],
        "unnecessary_indirection": [],
        "plan_scope_match": True,
        "abstraction_justifications": [],
        "context_bundle_ref": "context_bundle_v2:ctx2-abc123abc123abcd",
        "known_failure_patterns_avoided": ["failure_pattern:unused-helper-regression"],
        "existing_abstractions_satisfied": True,
        "speculative_expansion_detected": False,
        "reused_module_refs": ["spectrum_systems/modules/runtime/pqx_sequence_runner.py"],
        "complexity_signals": build_signals,
    }
    simplify = {
        "artifact_kind": "simplify",
        "source_build_artifact_id": f"tpa:run-001:{step_id}-B",
        "actions": ["reduce_nesting", "rename_for_clarity"],
        "behavior_changed": False,
        "new_layers_introduced": 0,
        "context_bundle_ref": "context_bundle_v2:ctx2-abc123abc123abcd",
        "redundant_code_paths_removed": 1,
        "duplicate_logic_collapsed": [],
        "pattern_consistency_refs": ["pattern:pqx-tpa-runtime-style"],
        "complexity_signals": simplify_signals,
        "delete_pass": {
            "deletion_considered": True,
            "deletion_performed": True,
            "deletion_rejected_reason": None,
            "deleted_items": ["obsolete_wrapper:legacy-branch"],
            "collapsed_abstractions": ["adapter-layer:thin-wrapper"],
            "removed_helpers": ["helper:unused_context_glue"],
            "removed_wrappers": ["wrapper:legacy_wrapper"],
            "indirection_avoided": ["direct_call:use_existing_runtime_seam"],
        },
    }
    gate = {
        "artifact_kind": "gate",
        "build_artifact_id": f"tpa:run-001:{step_id}-B",
        "simplify_artifact_id": f"tpa:run-001:{step_id}-S",
        "behavioral_equivalence": True,
        "contract_valid": True,
        "tests_valid": True,
        "selected_pass": "pass_2_simplify",
        "rejected_pass": "pass_1_build",
        "selection_inputs": {
            "build_artifact_id": f"tpa:run-001:{step_id}-B",
            "simplify_artifact_id": f"tpa:run-001:{step_id}-S",
            "comparison_inputs_present": True,
        },
        "selection_metrics": {
            "build": build_signals,
            "simplify": simplify_signals,
            "simplify_delta": {k: simplify_signals[k] - build_signals[k] for k in build_signals},
        },
        "selection_rationale": "equivalence proven and simplify has lower complexity",
        "promotion_ready": True,
        "fail_closed_reason": None,
        "context_bundle_ref": "context_bundle_v2:ctx2-abc123abc123abcd",
        "review_signal_refs": ["review_artifact:rvw-001"],
        "eval_signal_refs": ["eval_result:ev-001"],
        "addressed_failure_pattern_refs": ["failure_pattern:unused-helper-regression"],
        "unaddressed_failure_pattern_refs": [],
        "high_risk_unmitigated": False,
        "risk_mitigation_refs": ["mitigation:risk-high-1-covered"],
        "simplicity_review": {
            "decision": "allow",
            "overall_severity": "low",
            "findings": [
                {"category": "delete_instead_of_abstract", "severity": "low", "message": "Delete-pass completed."}
            ],
            "report_ref": "docs/reviews/2026-04-04-tpa-completion-hardening.md",
        },
        "complexity_regression_gate": {
            "decision": "allow",
            "policy_ref": "policy:tpa-complexity-regression:v1",
            "regression_detected": False,
            "historical_baseline_available": True,
            "historical_baseline_ref": "baseline:tpa:AI-01",
            "exception_justified": False,
        },
    }

    phase_payloads = {"plan": plan, "build": build, "simplify": simplify, "gate": gate}
    phase_suffix = {"plan": "P", "build": "B", "simplify": "S", "gate": "G"}
    for phase, payload in phase_payloads.items():
        artifact = {
            "artifact_type": "tpa_slice_artifact",
            "schema_version": "1.3.0",
            "artifact_id": f"tpa:run-001:{step_id}-{phase_suffix[phase]}",
            "request_id": f"req:{step_id}:{phase}",
            "run_id": "run-001",
            "trace_id": "trace-001",
            "slice_id": f"{step_id}-{phase_suffix[phase]}",
            "step_id": step_id,
            "phase": phase,
            "produced_at": "2026-04-04T00:00:00Z",
            "artifact": payload,
            "authenticity": {
                "issuer": "TPA",
                "key_id": "tpa-hs256-v1",
                "payload_digest": f"sha256:{'0'*64}",
                "audience": "pqx_repo_write_boundary",
                "scope": f"repo_write_lineage:tpa_slice_artifact:req:{step_id}:{phase}:trace-001",
                "issued_at": "2026-04-04T00:00:00Z",
                "expires_at": "2026-04-04T00:15:00Z",
                "lineage_token_id": "lin-1234567890abcdef12345678",
                "attestation": "0" * 64,
            },
        }
        refs[f"tpa_{phase}_artifact"] = _write_json(tmp_path / f"tpa_{phase}.json", artifact)

    envelope = {
        "artifact_type": "tpa_certification_envelope",
        "schema_version": "1.0.0",
        "envelope_id": f"tpa-cert:run-001:{step_id}",
        "run_id": "run-001",
        "trace_id": "trace-001",
        "step_id": step_id,
        "generated_at": "2026-04-04T00:00:00Z",
        "execution_mode": "feature_build",
        "tpa_mode": "full",
        "evidence_refs": {
            "tpa_plan_artifact_ref": refs["tpa_plan_artifact"],
            "tpa_build_artifact_ref": refs["tpa_build_artifact"],
            "tpa_simplify_artifact_ref": refs["tpa_simplify_artifact"],
            "tpa_gate_artifact_ref": refs["tpa_gate_artifact"],
            "equivalence_evidence_refs": ["gate.behavioral_equivalence:true"],
            "replay_ref": refs["replay_result_ref"],
        },
        "gate_decision": {
            "selected_pass": "pass_2_simplify",
            "promotion_ready": True,
            "simplicity_decision": "allow",
            "complexity_regression_decision": "allow",
        },
        "certification_decision": "certified",
        "blocking_reasons": [],
    }
    refs["tpa_certification_envelope_ref"] = _write_json(tmp_path / "tpa_certification_envelope.json", envelope)

    refs["scope_file_path"] = "spectrum_systems/modules/runtime/pqx_sequence_runner.py"
    refs["scope_module"] = "spectrum_systems.modules.runtime.pqx_sequence_runner"
    refs["scope_artifact_type"] = "pqx_generated_slice"
    refs["pqx_step_metadata"] = {"step_id": step_id}
    return refs



def test_certification_pass(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    first = run_done_certification(refs)
    second = run_done_certification(refs)

    assert first["final_status"] == "PASSED"
    assert first["system_response"] == "allow"
    assert first["blocking_reasons"] == []
    assert first["trust_spine_invariant_result"]["passed"] is True
    assert first["trust_spine_evidence_completeness_result"]["passed"] is True
    assert first["trust_spine_evidence_cohesion_result"]["passed"] is True
    assert first["check_results"]["trust_spine_evidence_completeness"]["passed"] is True
    assert first["check_results"]["trust_spine_evidence_cohesion"]["passed"] is True
    assert first["check_results"]["tpa_compliance"]["passed"] is True
    assert first["check_results"]["system_readiness"]["passed"] is True
    assert first["tpa_required"] is False
    assert first["tpa_status"] == "NOT_REQUIRED"
    assert first == second


def test_certification_warn_when_minor_degradation_and_policy_permits(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    review = json.loads(Path(refs["repo_review_snapshot_ref"]).read_text(encoding="utf-8"))
    review["findings_summary"]["redundancy_findings"] = 1
    Path(refs["repo_review_snapshot_ref"]).write_text(json.dumps(review), encoding="utf-8")
    control = json.loads(Path(refs["policy_ref"]).read_text(encoding="utf-8"))
    control["system_response"] = "warn"
    control["decision"] = "require_review"
    Path(refs["policy_ref"]).write_text(json.dumps(control), encoding="utf-8")

    result = run_done_certification(
            {
                **refs,
                "certification_policy": {
                    "allow_warn_as_pass": True,
                    "allow_warn_promotion": True,
                    "require_system_readiness": True,
                },
            }
        )
    assert result["final_status"] == "WARNED"
    assert result["system_response"] == "warn"


def test_governed_default_blocks_warn_grade_without_explicit_override(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    review = json.loads(Path(refs["repo_review_snapshot_ref"]).read_text(encoding="utf-8"))
    review["findings_summary"]["redundancy_findings"] = 1
    Path(refs["repo_review_snapshot_ref"]).write_text(json.dumps(review), encoding="utf-8")
    control = json.loads(Path(refs["policy_ref"]).read_text(encoding="utf-8"))
    control["system_response"] = "warn"
    control["decision"] = "require_review"
    Path(refs["policy_ref"]).write_text(json.dumps(control), encoding="utf-8")

    result = run_done_certification(refs)

    assert result["final_status"] == "FAILED"
    assert result["system_response"] == "block"
    assert "control decision warn requires certification_policy.allow_warn_as_pass=true" in result["blocking_reasons"]
    assert result["certification_policy"]["allow_warn_as_pass"] is False
    assert result["certification_policy"]["require_system_readiness"] is True


def test_governed_default_requires_readiness_refs(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    refs.pop("repo_review_snapshot_ref")

    result = run_done_certification(refs)

    assert result["final_status"] == "FAILED"
    assert "repo_review_snapshot_ref is required for system readiness certification" in result["blocking_reasons"]
    assert result["certification_policy"]["require_system_readiness"] is True


def test_legacy_mode_keeps_compatibility_defaults_for_warn_and_readiness(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    refs.pop("repo_review_snapshot_ref")
    refs.pop("repo_health_eval_summary_ref")
    control = json.loads(Path(refs["policy_ref"]).read_text(encoding="utf-8"))
    control["system_response"] = "warn"
    control["decision"] = "require_review"
    Path(refs["policy_ref"]).write_text(json.dumps(control), encoding="utf-8")

    result = run_done_certification({**refs, "authority_path_mode": "legacy_compatibility"})

    assert result["final_status"] == "WARNED"
    assert result["system_response"] == "warn"
    assert result["certification_policy"]["allow_warn_as_pass"] is True
    assert result["certification_policy"]["require_system_readiness"] is False


def test_certification_freeze_when_drift_high(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    review = json.loads(Path(refs["repo_review_snapshot_ref"]).read_text(encoding="utf-8"))
    review["findings_summary"]["drift_findings"] = 2
    Path(refs["repo_review_snapshot_ref"]).write_text(json.dumps(review), encoding="utf-8")

    result = run_done_certification(refs)
    assert result["final_status"] == "FROZEN"
    assert result["system_response"] == "freeze"


def test_certification_fails_when_repo_review_missing(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    refs.pop("repo_review_snapshot_ref")
    result = run_done_certification({**refs, "certification_policy": {"require_system_readiness": True}})
    assert result["final_status"] == "FAILED"
    assert "repo_review_snapshot_ref is required for system readiness certification" in result["blocking_reasons"]


def test_certification_fails_when_eval_missing(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    refs.pop("repo_health_eval_summary_ref")
    result = run_done_certification({**refs, "certification_policy": {"require_system_readiness": True}})
    assert result["final_status"] == "FAILED"
    assert "repo_health_eval_summary_ref is required for system readiness certification" in result["blocking_reasons"]


def test_trust_spine_threshold_context_mismatch_blocks(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    control = json.loads(Path(refs["policy_ref"]).read_text(encoding="utf-8"))
    control["threshold_context"] = "comparative_analysis"
    Path(refs["policy_ref"]).write_text(json.dumps(control), encoding="utf-8")

    result = run_done_certification(refs)
    assert result["final_status"] == "FAILED"
    assert result["check_results"]["trust_spine_invariants"]["passed"] is False
    assert "TRUST_SPINE_THRESHOLD_CONTEXT_MISMATCH" in result["trust_spine_invariant_result"]["blocking_reasons"]


def test_trust_spine_coverage_contradiction_blocks(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    coverage = json.loads(Path(refs["eval_coverage_summary_ref"]).read_text(encoding="utf-8"))
    coverage["uncovered_required_slices"] = ["runtime_guardrails"]
    Path(refs["eval_coverage_summary_ref"]).write_text(json.dumps(coverage), encoding="utf-8")

    result = run_done_certification(refs)
    assert result["final_status"] == "FAILED"
    assert "TRUST_SPINE_COVERAGE_PROMOTION_CONTRADICTION" in result["trust_spine_invariant_result"]["blocking_reasons"]


def test_done_certification_active_path_fails_closed_when_enforcement_ref_missing(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    refs.pop("enforcement_result_ref")

    result = run_done_certification({**refs, "authority_path_mode": "active_runtime"})
    assert result["final_status"] == "FAILED"
    assert result["check_results"]["trust_spine_evidence_completeness"]["passed"] is False
    assert "TRUST_SPINE_ENFORCEMENT_REF_MISSING" in result["trust_spine_evidence_completeness_result"]["blocking_reasons"]
    assert "TRUST_SPINE_ACTIVE_PATH_INCOMPLETE" in result["trust_spine_evidence_completeness_result"]["blocking_reasons"]
    assert "TRUST_SPINE_CERTIFICATION_EVIDENCE_INCOMPLETE" in result["trust_spine_evidence_completeness_result"]["blocking_reasons"]


def test_done_certification_active_path_fails_closed_when_coverage_ref_missing(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    refs.pop("eval_coverage_summary_ref")

    result = run_done_certification({**refs, "authority_path_mode": "active_runtime"})
    assert result["final_status"] == "FAILED"
    assert result["check_results"]["trust_spine_evidence_completeness"]["passed"] is False
    assert "TRUST_SPINE_COVERAGE_REF_MISSING" in result["trust_spine_evidence_completeness_result"]["blocking_reasons"]


def test_done_certification_legacy_mode_is_non_certifiable_when_incomplete(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    refs.pop("enforcement_result_ref")

    result = run_done_certification({**refs, "authority_path_mode": "legacy_compatibility"})
    assert result["final_status"] == "PASSED"
    assert result["trust_spine_evidence_completeness_result"]["authority_path_mode"] == "legacy_compatibility"
    assert result["trust_spine_evidence_completeness_result"]["certifiable"] is False


def test_done_certification_blocks_when_cohesion_result_blocks(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    cohesion = json.loads(Path(refs["trust_spine_evidence_cohesion_result_ref"]).read_text(encoding="utf-8"))
    cohesion["overall_decision"] = "BLOCK"
    cohesion["contradiction_categories"] = ["promotion_certification_contradiction"]
    cohesion["blocking_reasons"] = ["PROMOTION_CERTIFICATION_CONTRADICTION:promotion_allowed_with_failed_done_certification"]
    Path(refs["trust_spine_evidence_cohesion_result_ref"]).write_text(json.dumps(cohesion), encoding="utf-8")

    result = run_done_certification(refs)
    assert result["final_status"] == "FAILED"
    assert result["trust_spine_evidence_cohesion_result"]["overall_decision"] == "BLOCK"
    assert result["check_results"]["trust_spine_evidence_cohesion"]["passed"] is False


def test_replay_failure_blocks(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    replay = json.loads(Path(refs["replay_result_ref"]).read_text(encoding="utf-8"))
    replay["consistency_status"] = "mismatch"
    replay["drift_detected"] = True
    Path(refs["replay_result_ref"]).write_text(json.dumps(replay), encoding="utf-8")

    result = run_done_certification(refs)
    assert result["final_status"] == "FAILED"
    assert result["system_response"] == "block"


def test_regression_failure_blocks(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    regression = json.loads(Path(refs["regression_result_ref"]).read_text(encoding="utf-8"))
    regression["failed_traces"] = 1
    regression["passed_traces"] = 0
    regression["overall_status"] = "fail"
    regression["regression_status"] = "fail"
    regression["results"][0]["passed"] = False
    regression["results"][0]["mismatch_summary"] = [{"field": "x", "baseline_value": 1, "current_value": 2}]
    Path(refs["regression_result_ref"]).write_text(json.dumps(regression), encoding="utf-8")

    result = run_done_certification(refs)
    assert result["final_status"] == "FAILED"
    assert result["system_response"] == "block"


def test_missing_artifact_blocks(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    Path(refs["certification_pack_ref"]).unlink()
    with pytest.raises(DoneCertificationError, match="file not found"):
        run_done_certification(refs)


def test_error_budget_exhausted_blocks(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    error_budget = json.loads(Path(refs["error_budget_ref"]).read_text(encoding="utf-8"))
    error_budget["budget_status"] = "exhausted"
    Path(refs["error_budget_ref"]).write_text(json.dumps(error_budget), encoding="utf-8")

    result = run_done_certification(refs)
    assert result["final_status"] == "FAILED"
    assert result["system_response"] == "block"


def test_fail_closed_violation_blocks(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    failure = json.loads(Path(refs["failure_injection_ref"]).read_text(encoding="utf-8"))
    failure["results"][0]["observed_outcome"] = "allow"
    failure["results"][0]["expected_outcome"] = "block"
    Path(refs["failure_injection_ref"]).write_text(json.dumps(failure), encoding="utf-8")

    result = run_done_certification(refs)
    assert result["final_status"] == "FAILED"
    assert result["system_response"] == "block"


def test_invalid_schema_blocks(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    replay = json.loads(Path(refs["replay_result_ref"]).read_text(encoding="utf-8"))
    replay["unknown_field"] = "unexpected"
    Path(refs["replay_result_ref"]).write_text(json.dumps(replay), encoding="utf-8")

    with pytest.raises(DoneCertificationError, match="failed schema validation"):
        run_done_certification(refs)


def test_trace_mismatch_blocks(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    control_decision = json.loads(Path(refs["policy_ref"]).read_text(encoding="utf-8"))
    control_decision["trace_id"] = "trace-mismatch-999"
    Path(refs["policy_ref"]).write_text(json.dumps(control_decision), encoding="utf-8")

    with pytest.raises(DoneCertificationError, match="PROVENANCE_TRACE_MISMATCH"):
        run_done_certification(refs)


def test_run_mismatch_fails_closed(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    control_decision = json.loads(Path(refs["policy_ref"]).read_text(encoding="utf-8"))
    control_decision["run_id"] = "run-mismatch-999"
    Path(refs["policy_ref"]).write_text(json.dumps(control_decision), encoding="utf-8")

    with pytest.raises(DoneCertificationError, match="PROVENANCE_RUN_MISMATCH"):
        run_done_certification(refs)


def test_explicit_cross_run_policy_allows_cross_run_reference(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    control_decision = json.loads(Path(refs["policy_ref"]).read_text(encoding="utf-8"))
    control_decision["run_id"] = "run-cross-run-allowed"
    Path(refs["policy_ref"]).write_text(json.dumps(control_decision), encoding="utf-8")

    result = run_done_certification(
        {
            **refs,
            "identity_policy": {"allow_cross_run_reference": True},
        }
    )
    assert result["final_status"] == "PASSED"


def test_missing_trace_on_required_artifact_fails_closed(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    regression = json.loads(Path(refs["regression_result_ref"]).read_text(encoding="utf-8"))
    regression["results"][0].pop("trace_id", None)
    Path(refs["regression_result_ref"]).write_text(json.dumps(regression), encoding="utf-8")

    with pytest.raises(DoneCertificationError, match="failed schema validation"):
        run_done_certification(refs)


def test_ambiguous_certification_pack_trace_refs_blocks(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    certification_pack = json.loads(Path(refs["certification_pack_ref"]).read_text(encoding="utf-8"))
    replay = json.loads(Path(refs["replay_result_ref"]).read_text(encoding="utf-8"))
    certification_pack["provenance_trace_refs"]["trace_refs"] = [
        replay["trace_id"],
        f"{replay['trace_id']}-other",
    ]
    Path(refs["certification_pack_ref"]).write_text(json.dumps(certification_pack), encoding="utf-8")

    result = run_done_certification(refs)
    assert result["final_status"] == "FAILED"
    assert result["system_response"] == "block"
    assert any(reason.startswith("TRACE_LINKAGE_AMBIGUOUS:") for reason in result["blocking_reasons"])
    assert result["check_results"]["trace_linkage"]["passed"] is False


def test_done_certification_tpa_required_pass(tmp_path: Path) -> None:
    refs = _attach_valid_tpa_refs(_write_inputs(tmp_path), tmp_path)
    result = run_done_certification(refs)
    assert result["tpa_required"] is True
    assert result["tpa_status"] == "PASS"
    assert len(result["tpa_artifact_refs"]) >= 5
    assert result["check_results"]["tpa_compliance"]["passed"] is True


def test_done_certification_tpa_required_missing_artifact_fails_closed(tmp_path: Path) -> None:
    refs = _attach_valid_tpa_refs(_write_inputs(tmp_path), tmp_path)
    refs.pop("tpa_certification_envelope_ref")
    result = run_done_certification(refs)
    assert result["final_status"] == "FAILED"
    assert result["tpa_required"] is True
    assert result["tpa_status"] == "FAIL"
    assert result["check_results"]["tpa_compliance"]["passed"] is False


def test_done_certification_fails_closed_when_tpa_scope_policy_missing(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    refs["tpa_scope_policy_path"] = str(tmp_path / "missing_policy.json")
    with pytest.raises(DoneCertificationError, match="TPA scope policy evaluation failed"):
        run_done_certification(refs)
