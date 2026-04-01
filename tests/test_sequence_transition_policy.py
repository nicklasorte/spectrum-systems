from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.orchestration.sequence_transition_policy import evaluate_sequence_transition

_REPO_ROOT = Path(__file__).resolve().parents[1]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "sequence_replay"


def _base_manifest(state: str) -> dict:
    return {
        "cycle_id": "cycle-seq",
        "current_state": state,
        "roadmap_artifact_path": str(_REPO_ROOT / "docs" / "roadmap" / "system_roadmap.md"),
        "execution_report_paths": [
            str(_REPO_ROOT / "contracts" / "examples" / "execution_report_artifact.json"),
            str(_REPO_ROOT / "contracts" / "examples" / "execution_report_artifact.json"),
            str(_REPO_ROOT / "contracts" / "examples" / "execution_report_artifact.json"),
        ],
        "implementation_review_paths": [str(_REPO_ROOT / "tests" / "fixtures" / "autonomous_cycle" / "implementation_review_claude.json")],
        "certification_status": "passed",
        "certification_record_path": str(_REPO_ROOT / "contracts" / "examples" / "done_certification_record.json"),
        "decision_blocked": False,
        "control_allow_promotion": True,
        "required_judgments": ["artifact_release_readiness"],
        "judgment_record_path": str(_REPO_ROOT / "contracts" / "examples" / "judgment_record.json"),
        "judgment_application_record_path": str(_REPO_ROOT / "contracts" / "examples" / "judgment_application_record.json"),
        "judgment_eval_result_path": str(_REPO_ROOT / "contracts" / "examples" / "judgment_eval_result.json"),
        "control_loop_gate_proof": {
            "severity_linkage_complete": True,
            "deterministic_transition_consumption": True,
            "policy_caused_action_observed": True,
            "recurrence_prevention_linked": True,
            "failure_binding_required_for_progression": True,
            "missing_binding_blocks_progression": True,
            "advisory_only_learning_rejected": True,
            "transition_policy_consumes_binding_deterministically": True,
            "severity_linkage_refs": ["contracts/examples/failure_eval_case.json"],
            "transition_consumption_refs": ["contracts/examples/prompt_queue_transition_decision.json"],
            "policy_action_refs": ["contracts/examples/pqx_slice_execution_record.json"],
            "recurrence_prevention_refs": ["contracts/examples/failure_policy_binding.json"],
        },
        "sequence_trace_id": "trace-seq",
        "sequence_lineage": ["contracts/examples/roadmap_eligibility_artifact.json"],
        "blocking_issues": ["explicit block"],
    }


def test_sequence_happy_path_fixture_allows_ordered_transitions() -> None:
    fixture = json.loads((_FIXTURES / "happy_path.json").read_text(encoding="utf-8"))
    states = fixture["states"]
    for idx in range(len(states) - 1):
        manifest = _base_manifest(states[idx])
        decision = evaluate_sequence_transition(manifest, states[idx + 1])
        assert decision.allowed is True


def test_sequence_broken_path_fixture_blocks_illegal_transitions() -> None:
    fixture = json.loads((_FIXTURES / "broken_paths.json").read_text(encoding="utf-8"))
    for case in fixture["cases"]:
        manifest = _base_manifest(case["from"])
        decision = evaluate_sequence_transition(manifest, case["to"])
        assert decision.allowed is False
        assert case["reason"] in str(decision.reason)


def test_sequence_indeterminate_fixture_blocks_inconsistent_evidence() -> None:
    fixture = json.loads((_FIXTURES / "indeterminate_paths.json").read_text(encoding="utf-8"))
    for case in fixture["cases"]:
        manifest = _base_manifest(case["from"])
        manifest.update(case.get("mutations", {}))
        decision = evaluate_sequence_transition(manifest, case["to"])
        assert decision.allowed is False
        assert case["reason"] in str(decision.reason)


def test_promotion_blocks_when_failure_binding_proof_missing() -> None:
    manifest = _base_manifest("certification_pending")
    manifest["control_loop_gate_proof"]["failure_binding_required_for_progression"] = False
    decision = evaluate_sequence_transition(manifest, "promoted")
    assert decision.allowed is False
    assert "failure_binding_required_for_progression" in str(decision.reason)


def test_promotion_blocks_when_required_judgment_artifact_missing() -> None:
    manifest = _base_manifest("certification_pending")
    manifest["judgment_eval_result_path"] = ""
    decision = evaluate_sequence_transition(manifest, "promoted")
    assert decision.allowed is False
    assert "judgment_eval_result_path" in str(decision.reason)
