from __future__ import annotations

import copy
import json
from pathlib import Path

from spectrum_systems.modules.runtime.chaos_failure_intelligence import (
    aggregate_failure_hotspots,
    run_chaos_scenario,
    run_failure_intelligence_loop,
)
from spectrum_systems.modules.runtime.required_eval_coverage import load_required_eval_registry


_FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "chaos_fail_closed_cases.json"


def _fixture() -> dict:
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


def _run(
    *,
    eval_results: list[dict],
    eval_definitions: list[str] | None = None,
    trace_id: str = "trace-chaos-01",
    context: dict | None = None,
    lineage: list[str] | None = None,
    replay: dict | None = None,
    created_at: str = "2026-04-18T00:00:00Z",
) -> dict:
    fixture = _fixture()
    return run_chaos_scenario(
        artifact_family="system_change_governance",
        eval_definitions=eval_definitions or fixture["registry_eval_definitions"],
        eval_results=eval_results,
        trace_id=trace_id,
        run_id="run-chaos-01",
        created_at=created_at,
        stage="execution_gate",
        context=context if context is not None else fixture["base_context"],
        lineage=lineage if lineage is not None else fixture["base_lineage"],
        replay=replay if replay is not None else fixture["base_replay"],
        registry=load_required_eval_registry(),
    )


def test_missing_complexity_justification_record_blocks() -> None:
    fixture = _fixture()
    eval_results = copy.deepcopy(fixture["base_eval_results"])
    eval_results[0].pop("complexity_justification_record")

    result = _run(eval_results=eval_results)

    assert result["observation"]["observed_outcome"] == "halted"
    assert result["failure_record"] is not None


def test_missing_core_loop_alignment_record_blocks() -> None:
    fixture = _fixture()
    eval_results = copy.deepcopy(fixture["base_eval_results"])
    eval_results[1].pop("core_loop_alignment_record")

    result = _run(eval_results=eval_results)

    assert result["observation"]["observed_outcome"] == "halted"
    assert result["failure_record"] is not None


def test_missing_debuggability_record_blocks() -> None:
    fixture = _fixture()
    eval_results = copy.deepcopy(fixture["base_eval_results"])
    eval_results[2].pop("debuggability_record")

    result = _run(eval_results=eval_results)

    assert result["observation"]["observed_outcome"] == "halted"
    assert result["failure_record"] is not None


def test_missing_trace_or_lineage_blocks() -> None:
    fixture = _fixture()
    result = _run(eval_results=fixture["base_eval_results"], trace_id="", lineage=[])

    assert result["observation"]["observed_outcome"] == "halted"
    assert result["observation"]["reason_code"] == "missing_trace_or_lineage"
    assert result["failure_record"] is not None


def test_missing_required_evals_block() -> None:
    fixture = _fixture()
    result = _run(eval_results=fixture["base_eval_results"][:-1])

    assert result["observation"]["observed_outcome"] == "halted"
    assert result["observation"]["reason_code"] == "missing_required_eval_result"
    assert result["failure_record"] is not None


def test_invalid_context_blocks_or_freezes() -> None:
    fixture = _fixture()
    empty_context_result = _run(eval_results=fixture["base_eval_results"], context={})
    conflicting_context_result = _run(
        eval_results=fixture["base_eval_results"],
        context={"scope": "global", "target": "slice"},
    )

    assert empty_context_result["observation"]["observed_outcome"] in {"halted", "paused"}
    assert conflicting_context_result["observation"]["observed_outcome"] in {"halted", "paused"}
    assert empty_context_result["failure_record"] is not None
    assert conflicting_context_result["failure_record"] is not None


def test_replay_mismatch_freezes() -> None:
    fixture = _fixture()
    result = _run(
        eval_results=fixture["base_eval_results"],
        replay={"consistency_status": "mismatch", "expected": "allow", "observed": "block"},
    )

    assert result["observation"]["observed_outcome"] == "paused"
    assert result["observation"]["reason_code"] == "replay_mismatch"
    assert result["failure_record"] is not None


def test_aggregation_produces_expected_counts() -> None:
    fixture = _fixture()
    failing_1 = _run(eval_results=fixture["base_eval_results"][:-1], created_at="2026-04-18T00:00:00Z")
    failing_2 = _run(
        eval_results=fixture["base_eval_results"],
        replay={"consistency_status": "mismatch", "expected": "allow", "observed": "block"},
        created_at="2026-04-18T00:01:00Z",
    )
    records = [failing_1["failure_record"], failing_2["failure_record"]]

    report = aggregate_failure_hotspots(failure_records=records, time_window="last_2_runs")

    assert report["artifact_type"] == "failure_hotspot_report"
    assert report["failure_counts_by_type"] == {"BLOCK": 1, "FREEZE": 1}
    assert report["eval_failure_counts"] == {"debuggability_valid": 1}


def test_maintain_loop_emits_all_reports() -> None:
    fixture = _fixture()
    failed = _run(eval_results=fixture["base_eval_results"][:-1])

    outputs = run_failure_intelligence_loop(
        failure_records=[failed["failure_record"]],
        time_window="last_1_run",
    )

    assert set(outputs.keys()) == {"failure_hotspot_report", "missing_eval_report", "debug_gap_report"}
    assert outputs["failure_hotspot_report"]["artifact_type"] == "failure_hotspot_report"
    assert outputs["missing_eval_report"]["artifact_type"] == "missing_eval_report"
    assert outputs["debug_gap_report"]["artifact_type"] == "debug_gap_report"


def test_no_chaos_scenario_silently_succeeds() -> None:
    fixture = _fixture()
    scenarios = [
        _run(eval_results=fixture["base_eval_results"][:-1]),
        _run(eval_results=fixture["base_eval_results"], trace_id="", lineage=[]),
        _run(eval_results=fixture["base_eval_results"], context={"scope": "global", "target": "slice"}),
        _run(
            eval_results=fixture["base_eval_results"],
            replay={"consistency_status": "mismatch", "expected": "allow", "observed": "block"},
        ),
    ]

    for scenario in scenarios:
        assert scenario["observation"]["observed_outcome"] in {"halted", "paused"}
        assert scenario["failure_record"] is not None
