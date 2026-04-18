from __future__ import annotations

from spectrum_systems.modules.wpg.context_governance import build_context_redteam_findings


def test_redteam_context_failures_include_required_adversarial_classes() -> None:
    findings = build_context_redteam_findings(trace_id="trace-ctx-rtx")
    classes = {row["failure_class"] for row in findings["findings"]}
    assert {"stale_data", "missing_sources", "conflicting_inputs", "prompt_like_injection"}.issubset(classes)
