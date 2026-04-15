from __future__ import annotations

from spectrum_systems.modules.wpg.common import StageContext
from spectrum_systems.modules.wpg.critique_memory import build_industry_critique_profile


def test_industry_profiles_include_deployment_ambiguity_burden() -> None:
    signal = {
        "artifact_type": "comment_matrix_signal_artifact",
        "schema_version": "1.0.0",
        "trace_id": "t1",
        "outputs": {
            "signal_count": 1,
            "malformed_count": 0,
            "signals": [
                {"issue_class": "deployment ambiguity burden", "stakeholder": "Industry", "section_type": "ops", "resolution_pattern": "compliance cost", "severity": "high"}
            ],
        },
        "evaluation_refs": {"control_decision": {"decision": "ALLOW"}},
    }
    profile = build_industry_critique_profile(signal, StageContext(run_id="r1", trace_id="t1"))
    themes = {row["theme"] for row in profile["outputs"]["objections"] if row["count"] > 0}
    assert {"deployment", "ambiguity", "burden"}.issubset(themes)
