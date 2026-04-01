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
        "sequence_trace_id": "trace-seq",
        "sequence_lineage": ["contracts/examples/roadmap_eligibility_artifact.json"],
        "blocking_issues": ["explicit block"],
        "failure_binding_enforcement": {
            "severity_qualified_failure_count": 1,
            "bound_failure_count": 1,
            "missing_failure_bindings": [],
            "eval_update_refs": ["outputs/control_loop_certification/failure_binding.json"],
            "policy_update_refs": ["outputs/control_loop_certification/policy_update.json"],
            "transition_enforcement_refs": ["outputs/control_loop_certification/transition_consumption.json"],
            "learning_authority_applied": True,
        },
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


def test_promotion_blocks_when_failure_binding_evidence_missing() -> None:
    manifest = _base_manifest("certification_pending")
    manifest["failure_binding_enforcement"]["missing_failure_bindings"] = ["failure-1"]

    decision = evaluate_sequence_transition(manifest, "promoted")

    assert decision.allowed is False
    assert "missing severity-qualified failure binding evidence" in str(decision.reason)


def test_promotion_blocks_when_learning_authority_not_applied() -> None:
    manifest = _base_manifest("certification_pending")
    manifest["failure_binding_enforcement"]["learning_authority_applied"] = False

    decision = evaluate_sequence_transition(manifest, "promoted")

    assert decision.allowed is False
    assert "learning authority not applied" in str(decision.reason)
