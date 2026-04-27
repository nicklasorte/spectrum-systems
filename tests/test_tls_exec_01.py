from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.modules.tls_dependency_graph.tls_exec_01 import phase_1_ranking_review
from spectrum_systems.modules.tls_dependency_graph.tls_exec_01 import phase_2_fix_loop
from spectrum_systems.modules.tls_dependency_graph.tls_exec_01 import phase_3_action_layer
from spectrum_systems.modules.tls_dependency_graph.tls_exec_01 import phase_4_control_integration
from spectrum_systems.modules.tls_dependency_graph.tls_exec_01 import phase_5_learning_loop
from spectrum_systems.modules.tls_dependency_graph.tls_exec_01 import run_tls_exec_01


def _base_priority_payload() -> dict:
    return {
        "schema_version": "tls-04.v1",
        "phase": "TLS-04",
        "ranked_systems": [
            {
                "system_id": "A",
                "rank": 1,
                "classification": "active_system",
                "score": 100,
                "spine_position_index": 0,
                "trust_gap_signals": ["missing_lineage"],
                "dependencies": {"upstream": ["B"], "downstream": []},
                "why_now": "short",
                "next_prompt": "Run TLS-FIX-A",
            },
            {
                "system_id": "B",
                "rank": 2,
                "classification": "active_system",
                "score": 80,
                "spine_position_index": 1,
                "trust_gap_signals": [],
                "dependencies": {"upstream": [], "downstream": []},
                "why_now": "no immediate priority signal",
                "next_prompt": "Run TLS-FIX-B",
            },
            {
                "system_id": "C",
                "rank": 3,
                "classification": "h_slice",
                "score": 70,
                "spine_position_index": 2,
                "trust_gap_signals": ["missing_tests"],
                "dependencies": {"upstream": [], "downstream": []},
                "why_now": "on canonical loop; trust-boundary authority; test gap",
                "next_prompt": "Run TLS-FIX-C",
            },
        ],
        "global_ranked_systems": [],
        "top_5": [],
        "requested_candidate_ranking": [
            {
                "system_id": "C",
                "build_now_assessment": "blocked_signal",
                "safe_next_action": "recommendation: harden B before build scope on C.",
                "prerequisite_systems": ["B"],
                "requested_rank": 1,
                "global_rank": 3,
                "score": 70,
            }
        ],
    }


def test_misranking_detection_and_missing_dependencies_and_weak_explanations():
    review = phase_1_ranking_review(_base_priority_payload())
    assert review["summary"]["misranked_count"] == 1
    assert review["summary"]["missing_dependency_count"] == 1
    assert review["summary"]["premature_build_count"] == 1
    assert review["summary"]["weak_explanation_count"] >= 1


def test_ranking_improvement_updates_score_and_rank():
    priority = _base_priority_payload()
    review = phase_1_ranking_review(priority)
    updated, log = phase_2_fix_loop(priority, review)

    rows = {row["system_id"]: row for row in updated["ranked_systems"]}
    assert rows["A"]["score"] < 100
    assert rows["A"]["rank"] > 1
    assert any(item["adjustment_total"] != 0 for item in log["rows"])


def test_action_plan_correctness_contains_required_fields():
    priority = _base_priority_payload()
    review = phase_1_ranking_review(priority)
    updated, _ = phase_2_fix_loop(priority, review)
    action_plan = phase_3_action_layer(updated)

    first = action_plan["systems"][0]
    assert {"next_prompt", "files_to_modify", "expected_artifacts", "stop_condition", "required_tests"}.issubset(first)


def test_control_enforcement_requires_cde_and_sel():
    priority = _base_priority_payload()
    review = phase_1_ranking_review(priority)
    updated, _ = phase_2_fix_loop(priority, review)
    action_plan = phase_3_action_layer(updated)
    control_input, control_decision = phase_4_control_integration(action_plan)

    assert control_input["tls_can_execute_directly"] is False
    assert control_input["cde_approval_required"] is True
    assert control_decision["constraints"]["sel_must_enforce"] is True
    assert control_decision["allowed_execution"] is False


def test_learning_updates_are_emitted(tmp_path: Path):
    priority = _base_priority_payload()
    review = phase_1_ranking_review(priority)
    _updated, log = phase_2_fix_loop(priority, review)
    _control_input, control_decision = phase_4_control_integration({"systems": []})
    learning, weight_updates = phase_5_learning_loop(review, log, control_decision)

    assert "ranking_quality" in learning
    assert "recommended_weight_updates" in weight_updates


def test_end_to_end_writes_all_artifacts(tmp_path: Path):
    priority_path = tmp_path / "system_dependency_priority_report.json"
    out_dir = tmp_path / "tls"
    top_out = tmp_path / "top_system_dependency_priority_report.json"
    priority_path.write_text(json.dumps(_base_priority_payload()), encoding="utf-8")

    run_tls_exec_01(priority_path, out_dir, top_out)

    expected = [
        out_dir / "tls_ranking_review_report.json",
        out_dir / "system_dependency_priority_report.json",
        out_dir / "ranking_adjustment_log.json",
        out_dir / "tls_action_plan.json",
        out_dir / "tls_control_input_artifact.json",
        out_dir / "tls_control_decision_artifact.json",
        out_dir / "tls_learning_record.json",
        out_dir / "tls_weight_update_record.json",
        top_out,
    ]
    for path in expected:
        assert path.is_file(), f"missing artifact: {path}"
