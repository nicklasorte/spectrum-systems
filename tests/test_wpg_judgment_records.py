from __future__ import annotations

from spectrum_systems.modules.wpg.judgment import build_judgment_record


def test_judgment_record_emits_structured_rationale() -> None:
    critique = {"outputs": {"findings": [{"section_title": "Methods", "severity": "medium"}]}}
    record = build_judgment_record(critique_artifact=critique, trace_id="t1")
    assert record["artifact_type"] == "judgment_record"
    assert record["rationale_summary"]
