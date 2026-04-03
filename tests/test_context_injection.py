from __future__ import annotations

from spectrum_systems.modules.runtime.context_injection import build_context_injection_payload


def test_injection_payload_is_bounded_and_traceable() -> None:
    bundle = {
        "artifact_type": "context_bundle_v2",
        "context_id": "ctx2-f9f81798fe65e4bb",
        "trace_id": "trace-ctx-1",
        "target_scope": {"scope_type": "batch_id", "scope_id": "BATCH-O"},
        "selected_artifact_refs": [f"eval_result:eval-{i}" for i in range(20)],
        "source_refs": [f"ref:{i}" for i in range(50)],
    }

    payload = build_context_injection_payload(context_bundle=bundle, consumer="codex", max_refs=8)
    assert payload["advisory_only"] is True
    assert payload["hidden_context_allowed"] is False
    assert len(payload["selected_artifact_refs"]) == 8
    assert len(payload["source_refs"]) == 16


def test_source_refs_are_preserved_with_bounding() -> None:
    bundle = {
        "artifact_type": "context_bundle_v2",
        "context_id": "ctx2-f9f81798fe65e4bb",
        "trace_id": "trace-ctx-1",
        "target_scope": {"scope_type": "batch_id", "scope_id": "BATCH-O"},
        "selected_artifact_refs": ["review_artifact:r1"],
        "source_refs": ["review_artifact:r1", "build_report:b1"],
    }
    payload = build_context_injection_payload(context_bundle=bundle, consumer="pqx", max_refs=4)
    assert payload["source_refs"] == ["review_artifact:r1", "build_report:b1"]
