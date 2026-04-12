from __future__ import annotations

from spectrum_systems.modules.runtime.apx_module_system import (
    DatasetRegistry,
    build_human_review_artifacts,
    build_review_operations,
    compile_patterns,
    context_quality_check,
    faq_certification_gate,
    faq_eval_suite,
    module_admission_gate,
    run_faq_module,
    run_module_pattern,
    run_policy_backtest,
)


def test_module_admission_fails_closed_when_requirements_missing() -> None:
    denied = module_admission_gate({"schemas": ["x"]})
    assert denied["admitted"] is False
    assert denied["fail_closed"] is True

    admitted = module_admission_gate(
        {
            "schemas": ["transcript_faq_artifact"],
            "evals": ["grounding"],
            "trace": ["trace_id"],
            "context_requirements": ["freshness"],
            "promotion_path": ["eval", "certification"],
        }
    )
    assert admitted["admitted"] is True


def test_faq_governed_path_eval_and_certification_gate() -> None:
    faq = run_faq_module(
        trace_id="trace-faq",
        transcript="What is policy A?\nWho approves release?",
        docs=[{"doc_id": "d1", "content": "What policy A requires evidence."}, {"doc_id": "d2", "content": "Who approves release is TPA."}],
    )
    eval_result = faq_eval_suite(faq)
    cert = faq_certification_gate(faq_eval=eval_result, trace_complete=True, replay_consistent=True)

    assert faq["artifact_type"] == "transcript_faq_artifact"
    assert eval_result["all_passed"] is True
    assert cert["certified"] is True


def test_review_loop_override_bounds_and_context_failure() -> None:
    review = build_review_operations(trace_id="trace-1", failed=True)
    human = build_human_review_artifacts(trace_id="trace-1", outcome="allow", override=True)
    bad_context = context_quality_check({"freshness_days": 99, "conflicts": ["x"], "evidence_count": 0})

    assert review["fix_slice_request"]["requested"] is True
    assert human["override_record"]["bounded"] is True
    assert bad_context["valid"] is False


def test_pattern_backtest_dataset_registry_and_module_reuse() -> None:
    patterns = compile_patterns(failures=["f1"], corrections=["c1"], overrides=["o1"])
    backtest = run_policy_backtest(policy_candidates=patterns["policy_candidates"], dataset_rows=[{"id": 1}, {"id": 2}])
    registry = DatasetRegistry()
    v1 = registry.register("faq_dataset", [{"id": 1}])
    v2 = registry.register("faq_dataset", [{"id": 1}, {"id": 2}])
    minutes = run_module_pattern(module_kind="meeting_minutes", trace_id="trace-mm", transcript="What changed?", docs=[{"doc_id": "d", "content": "What changed in meeting."}])
    paper = run_module_pattern(module_kind="working_paper", trace_id="trace-wp", transcript="What is claim?", docs=[{"doc_id": "d", "content": "What is claim evidence."}])
    comments = run_module_pattern(module_kind="comment_resolution", trace_id="trace-cr", transcript="What comment resolved?", docs=[{"doc_id": "d", "content": "What comment resolved statement."}])

    assert backtest["auto_activation"] is False
    assert v1["version"] == "v1"
    assert v2["version"] == "v2"
    assert minutes["module_kind"] == "meeting_minutes"
    assert paper["module_kind"] == "working_paper"
    assert comments["module_kind"] == "comment_resolution"
