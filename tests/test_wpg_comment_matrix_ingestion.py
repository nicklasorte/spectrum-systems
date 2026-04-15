from __future__ import annotations

import pytest

from spectrum_systems.modules.wpg.common import StageContext, WPGError
from spectrum_systems.modules.wpg.critique_memory import ingest_comment_matrix_signal


def test_ingest_comment_matrix_signal_structures_memory() -> None:
    matrix = {
        "artifact_type": "comment_resolution_matrix",
        "schema_version": "1.0.0",
        "trace_id": "t1",
        "outputs": {
            "rows": [
                {
                    "issue_class": "ambiguity",
                    "stakeholder": "FCC",
                    "section_type": "methods",
                    "resolution_pattern": "clarify language",
                    "severity": "medium",
                }
            ]
        },
    }
    out = ingest_comment_matrix_signal(matrix, StageContext(run_id="r1", trace_id="t1"))
    assert out["outputs"]["signal_count"] == 1
    assert out["evaluation_refs"]["control_decision"]["decision"] == "ALLOW"


def test_ingest_comment_matrix_signal_blocks_malformed_matrix() -> None:
    matrix = {"outputs": {"rows": ["bad-row"]}}
    out = ingest_comment_matrix_signal(matrix, StageContext(run_id="r2", trace_id="t2"))
    assert out["evaluation_refs"]["control_decision"]["decision"] == "BLOCK"
