from __future__ import annotations

import copy

from spectrum_systems.contracts import load_example
from spectrum_systems.modules.runtime.repo_health_eval import build_repo_health_eval
from spectrum_systems.modules.runtime.repo_process_flow_doc import generate_repo_process_flow_markdown
from spectrum_systems.modules.runtime.review_roadmap_generator import build_review_roadmap


def _snapshot() -> dict:
    return copy.deepcopy(load_example("repo_review_snapshot"))


def test_process_flow_doc_contains_required_sections_and_weak_points() -> None:
    snapshot = _snapshot()
    snapshot["findings_summary"]["eval_coverage_gaps"] = 1
    eval_artifacts = build_repo_health_eval(snapshot)
    roadmap = build_review_roadmap(
        snapshot=snapshot,
        control_decision={"system_response": "allow", "decision_id": "ECD-ALLOW"},
    )
    doc = generate_repo_process_flow_markdown(
        snapshot=snapshot,
        eval_result=eval_artifacts["eval_result"],
        eval_summary=eval_artifacts["eval_summary"],
        control_decision={"system_response": "allow"},
        roadmap_plan=roadmap,
        sequence_state={"requested_slice_ids": ["PQX-QUEUE-01", "PQX-QUEUE-02"]},
    )
    assert "## Basic flow" in doc
    assert "## Expanded flow" in doc
    assert "## Current Weak Points" in doc
    assert "Roadmap Selection" in doc
    assert "Control Authorization" in doc
    assert "Authorized Batch Execution (PQX)" in doc
    assert "Roadmap Progress Update (roadmap_progress_update)" in doc
    assert "Next Candidate Selection" in doc
    assert "missing eval coverage" in doc


def test_process_flow_doc_is_deterministic_for_same_inputs() -> None:
    snapshot = _snapshot()
    eval_artifacts = build_repo_health_eval(snapshot)
    roadmap = build_review_roadmap(
        snapshot=snapshot,
        control_decision={"system_response": "allow", "decision_id": "ECD-ALLOW"},
    )
    kwargs = {
        "snapshot": snapshot,
        "eval_result": eval_artifacts["eval_result"],
        "eval_summary": eval_artifacts["eval_summary"],
        "control_decision": {"system_response": "allow"},
        "roadmap_plan": roadmap,
        "sequence_state": {"requested_slice_ids": ["PQX-QUEUE-01", "PQX-QUEUE-02"]},
    }
    first = generate_repo_process_flow_markdown(**kwargs)
    second = generate_repo_process_flow_markdown(**kwargs)
    assert first == second
