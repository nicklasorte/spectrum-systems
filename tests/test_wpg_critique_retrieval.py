from __future__ import annotations

from spectrum_systems.modules.wpg.critique_memory import retrieve_critique_memory


def test_retrieve_critique_memory_warns_when_missing() -> None:
    signal = {
        "artifact_type": "comment_matrix_signal_artifact",
        "schema_version": "1.0.0",
        "trace_id": "t1",
        "outputs": {"signal_count": 0, "malformed_count": 0, "signals": []},
        "evaluation_refs": {"control_decision": {"decision": "ALLOW"}},
    }
    out = retrieve_critique_memory(signal, trace_id="t1", band="C", topic="x", stakeholder="FCC", section_type="methods")
    assert out["evaluation_refs"]["control_decision"]["decision"] == "WARN"
