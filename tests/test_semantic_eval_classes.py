from spectrum_systems.modules.runtime.semantic_eval import evaluate_semantic_classes, semantic_control_decision


def test_semantic_eval_detects_contradiction_and_blocks() -> None:
    transcript = {
        "segments": [
            {"text": "Can we deploy now? Yes we can deploy now."},
            {"text": "Can we deploy now? No we cannot deploy now."},
        ]
    }
    faqs = [{"question": "Can we deploy now?", "answer": "Yes we can deploy now."}]
    results = evaluate_semantic_classes(trace_id="t1", stage="working_paper_assembly", transcript=transcript, faqs=faqs)
    decision = semantic_control_decision(results)
    assert any(r["eval_class"] == "contradiction_detection" and r["result"] == "fail" for r in results)
    assert decision.decision == "BLOCK"


def test_grounding_failure_blocks() -> None:
    transcript = {"segments": [{"text": "Status is unknown pending certification."}]}
    faqs = [{"question": "What is status?", "answer": "Deployment approved immediately."}]
    results = evaluate_semantic_classes(trace_id="t2", stage="working_paper_assembly", transcript=transcript, faqs=faqs)
    decision = semantic_control_decision(results)
    assert "grounding_failure" in decision.reasons
    assert decision.decision == "BLOCK"
