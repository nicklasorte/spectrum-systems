from spectrum_systems.orchestration.wpg_pipeline import run_wpg_pipeline


def test_regression_eval_cases_bound_and_canonical_owner_emits_control_decision() -> None:
    transcript = {
        "segments": [
            {"segment_id": "r1", "speaker": "A", "agency": "FAA", "text": "Can we deploy now? Yes we can deploy now."},
            {"segment_id": "r2", "speaker": "B", "agency": "DoD", "text": "Can we deploy now? No we cannot deploy now."},
        ]
    }
    bundle = run_wpg_pipeline(transcript, run_id="run-reg", trace_id="trace-reg")
    regressions = bundle["artifact_chain"]["regression_eval_cases"]["outputs"]
    assert regressions["repeated_failure_class_blocked"] is True
    assert regressions["cases"]

    canonical_control = bundle["artifact_chain"]["semantic_control_decision_record"]
    assert canonical_control["artifact_type"] == "evaluation_control_decision"
    assert canonical_control["decision"] in {"allow", "warn", "freeze", "deny"}
