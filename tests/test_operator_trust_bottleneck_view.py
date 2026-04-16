from spectrum_systems.modules.runtime.operator_trust_view import build_operator_trust_view

def test_operator_view() -> None:
    out=build_operator_trust_view(trace_id="t", trust_posture={}, evidence_gaps={}, unresolved_critique={}, override_hotspots={}, certification_state="CERTIFIED", phase_state="PHASE_B", top_bottlenecks=[])
    assert out["artifact_type"]=="operator_trust_bottleneck_view"
