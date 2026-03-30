from __future__ import annotations

import json
from pathlib import Path

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
    }


def test_happy_path_progression(tmp_path: Path) -> None:
    path = _write(tmp_path / "cycle_manifest.json", _manifest("draft_roadmap"))
    decision = build_next_step_decision(str(path))
    assert decision["next_action"] == "submit_for_review"
    assert decision["blocking"] is False
    assert decision["policy_id"] == "NEXT_STEP_DECISION_POLICY"
    assert decision["policy_version"] == "1.0.0"


def test_missing_strategy_fails_closed(tmp_path: Path) -> None:
    payload = _manifest("roadmap_under_review")
    payload.pop("strategy_authority")
    path = _write(tmp_path / "cycle_manifest.json", payload)
    decision = build_next_step_decision(str(path))
    assert decision["next_action"] == "block"
    assert "strategy_authority" in " ".join(decision["required_inputs_missing"])
    assert decision["blocking"] is True


def test_missing_sources_fail_closed(tmp_path: Path) -> None:
    payload = _manifest("roadmap_under_review")
    payload["source_authorities"] = []
    path = _write(tmp_path / "cycle_manifest.json", payload)
    decision = build_next_step_decision(str(path))
    assert decision["next_action"] == "block"
    assert "source_authorities" in " ".join(decision["required_inputs_missing"])


def test_drift_detected_forces_remediation(tmp_path: Path) -> None:
    payload = _manifest("execution_complete_unreviewed")
    drift_path = tmp_path / "drift.json"
    _write(drift_path, {"drift_detected": True, "drift_status": "exceeds_threshold"})
    payload["drift_detection_result_path"] = str(drift_path)
    path = _write(tmp_path / "cycle_manifest.json", payload)
    decision = build_next_step_decision(str(path))
    assert decision["next_action"] == "generate_fix_roadmap"
    assert decision["blocking"] is True
    assert decision["drift_detected"] is True


def test_invalid_state_fails_closed(tmp_path: Path) -> None:
    path = _write(tmp_path / "cycle_manifest.json", _manifest("invalid_state"))
    decision = build_next_step_decision(str(path))
    assert decision["next_action"] == "block"
    assert decision["blocking"] is True


def test_deterministic_output_id(tmp_path: Path) -> None:
    path = _write(tmp_path / "cycle_manifest.json", _manifest("roadmap_approved"))
    first = build_next_step_decision(str(path))
    second = build_next_step_decision(str(path))
    assert first["decision_id"] == second["decision_id"]


def test_contract_example_cases_validate() -> None:
    schema = load_schema("next_step_decision_artifact")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    cases = json.loads((_REPO_ROOT / "contracts" / "examples" / "next_step_decision_artifact.json").read_text())
    for payload in cases.values():
        validator.validate(payload)
