from __future__ import annotations

import json
from pathlib import Path
import subprocess

from spectrum_systems.modules.runtime.shift_left_hardening_superlayer import (
    apply_fix_pack,
    classify_fix,
    decide_escalation,
    decide_pre_execution_certification,
    detect_hidden_state,
    detect_retry_storm,
    emit_final_proof_artifacts,
    enforce_exploit_coverage_gate,
    evaluate_context_sufficiency,
    evaluate_forbidden_vocabulary_guard,
    evaluate_lineage_precondition,
    evaluate_manifest_strict_validation,
    evaluate_minimal_trace_contract,
    evaluate_owner_boundary_lint,
    evaluate_proof_only_detector,
    evaluate_replay_precondition,
    evaluate_required_eval_presence,
    evaluate_structure_controls,
    evaluate_system_registry_overlap,
    extract_failure_signatures,
    generate_shift_left_remediation_hint,
    generate_auto_eval,
    generate_auto_regression_pack,
    detect_fail_open_conditions,
    normalize_reason_codes,
    plan_targeted_rerun,
    register_exploit_family,
    run_red_team_round,
    run_shift_left_guard_chain,
    track_exploit_persistence,
    track_repair_capacity,
    validate_dependency_graph,
    verify_eval_completeness,
    verify_lineage_integrity,
    verify_observability_completeness,
    verify_replay_integrity,
)


def test_sl_core_guard_chain_fail_fast() -> None:
    created_at = "2026-04-17T00:00:00Z"
    manifest = evaluate_manifest_strict_validation(
        manifest_contracts=[{"artifact_type": "BadType", "artifact_class": "coordination"}],
        forbidden_classes={"forbidden"},
        created_at=created_at,
    )
    chain = run_shift_left_guard_chain(
        checks={manifest["artifact_type"]: manifest},
        fail_fast=True,
        created_at=created_at,
    )
    assert chain["status"] == "fail"
    assert chain["blocked_by"] == "con_standards_manifest_strict_validation_result"
    assert len(chain["checks_executed"]) == 1


def test_manifest_strict_validation_blocks_empty_evidence() -> None:
    created_at = "2026-04-17T00:00:00Z"
    result = evaluate_manifest_strict_validation(
        manifest_contracts=[],
        forbidden_classes={"forbidden"},
        created_at=created_at,
    )
    assert result["status"] == "fail"
    assert "empty_evidence_set" in result["reason_codes"]
    assert "missing_manifest_contracts" in result["reason_codes"]


def test_sl_core_and_structure_pass_path() -> None:
    created_at = "2026-04-17T00:00:00Z"
    results = [
        evaluate_manifest_strict_validation(
            manifest_contracts=[{"artifact_type": "valid_contract", "artifact_class": "coordination", "example_path": "x", "schema_version": "1.0.0"}],
            forbidden_classes={"forbidden"},
            created_at=created_at,
        ),
        evaluate_system_registry_overlap(overlaps=[], shadow_owners=[], authority_violations=[], created_at=created_at),
        evaluate_owner_boundary_lint(owner_import_count=1, mixed_owner_functions=[], multi_artifact_functions=[], created_at=created_at),
        evaluate_forbidden_vocabulary_guard(forbidden_terms=[], created_at=created_at),
        evaluate_required_eval_presence(missing_eval_families=[], created_at=created_at),
        evaluate_context_sufficiency(missing_recipes=[], ambiguous_paths=[], created_at=created_at),
        evaluate_minimal_trace_contract(missing_fields=[], created_at=created_at),
        evaluate_replay_precondition(missing_preconditions=[], created_at=created_at),
        evaluate_lineage_precondition(missing_preconditions=[], created_at=created_at),
        evaluate_proof_only_detector(proof_only_paths=[], created_at=created_at),
    ]
    chain = run_shift_left_guard_chain(
        checks={item["artifact_type"]: item for item in results},
        fail_fast=True,
        created_at=created_at,
    )
    assert chain["status"] == "pass"

    structure = evaluate_structure_controls(
        orchestration_hotspots=["mod_a"],
        multi_owner_functions=[],
        artifact_explosion_units=[],
        proof_substitution_paths=[],
        created_at=created_at,
    )
    assert structure["concentration"]["status"] == "fail"
    assert structure["metrics"]["total_pressure"] == 1


def test_mini_cert_requires_all_critical_dimensions() -> None:
    created_at = "2026-04-17T00:00:00Z"
    mini = decide_pre_execution_certification(
        checks={
            "sl_core": {"status": "pass"},
            "sl_structure": {"status": "pass"},
            "sl_memory": {"status": "pass"},
            "sl_router": {"status": "pass"},
            "sl_cert": {"status": "pass"},
            "dependency_graph": {"status": "pass"},
            "runtime_parity": {"status": "pass", "parity_strength": "strong"},
        },
        created_at=created_at,
    )
    assert mini["status"] == "fail"
    assert "missing_check:eval" in mini["reason_codes"]
    assert "missing_check:hidden_state" in mini["reason_codes"]
    assert "missing_check:lineage" in mini["reason_codes"]
    assert "missing_check:observability" in mini["reason_codes"]
    assert "missing_check:replay" in mini["reason_codes"]


def test_mini_cert_emits_missing_evidence_and_parity_weakness_reason_codes() -> None:
    created_at = "2026-04-17T00:00:00Z"
    mini = decide_pre_execution_certification(
        checks={
            "sl_core": {"status": "pass"},
            "sl_structure": {"status": "pass"},
            "sl_memory": {"status": "pass"},
            "sl_router": {"status": "pass"},
            "sl_cert": {"status": "pass"},
            "dependency_graph": {"status": "pass"},
            "runtime_parity": {"status": "pass", "parity_strength": "weak"},
            "eval": {"status": "pass", "reason_codes": ["missing_evidence:eval_registry"]},
            "replay": {"status": "pass"},
            "lineage": {"status": "pass"},
            "observability": {"status": "pass"},
            "hidden_state": {"status": "pass"},
        },
        created_at=created_at,
    )
    assert mini["status"] == "fail"
    assert "missing_evidence:eval" in mini["reason_codes"]
    assert "parity_weakness:runtime_parity" in mini["reason_codes"]


def test_sl_memory_and_coverage_gate() -> None:
    created_at = "2026-04-17T00:00:00Z"
    family = register_exploit_family(family_id="manifest-drift", failure_modes=["invalid_artifact_class"], created_at=created_at)
    signatures = extract_failure_signatures(
        failures=[
            {"component": "con", "reason": "manifest"},
            {"component": "con", "reason": "manifest"},
            {"component": "rep", "reason": "replay"},
        ],
        created_at=created_at,
    )
    evals = generate_auto_eval(signatures=signatures["signatures"], created_at=created_at)
    regressions = generate_auto_regression_pack(signatures=signatures["signatures"], created_at=created_at)
    persistence = track_exploit_persistence(family_id="manifest-drift", recurrence_count=0, created_at=created_at)
    coverage = enforce_exploit_coverage_gate(
        has_exploit_artifact=True,
        has_regression_or_eval=bool(evals["eval_count"] or regressions["test_count"]),
        has_family_registration=family["status"] == "pass",
        created_at=created_at,
    )
    assert signatures["signature_count"] == 2
    assert persistence["status"] == "pass"
    assert coverage["status"] == "pass"


def test_sl_router_and_escalation() -> None:
    created_at = "2026-04-17T00:00:00Z"
    classified = classify_fix(failure_signature="control.loop.overload", created_at=created_at)
    rerun = plan_targeted_rerun(fix_class=classified["fix_class"], created_at=created_at)
    retry = detect_retry_storm(retry_cycles=5, threshold=3, created_at=created_at)
    cap = track_repair_capacity(active_loops=2, capacity_limit=4, created_at=created_at)
    esc = decide_escalation(
        fix_class=classified["fix_class"],
        retry_storm=retry["status"] == "fail",
        capacity_saturated=cap["status"] == "fail",
        created_at=created_at,
    )
    assert rerun["status"] == "pass"
    assert retry["status"] == "fail"
    assert esc["escalate"] is True
    assert classified["fix_class"] == "control_fix"


def test_sl_cert_and_red_team_loops_and_final_proof() -> None:
    created_at = "2026-04-17T00:00:00Z"
    eval_comp = verify_eval_completeness(missing_evals=[], created_at=created_at)
    replay_comp = verify_replay_integrity(replay_gaps=[], created_at=created_at)
    lineage_comp = verify_lineage_integrity(lineage_gaps=[], created_at=created_at)
    obs_comp = verify_observability_completeness(observability_gaps=[], created_at=created_at)
    dep = validate_dependency_graph(graph_errors=[], created_at=created_at)
    hidden = detect_hidden_state(hidden_state_findings=["unexpected_cache"], created_at=created_at)

    mini = decide_pre_execution_certification(
        checks={
            "sl_core": {"status": "pass"},
            "sl_structure": {"status": "pass"},
            "sl_memory": {"status": "pass"},
            "sl_router": {"status": "pass"},
            "sl_cert": {"status": "pass"},
            "dependency_graph": dep,
            "runtime_parity": {"status": "pass"},
            "hidden_state": hidden,
            "eval": eval_comp,
            "replay": replay_comp,
            "lineage": lineage_comp,
            "observability": obs_comp,
        },
        created_at=created_at,
    )
    assert mini["status"] == "fail"

    rt = run_red_team_round(
        artifact_type="ril_shift_left_guard_bypass_red_team_report",
        round_id="RT-SL-A",
        scenarios=[{"scenario_id": "guard-bypass", "expected": "block", "observed": "accepted"}],
        created_at=created_at,
    )
    fix = apply_fix_pack(
        artifact_type="fre_tpa_sel_pqx_shift_left_guard_fix_pack",
        fix_pack_id="FX-SL-A",
        bypasses=rt["bypasses"],
        created_at=created_at,
    )
    proofs = emit_final_proof_artifacts(created_at=created_at)

    assert rt["status"] == "fail"
    assert fix["rerun_validated"] is True
    assert set(proofs) == {"FINAL-SL-01", "FINAL-SL-02", "FINAL-SL-03", "FINAL-SL-04", "FINAL-SL-05", "FINAL-SL-06"}


def test_runner_uses_repo_derived_signals(tmp_path: Path) -> None:
    output_path = tmp_path / "slh.json"
    cmd = [
        "python",
        "scripts/run_shift_left_hardening_superlayer.py",
        "--output",
        str(output_path),
        "--changed-files",
        "scripts/run_shift_left_hardening_superlayer.py",
        "tests/test_shift_left_hardening_superlayer.py",
    ]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    assert proc.returncode in {0, 1}
    assert output_path.exists()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    signals = payload["repo_derived_signals"]
    assert signals["manifest_path"] == "contracts/standards-manifest.json"
    assert "scripts/build_dependency_graph.py" in signals["dependency_graph_command"]
    assert "scripts/run_shift_left_hardening_superlayer.py" in signals["changed_files"]
    assert payload["shift_left_guard_chain"]["checks_executed"][0]["check"] == "con_standards_manifest_strict_validation_result"


def test_runner_blocks_proof_only_changed_scope(tmp_path: Path) -> None:
    output_path = tmp_path / "slh-proof-only.json"
    cmd = [
        "python",
        "scripts/run_shift_left_hardening_superlayer.py",
        "--output",
        str(output_path),
        "--changed-files",
        "docs/reviews/SLH-001-HARDENING-001_delivery_report.md",
    ]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    assert proc.returncode == 1
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["mini_certification_decision"]["status"] == "fail"


def test_remediation_hint_is_deterministic_for_same_failure() -> None:
    created_at = "2026-04-17T00:00:00Z"
    first = generate_shift_left_remediation_hint(
        failure_class="lineage",
        reason_codes=["failed_check:lineage", "missing_evidence:lineage"],
        impacted_files=["contracts/standards-manifest.json", "scripts/pqx_runner.py"],
        created_at=created_at,
    )
    second = generate_shift_left_remediation_hint(
        failure_class="lineage",
        reason_codes=["failed_check:lineage", "missing_evidence:lineage"],
        impacted_files=["scripts/pqx_runner.py", "contracts/standards-manifest.json"],
        created_at=created_at,
    )
    assert first["fix_instructions"] == second["fix_instructions"]
    assert first["impacted_files"] == second["impacted_files"]


def test_fail_open_detector_flags_unknown_and_skipped_evidence() -> None:
    findings = detect_fail_open_conditions(
        checks={
            "taxonomy": {"status": "pass", "evidence_present": None, "reason_codes": []},
            "registry": {"status": "skip", "evidence_present": True, "reason_codes": []},
            "lineage": {"status": "pass", "evidence_present": True, "reason_codes": ["missing_signal"]},
        }
    )
    assert "missing_evidence_treated_as_pass:taxonomy" in findings
    assert "skipped_check:registry" in findings
    assert "missing_signal_treated_as_pass:lineage" in findings


def test_reason_code_normalization_uses_machine_readable_prefixes() -> None:
    codes = normalize_reason_codes(
        check_name="lineage_gate",
        failure_type="lineage",
        evidence_state="unknown",
        reasons=["lineage_precondition_missing"],
    )
    assert "missing_evidence:lineage_gate" in codes
    assert "failed_check:lineage" in codes
