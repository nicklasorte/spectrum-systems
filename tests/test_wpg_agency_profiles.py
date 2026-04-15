from __future__ import annotations

from spectrum_systems.modules.wpg.common import StageContext
from spectrum_systems.modules.wpg.critique_memory import build_agency_critique_profile


def test_agency_profiles_queryable() -> None:
    signal = {
        "artifact_type": "comment_matrix_signal_artifact",
        "schema_version": "1.0.0",
        "trace_id": "t1",
        "outputs": {
            "signal_count": 2,
            "malformed_count": 0,
            "signals": [
                {"issue_class": "ambiguity", "stakeholder": "FCC", "section_type": "methods", "resolution_pattern": "clarify", "severity": "medium"},
                {"issue_class": "ambiguity", "stakeholder": "FCC", "section_type": "summary", "resolution_pattern": "clarify", "severity": "low"},
            ],
        },
        "evaluation_refs": {"control_decision": {"decision": "ALLOW"}},
    }
    profile = build_agency_critique_profile(signal, StageContext(run_id="r1", trace_id="t1"))
    assert profile["outputs"]["profiles"][0]["agency"] == "FCC"
