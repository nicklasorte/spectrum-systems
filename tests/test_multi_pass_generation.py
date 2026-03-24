from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.multi_pass_generation import (  # noqa: E402
    MultiPassGenerationError,
    run_multi_pass_generation,
)


def _input_artifact() -> dict:
    return {
        "artifact_id": 123,
        "summary": "",
        "claims": [
            {"text": "UNSUPPORTED finding", "supporting_evidence_refs": []},
            {"text": "grounded finding", "supporting_evidence_refs": ["ev-1"]},
        ],
    }


def test_full_multi_pass_execution_path() -> None:
    record = run_multi_pass_generation(
        run_id="agent-run-001",
        trace_id="trace-001",
        input_artifact=_input_artifact(),
    )
    assert [p["pass_id"] for p in record["passes"]] == ["pass_1", "pass_2", "pass_3", "final"]
    assert record["passes"][1]["pass_type"] == "critique"
    assert record["passes"][2]["pass_type"] == "refine"


def test_deterministic_outputs_across_runs() -> None:
    r1 = run_multi_pass_generation(run_id="agent-run-002", trace_id="trace-002", input_artifact=_input_artifact())
    r2 = run_multi_pass_generation(run_id="agent-run-002", trace_id="trace-002", input_artifact=_input_artifact())
    assert r1 == r2


def test_critique_flags_known_issues() -> None:
    record = run_multi_pass_generation(run_id="agent-run-003", trace_id="trace-003", input_artifact=_input_artifact())
    critique = record["critique"]
    assert {f["field"] for f in critique["inconsistencies"]} == {"artifact_id"}
    assert {f["field"] for f in critique["missing_elements"]} == {"summary"}
    assert any(f["issue"] == "unsupported_claim" for f in critique["weak_reasoning"])


def test_refinement_corrects_critique_issues() -> None:
    record = run_multi_pass_generation(run_id="agent-run-004", trace_id="trace-004", input_artifact=_input_artifact())
    final_output = record["final_output"]
    assert final_output["artifact_id"] == "123"
    assert final_output["summary"] == "MISSING_REQUIRED_VALUE"
    assert len(final_output["claims"]) == 1


def test_fail_closed_on_invalid_input_artifact() -> None:
    with pytest.raises(MultiPassGenerationError, match="input_artifact must be an object"):
        run_multi_pass_generation(run_id="agent-run-005", trace_id="trace-005", input_artifact="bad")  # type: ignore[arg-type]


def test_trace_linkage_fields_present_for_all_passes() -> None:
    record = run_multi_pass_generation(run_id="agent-run-006", trace_id="trace-006", input_artifact=_input_artifact())
    for p in record["passes"]:
        assert p["trace_id"] == "trace-006"
        assert p["output_ref"].startswith("multi-pass://agent-run-006/")
        assert isinstance(p["parent_pass_ids"], list)
