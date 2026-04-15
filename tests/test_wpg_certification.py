from __future__ import annotations

from spectrum_systems.modules.wpg.certification import build_lifecycle_certification, build_reusable_template


def test_certification_fails_when_blocking_controls_present() -> None:
    cert = build_lifecycle_certification(trace_id="t1", required_controls=[{"decision": "BLOCK"}])
    assert cert["verdict"] == "FAIL"


def test_reusable_template_requires_sections() -> None:
    template = build_reusable_template(trace_id="t1", required_sections=["summary"])
    assert template["evaluation_refs"]["control_decision"]["decision"] == "ALLOW"
