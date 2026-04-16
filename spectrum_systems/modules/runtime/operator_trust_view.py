from __future__ import annotations
from typing import Dict
from spectrum_systems.modules.runtime.bne_utils import ensure_contract


def build_operator_trust_view(*, trace_id: str, trust_posture: dict, evidence_gaps: dict, unresolved_critique: dict, override_hotspots: dict, certification_state: str, phase_state: str, top_bottlenecks: list[str]) -> Dict[str, any]:
    return ensure_contract({
        "artifact_type":"operator_trust_bottleneck_view",
        "schema_version":"1.0.0",
        "trace_id":trace_id,
        "outputs":{
            "trust_posture":trust_posture,
            "evidence_gaps":evidence_gaps,
            "unresolved_critique":unresolved_critique,
            "override_hotspots":override_hotspots,
            "certification_state":certification_state,
            "phase_state":phase_state,
            "top_bottlenecks":top_bottlenecks,
        },
    }, "operator_trust_bottleneck_view")
