from spectrum_systems.modules.runtime.semantic_eval import evaluate_semantic_classes, summarize_semantic_evidence


def test_semantic_eval_detects_contradiction_and_requires_control_review() -> None:
    transcript = {
        "segments": [
            {"text": "Can we deploy now? Yes we can deploy now."},
            {"text": "Can we deploy now? No we cannot deploy now."},
        ]
    }
    faqs = [{"question": "Can we deploy now?", "answer": "Yes we can deploy now."}]
    results = evaluate_semantic_classes(trace_id="t1", stage="working_paper_assembly", transcript=transcript, faqs=faqs)
    evidence = summarize_semantic_evidence(results)
    assert any(r["eval_class"] == "contradiction_detection" and r["result"] == "fail" for r in results)
    assert evidence.requires_control_review is True
    assert evidence.recommended_action == "control_review_required"


def test_grounding_failure_sets_blocking_reason_without_authority_decision_field() -> None:
    transcript = {"segments": [{"text": "Status is unknown pending certification."}]}
    faqs = [{"question": "What is status?", "answer": "Deployment approved immediately."}]
    results = evaluate_semantic_classes(trace_id="t2", stage="working_paper_assembly", transcript=transcript, faqs=faqs)
    evidence = summarize_semantic_evidence(results)
    assert "grounding_failure" in evidence.blocking_reasons
    assert hasattr(evidence, "recommended_action")
