from spectrum_systems.modules.runtime.cax import build_arbitration_inputs, emit_control_arbitration_record
from spectrum_systems.modules.runtime.ctx import assemble_context_bundle


def test_control_arbitration_artifact_is_replay_stable() -> None:
    inputs = build_arbitration_inputs(
        tax_decision="complete",
        bax_decision="allow",
        tpa_decision="allow",
        required_signals_present=True,
        trace_complete=True,
        replay_blocking=False,
        drift_blocking=False,
    )
    record_a = emit_control_arbitration_record(
        run_id="run-1",
        trace_id="trace-1",
        policy_version="p1",
        reason_bundle_ref="rb1",
        input_refs={"tax": "t1", "bax": "b1"},
        inputs=inputs,
    )
    record_b = emit_control_arbitration_record(
        run_id="run-1",
        trace_id="trace-1",
        policy_version="p1",
        reason_bundle_ref="rb1",
        input_refs={"tax": "t1", "bax": "b1"},
        inputs=inputs,
    )
    assert record_a == record_b


def test_context_bundle_manifest_hash_is_replay_stable() -> None:
    recipe = {
        "recipe_id": "CTX-RCP-1",
        "artifact_family": "review_projection_bundle_artifact",
        "strict_mode": True,
        "required_sources": ["a"],
    }
    candidates = [{"source_id": "a", "trace_ref": "t1", "content_hash": "h1", "priority": 1, "fresh": True}]
    a = assemble_context_bundle(run_id="run", trace_id="trace", recipe=recipe, candidates=candidates)
    b = assemble_context_bundle(run_id="run", trace_id="trace", recipe=recipe, candidates=candidates)
    assert a["manifest_hash"] == b["manifest_hash"]
