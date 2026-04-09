from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.orchestration import next_step_decision as nsd
from spectrum_systems.orchestration.next_step_decision import NextStepDecisionError, build_next_step_decision

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _manifest(state: str = "draft_roadmap") -> dict:
    return {
        "cycle_id": "cycle-policy-test",
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
        "fix_execution_report_paths": [str(_REPO_ROOT / "contracts" / "examples" / "execution_report_artifact.json")],
        "updated_at": "2026-03-30T00:00:00Z",
        "done_certification_input_refs": {
            "replay_result_ref": "a",
            "regression_result_ref": "b",
            "certification_pack_ref": "c",
            "error_budget_ref": "d",
            "policy_ref": "e",
        },
    }


def _eligibility() -> dict:
    strategy_status = {
        "artifact_type": "pqx_strategy_status_artifact",
        "schema_version": "1.0.0",
        "roadmap_row_id": "CTRL-02",
        "strategy_gate_decision": "allow",
        "violated_invariants": [],
        "drift_signals": [],
        "hardening_vs_expansion": "hardening",
        "replay_trace_declared": True,
        "eval_control_declared": False,
        "rationale": "strategy gate allows execution; required strategy and trust declarations are complete",
    }
    return {
        "artifact_type": "roadmap_eligibility_artifact",
        "schema_version": "1.2.0",
        "artifact_version": "1.2.0",
        "roadmap_ref": "docs/roadmaps/system_roadmap.md",
        "evaluated_at": "2026-03-30T00:00:00Z",
        "identity_basis": {
            "roadmap_artifact_id": "roadmap-cycle-policy-test",
            "roadmap_digest": "a542be4e4e3d2a77e6a508d46267f37754378291a075e59977fe80c0baab1128",
        },
        "program_alignment_status": "not_evaluated",
        "program_violation": False,
        "program_enforcement_action": "no_program_artifact",
        "eligible_step_ids": ["CTRL-02"],
        "recommended_next_step_ids": ["CTRL-02"],
        "blocked_steps": [],
        "strategy_status_artifacts": [strategy_status],
        "summary": {
            "total_steps": 1,
            "completed_steps": 0,
            "eligible_steps": 1,
            "blocked_steps": 0,
            "strategy_gate": {
                "allow": 1,
                "warn": 0,
                "freeze": 0,
                "block": 0,
            },
        },
        "artifact_id": "c1bfd40c7ea68193b177e33a01da488ff42d8d59cd6ab745ee019ec83afe83a1",
    }


def _load_default_policy() -> dict:
    return json.loads((Path(nsd._POLICY_PATH)).read_text(encoding="utf-8"))


def test_valid_policy_loads_and_sets_provenance(tmp_path: Path) -> None:
    manifest_path = _write(tmp_path / "cycle_manifest.json", _manifest())
    eligibility_path = _write(tmp_path / "eligibility.json", _eligibility())
    decision = build_next_step_decision(str(manifest_path), str(eligibility_path))
    assert decision["policy_id"] == "NEXT_STEP_DECISION_POLICY"
    assert decision["policy_version"] == "1.0.0"
    assert len(decision["policy_hash"]) == 64


def test_invalid_policy_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    invalid_policy_path = _write(tmp_path / "policy.json", {"policy_id": "NEXT_STEP_DECISION_POLICY"})
    monkeypatch.setattr(nsd, "_POLICY_PATH", invalid_policy_path)
    manifest_path = _write(tmp_path / "cycle_manifest.json", _manifest())
    eligibility_path = _write(tmp_path / "eligibility.json", _eligibility())
    with pytest.raises(NextStepDecisionError, match="failed schema validation"):
        build_next_step_decision(str(manifest_path), str(eligibility_path))


def test_missing_policy_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(nsd, "_POLICY_PATH", tmp_path / "missing-policy.json")
    manifest_path = _write(tmp_path / "cycle_manifest.json", _manifest())
    eligibility_path = _write(tmp_path / "eligibility.json", _eligibility())
    with pytest.raises(NextStepDecisionError, match="policy missing"):
        build_next_step_decision(str(manifest_path), str(eligibility_path))


def test_decision_behavior_matches_policy_mapping(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    policy = _load_default_policy()
    policy["decision_mapping_rules"]["execution_ready"]["next_action"] = "prepare_execution_request"
    policy["decision_mapping_rules"]["execution_ready"]["allowed_actions"] = ["prepare_execution_request", "block"]
    policy_path = _write(tmp_path / "policy.json", policy)
    monkeypatch.setattr(nsd, "_POLICY_PATH", policy_path)

    manifest_path = _write(tmp_path / "cycle_manifest.json", _manifest("execution_ready"))
    eligibility_path = _write(tmp_path / "eligibility.json", _eligibility())
    decision = build_next_step_decision(str(manifest_path), str(eligibility_path))
    assert decision["recommendation_action"] == "prepare_execution_request"
    assert decision["recommendation_candidates"] == ["prepare_execution_request", "block"]
    assert decision["next_action"] == decision["recommendation_action"]
    assert decision["allowed_actions"] == decision["recommendation_candidates"]


def test_policy_change_changes_decision_deterministically(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest_path = _write(tmp_path / "cycle_manifest.json", _manifest("roadmap_approved"))
    eligibility_path = _write(tmp_path / "eligibility.json", _eligibility())

    policy_a = _load_default_policy()
    policy_a_path = _write(tmp_path / "policy-a.json", policy_a)
    monkeypatch.setattr(nsd, "_POLICY_PATH", policy_a_path)
    decision_a_1 = build_next_step_decision(str(manifest_path), str(eligibility_path))
    decision_a_2 = build_next_step_decision(str(manifest_path), str(eligibility_path))
    assert decision_a_1["decision_id"] == decision_a_2["decision_id"]

    policy_b = _load_default_policy()
    policy_b["version"] = "1.0.1"
    policy_b_path = _write(tmp_path / "policy-b.json", policy_b)
    monkeypatch.setattr(nsd, "_POLICY_PATH", policy_b_path)
    decision_b_1 = build_next_step_decision(str(manifest_path), str(eligibility_path))
    decision_b_2 = build_next_step_decision(str(manifest_path), str(eligibility_path))

    assert decision_b_1["decision_id"] == decision_b_2["decision_id"]
    assert decision_a_1["decision_id"] != decision_b_1["decision_id"]
