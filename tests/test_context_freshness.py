from __future__ import annotations

from datetime import datetime, timezone

from spectrum_systems.modules.wpg.context_governance import enforce_context_freshness


def test_context_freshness_classification_and_freeze_for_stale_critical() -> None:
    output = enforce_context_freshness(
        [
            {
                "source_type": "transcript",
                "source_ref": "transcript_artifact",
                "captured_at": "2026-04-15T00:00:00Z",
            },
            {
                "source_type": "prior_wpg_outputs",
                "source_ref": "prior_working_paper_artifact",
                "captured_at": "2026-03-01T00:00:00Z",
            },
        ],
        now=datetime(2026, 4, 18, tzinfo=timezone.utc),
    )
    assert output["freshness_status"] == "fail"
    assert output["freshness_action"] == "FREEZE"
    assert any(row["source_ref"] == "transcript_artifact" for row in output["critical_stale_sources"])
