from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.orchestration.next_step_decision import build_next_step_decision


_REPO_ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _manifest(state: str = "draft_roadmap") -> dict:
    return {
        "cycle_id": "cycle-test",
        "current_state": state,
        "roadmap_artifact_path": str(_REPO_ROOT / "docs" / "roadmap" / "system_roadmap.md"),
        "strategy_authority": {"path": "docs/architecture/system_strategy.md", "version": "2026-03-30"},
        "source_authorities": [
            {
                "source_id": "SRE-MAPPING",
                "path": "docs/source_structured/mapping_google_sre_reliability_principles_to_spectrum_systems.json",
                "title": "Mapping Google SRE Reliability Principles to Spectrum Systems",
            }
        ],
        "roadmap_review_artifact_paths": [str(_REPO_ROOT / "contracts" / "examples" / "roadmap_review_artifact.json")],
        "execution_report_paths": [str(_REPO_ROOT / "contracts" / "examples" / "execution_report_artifact.json")],
        "implementation_review_paths": [str(_REPO_ROOT / "contracts" / "examples" / "implementation_review_artifact.json")],
        "fix_roadmap_path": str(_REPO_ROOT / "contracts" / "examples" / "fix_roadmap_artifact.json"),
        "fix_roadmap_markdown_path": None,
        "fix_group_refs": [],
        "fix_execution_report_paths": [str(_REPO_ROOT / "contracts" / "examples" / "execution_report_artifact.json")],
        "certification_record_path": None,
        "blocking_issues": [],
        "next_action": "await_roadmap_approval",
        "updated_at": "2026-03-30T00:00:00Z",
        "done_certification_input_refs": {
            "replay_result_ref": "a",
            "regression_result_ref": "b",
            "certification_pack_ref": "c",
            "error_budget_ref": "d",
            "policy_ref": "e",
        },
        "required_judgments": [],
        "judgment_scope": "autonomous_cycle",
        "judgment_environment": "prod",
        "judgment_policy_paths": [str(_REPO_ROOT / "contracts" / "examples" / "judgment_policy.json")],
        "judgment_policy_lifecycle_paths": [str(_REPO_ROOT / "contracts" / "examples" / "judgment_policy_lifecycle_record.json")],
        "judgment_policy_rollout_paths": [str(_REPO_ROOT / "contracts" / "examples" / "judgment_policy_rollout_record.json")],
        "judgment_input_context": {},
        "judgment_evidence_refs": [],
        "judgment_precedent_record_paths": [],
        "judgment_record_path": None,
        "judgment_application_record_path": None,
        "judgment_eval_result_path": None,
        "fre_fix_plan_artifact_ref": str(_REPO_ROOT / "contracts" / "examples" / "fix_plan_artifact.json"),
    }


def _eligibility(eligible_step_ids: list[str] | None = None) -> dict:
    if eligible_step_ids is None:
        eligible_step_ids = ["CTRL-02"]
    status_artifacts = [
        {
            "artifact_type": "pqx_strategy_status_artifact",
            "schema_version": "1.0.0",
            "roadmap_row_id": step_id,
            "strategy_gate_decision": "allow",
            "violated_invariants": [],
            "drift_signals": [],
            "hardening_vs_expansion": "hardening",
            "replay_trace_declared": True,
            "eval_control_declared": False,
            "rationale": "strategy gate allows execution; required strategy and trust declarations are complete",
        }
        for step_id in sorted(set(eligible_step_ids))
    ]
    return {
        "artifact_type": "roadmap_eligibility_artifact",
        "schema_version": "1.2.0",
        "artifact_version": "1.2.0",
        "roadmap_ref": "docs/roadmaps/system_roadmap.md",
        "evaluated_at": "2026-03-30T00:00:00Z",
        "identity_basis": {
            "roadmap_artifact_id": "roadmap-cycle-test",
            "roadmap_digest": "a542be4e4e3d2a77e6a508d46267f37754378291a075e59977fe80c0baab1128",
        },
        "program_alignment_status": "not_evaluated",
        "program_violation": False,
        "program_enforcement_action": "no_program_artifact",
        "eligible_step_ids": eligible_step_ids,
        "recommended_next_step_ids": eligible_step_ids,
        "blocked_steps": [],
        "strategy_status_artifacts": status_artifacts,
        "summary": {
            "total_steps": 1,
            "completed_steps": 0,
            "eligible_steps": len(eligible_step_ids),
            "blocked_steps": 0,
            "strategy_gate": {
                "allow": len(status_artifacts),
                "warn": 0,
                "freeze": 0,
                "block": 0,
            },
        },
        "artifact_id": "c1bfd40c7ea68193b177e33a01da488ff42d8d59cd6ab745ee019ec83afe83a1",
    }


def test_happy_path_progression(tmp_path: Path) -> None:
    path = _write(tmp_path / "cycle_manifest.json", _manifest("draft_roadmap"))
    eligibility_path = _write(tmp_path / "eligibility.json", _eligibility())
    decision = build_next_step_decision(str(path), str(eligibility_path))
    assert decision["recommendation_action"] == "submit_for_review"
    assert decision["blocking"] is False
    assert decision["remediation_required"] is False
    assert decision["policy_id"] == "NEXT_STEP_DECISION_POLICY"
    assert decision["policy_version"] == "1.0.0"
    assert decision["selection_basis"] == "eligibility_constrained"
    assert decision["selected_step_id"] == "CTRL-02"


def test_missing_strategy_fails_closed(tmp_path: Path) -> None:
    payload = _manifest("roadmap_under_review")
    payload.pop("strategy_authority")
    path = _write(tmp_path / "cycle_manifest.json", payload)
    eligibility_path = _write(tmp_path / "eligibility.json", _eligibility())
    decision = build_next_step_decision(str(path), str(eligibility_path))
    assert decision["recommendation_action"] == "block"
    assert "strategy_authority" in " ".join(decision["required_inputs_missing"])
    assert decision["blocking"] is True


def test_missing_sources_fail_closed(tmp_path: Path) -> None:
    payload = _manifest("roadmap_under_review")
    payload["source_authorities"] = []
    path = _write(tmp_path / "cycle_manifest.json", payload)
    eligibility_path = _write(tmp_path / "eligibility.json", _eligibility())
    decision = build_next_step_decision(str(path), str(eligibility_path))
    assert decision["recommendation_action"] == "block"
    assert "source_authorities" in " ".join(decision["required_inputs_missing"])


def test_drift_detected_forces_remediation(tmp_path: Path) -> None:
    payload = _manifest("execution_complete_unreviewed")
    drift_path = tmp_path / "drift.json"
    _write(drift_path, {"drift_detected": True, "drift_status": "exceeds_threshold"})
    payload["drift_detection_result_path"] = str(drift_path)
    path = _write(tmp_path / "cycle_manifest.json", payload)
    eligibility_path = _write(tmp_path / "eligibility.json", _eligibility())
    decision = build_next_step_decision(str(path), str(eligibility_path))
    assert decision["recommendation_action"] == "generate_fix_roadmap"
    assert decision["blocking"] is True
    assert decision["drift_detected"] is True
    assert decision["remediation_required"] is True
    assert decision["remediation_class"] == "roadmap_repair"
    assert decision["blocking_reason_category"] == "blocking_drift_finding"
    assert isinstance(decision["drift_remediation_artifact"], dict)
    assert decision["fre_fix_plan_artifact_ref"] == str(_REPO_ROOT / "contracts" / "examples" / "fix_plan_artifact.json")


def test_blocking_recommendation_requires_fre_fix_plan_artifact(tmp_path: Path) -> None:
    payload = _manifest("execution_complete_unreviewed")
    payload.pop("fre_fix_plan_artifact_ref")
    drift_path = tmp_path / "drift.json"
    _write(drift_path, {"drift_detected": True, "drift_status": "exceeds_threshold"})
    payload["drift_detection_result_path"] = str(drift_path)
    path = _write(tmp_path / "cycle_manifest.json", payload)
    eligibility_path = _write(tmp_path / "eligibility.json", _eligibility())
    with pytest.raises(ValueError, match="fre_fix_plan_artifact_ref"):
        build_next_step_decision(str(path), str(eligibility_path))


def test_invalid_state_fails_closed(tmp_path: Path) -> None:
    path = _write(tmp_path / "cycle_manifest.json", _manifest("invalid_state"))
    eligibility_path = _write(tmp_path / "eligibility.json", _eligibility())
    decision = build_next_step_decision(str(path), str(eligibility_path))
    assert decision["recommendation_action"] == "block"
    assert decision["blocking"] is True


def test_deterministic_output_id(tmp_path: Path) -> None:
    path = _write(tmp_path / "cycle_manifest.json", _manifest("roadmap_approved"))
    eligibility_path = _write(tmp_path / "eligibility.json", _eligibility())
    first = build_next_step_decision(str(path), str(eligibility_path))
    second = build_next_step_decision(str(path), str(eligibility_path))
    assert first["decision_id"] == second["decision_id"]


def test_selecting_non_eligible_step_fails(tmp_path: Path) -> None:
    payload = _manifest("roadmap_approved")
    payload["selected_step_id"] = "CTRL-99"
    path = _write(tmp_path / "cycle_manifest.json", payload)
    eligibility_path = _write(tmp_path / "eligibility.json", _eligibility(["CTRL-02"]))
    with pytest.raises(ValueError, match="selected step_id is not eligible"):
        build_next_step_decision(str(path), str(eligibility_path))


def test_missing_eligibility_artifact_fails(tmp_path: Path) -> None:
    path = _write(tmp_path / "cycle_manifest.json", _manifest("roadmap_approved"))
    with pytest.raises(ValueError, match="roadmap eligibility artifact missing"):
        build_next_step_decision(str(path), str(tmp_path / "missing-eligibility.json"))


def test_empty_eligible_steps_blocks(tmp_path: Path) -> None:
    path = _write(tmp_path / "cycle_manifest.json", _manifest("roadmap_approved"))
    eligibility_path = _write(tmp_path / "eligibility.json", _eligibility([]))
    decision = build_next_step_decision(str(path), str(eligibility_path))
    assert decision["blocking"] is True
    assert "no eligible steps available" in decision["blocking_reasons"]
    assert decision["selected_step_id"] is None


def test_eligibility_provenance_present_in_decision_artifact(tmp_path: Path) -> None:
    path = _write(tmp_path / "cycle_manifest.json", _manifest("roadmap_approved"))
    eligibility_path = _write(tmp_path / "eligibility.json", _eligibility(["CTRL-02", "CTRL-03"]))
    decision = build_next_step_decision(str(path), str(eligibility_path))
    assert decision["eligibility_artifact_path"] == str(eligibility_path)
    assert decision["eligible_step_ids_snapshot"] == ["CTRL-02", "CTRL-03"]
    assert decision["selected_step_id"] == "CTRL-02"
    assert decision["selection_basis"] == "eligibility_constrained"


def test_eligibility_snapshot_is_stably_sorted(tmp_path: Path) -> None:
    path = _write(tmp_path / "cycle_manifest.json", _manifest("roadmap_approved"))
    eligibility_path = _write(tmp_path / "eligibility.json", _eligibility(["CTRL-03", "CTRL-02"]))
    decision = build_next_step_decision(str(path), str(eligibility_path))
    assert decision["eligible_step_ids_snapshot"] == ["CTRL-02", "CTRL-03"]


def test_contract_example_cases_validate() -> None:
    schema = load_schema("next_step_decision_artifact")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    cases = json.loads((_REPO_ROOT / "contracts" / "examples" / "next_step_decision_artifact.json").read_text())
    for payload in cases.values():
        validator.validate(payload)
