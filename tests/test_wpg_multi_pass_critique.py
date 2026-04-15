from __future__ import annotations

from spectrum_systems.modules.wpg.common import StageContext
from spectrum_systems.modules.wpg.critique_loop import run_multi_pass_critique


def test_multi_pass_critique_blocks_high_severity() -> None:
    sections = {"outputs": {"sections": [{"title": "Methods"}]}}
    agency = {"outputs": {"profiles": [{"agency": "FCC", "recurring_objections": ["x"], "top_resolution_pattern": "deploy_gate"}]}}
    industry = {"outputs": {"objections": [{"theme": "deployment", "count": 1}]}}
    out = run_multi_pass_critique(sections_artifact=sections, agency_profile=agency, industry_profile=industry, ctx=StageContext(run_id="r1", trace_id="t1"))
    assert out["evaluation_refs"]["control_decision"]["decision"] == "BLOCK"
