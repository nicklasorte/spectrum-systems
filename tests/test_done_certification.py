"""Tests for DONE-01 deterministic fail-closed done certification gate."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from spectrum_systems.modules.governance.done_certification import (
    DoneCertificationError,
    run_done_certification,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_EXAMPLES = _REPO_ROOT / "contracts" / "examples"


def _load_example(name: str) -> Dict[str, Any]:
    return json.loads((_EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))


def _regression_result_pass() -> Dict[str, Any]:
    return {
        "blocked": False,
        "regression_status": "pass",
        "schema_version": "1.1.0",
        "artifact_type": "regression_result",
        "run_id": "reg-run-001",
        "suite_id": "suite-001",
        "created_at": "2026-03-28T00:00:00Z",
        "total_traces": 1,
        "passed_traces": 1,
        "failed_traces": 0,
        "pass_rate": 1.0,
        "overall_status": "pass",
        "results": [
            {
                "trace_id": "trace-001",
                "replay_result_id": "replay-001",
                "analysis_id": "analysis-001",
                "decision_status": "consistent",
                "reproducibility_score": 1.0,
                "drift_type": "",
                "passed": True,
                "failure_reasons": [],
                "baseline_replay_result_id": "base-001",
                "current_replay_result_id": "cur-001",
                "baseline_trace_id": "trace-001",
                "current_trace_id": "trace-001",
                "baseline_reference": "replay_result:base-001",
                "current_reference": "replay_result:cur-001",
                "mismatch_summary": [],
                "comparison_digest": "a" * 64,
            }
        ],
        "summary": {"drift_counts": {}, "average_reproducibility_score": 1.0},
    }


def _write_json(path: Path, payload: Dict[str, Any]) -> str:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def _write_inputs(tmp_path: Path) -> Dict[str, str]:
    replay = _load_example("replay_result")
    replay["consistency_status"] = "match"
    replay["drift_detected"] = False
    replay["failure_reason"] = None
    trace_id = replay["trace_id"]
    run_id = replay["replay_run_id"]

    regression = _regression_result_pass()
    regression["run_id"] = run_id
    regression["results"][0]["trace_id"] = trace_id
    regression["results"][0]["baseline_trace_id"] = trace_id
    regression["results"][0]["current_trace_id"] = trace_id
    certification_pack = _load_example("control_loop_certification_pack")
    certification_pack["run_id"] = run_id
    certification_pack["decision"] = "pass"
    certification_pack["certification_status"] = "certified"
    certification_pack["provenance_trace_refs"]["trace_refs"] = [trace_id]

    error_budget = _load_example("error_budget_status")
    error_budget["budget_status"] = "healthy"
    error_budget["trace_refs"]["trace_id"] = trace_id

    control_decision = _load_example("evaluation_control_decision")
    control_decision["run_id"] = run_id
    control_decision["system_status"] = "healthy"
    control_decision["system_response"] = "allow"
    control_decision["decision"] = "allow"
    control_decision["trace_id"] = trace_id

    failure_injection = _load_example("governed_failure_injection_summary")
    failure_injection["fail_count"] = 0
    failure_injection["pass_count"] = failure_injection["case_count"]
    failure_injection["trace_refs"]["primary"] = trace_id
    failure_injection["trace_refs"]["related"] = []
    for result in failure_injection["results"]:
        result["passed"] = True
        result["expected_outcome"] = "block"
        result["observed_outcome"] = "block"
        result["invariant_violations"] = []
        result["trace_refs"]["primary"] = trace_id
        result["trace_refs"]["related"] = []

    return {
        "replay_result_ref": _write_json(tmp_path / "replay.json", replay),
        "regression_result_ref": _write_json(tmp_path / "regression.json", regression),
        "certification_pack_ref": _write_json(tmp_path / "certification_pack.json", certification_pack),
        "error_budget_ref": _write_json(tmp_path / "error_budget.json", error_budget),
        "policy_ref": _write_json(tmp_path / "policy.json", control_decision),
        "enforcement_result_ref": _write_json(
            tmp_path / "enforcement.json",
            {
                "artifact_type": "enforcement_result",
                "schema_version": "1.1.0",
                "enforcement_result_id": "enf-001",
                "timestamp": "2026-03-28T00:00:00Z",
                "trace_id": trace_id,
                "run_id": run_id,
                "input_decision_reference": "ecd-001",
                "enforcement_action": "allow_execution",
                "final_status": "allow",
                "rationale_code": "allow_authorized",
                "fail_closed": False,
                "enforcement_path": "baf_single_path",
                "provenance": {
                    "source_artifact_type": "evaluation_control_decision",
                    "source_artifact_id": control_decision["decision_id"],
                },
            },
        ),
        "eval_coverage_summary_ref": _write_json(
            tmp_path / "coverage.json",
            {
                "artifact_type": "eval_coverage_summary",
                "schema_version": "1.1.0",
                "id": "coverage-001",
                "coverage_run_id": run_id,
                "timestamp": "2026-03-28T00:00:00Z",
                "trace_refs": {"primary": trace_id, "related": []},
                "dataset_refs": ["contracts/examples/eval_case_dataset.json"],
                "total_eval_cases": 1,
                "covered_slices": ["runtime_guardrails"],
                "uncovered_required_slices": [],
                "slice_case_counts": {"runtime_guardrails": 1},
                "risk_weighted_coverage_score": 1.0,
                "coverage_gaps": [],
            },
        ),
        "failure_injection_ref": _write_json(tmp_path / "failure_injection.json", failure_injection),
    }


def test_certification_pass(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    first = run_done_certification(refs)
    second = run_done_certification(refs)

    assert first["final_status"] == "PASSED"
    assert first["system_response"] == "allow"
    assert first["blocking_reasons"] == []
    assert first["trust_spine_invariant_result"]["passed"] is True
    assert first == second


def test_trust_spine_threshold_context_mismatch_blocks(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    control = json.loads(Path(refs["policy_ref"]).read_text(encoding="utf-8"))
    control["threshold_context"] = "comparative_analysis"
    Path(refs["policy_ref"]).write_text(json.dumps(control), encoding="utf-8")

    result = run_done_certification(refs)
    assert result["final_status"] == "FAILED"
    assert result["check_results"]["trust_spine_invariants"]["passed"] is False
    assert "TRUST_SPINE_THRESHOLD_CONTEXT_MISMATCH" in result["trust_spine_invariant_result"]["blocking_reasons"]


def test_trust_spine_coverage_contradiction_blocks(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    coverage = json.loads(Path(refs["eval_coverage_summary_ref"]).read_text(encoding="utf-8"))
    coverage["uncovered_required_slices"] = ["runtime_guardrails"]
    Path(refs["eval_coverage_summary_ref"]).write_text(json.dumps(coverage), encoding="utf-8")

    result = run_done_certification(refs)
    assert result["final_status"] == "FAILED"
    assert "TRUST_SPINE_COVERAGE_PROMOTION_CONTRADICTION" in result["trust_spine_invariant_result"]["blocking_reasons"]


def test_replay_failure_blocks(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    replay = json.loads(Path(refs["replay_result_ref"]).read_text(encoding="utf-8"))
    replay["consistency_status"] = "mismatch"
    replay["drift_detected"] = True
    Path(refs["replay_result_ref"]).write_text(json.dumps(replay), encoding="utf-8")

    result = run_done_certification(refs)
    assert result["final_status"] == "FAILED"
    assert result["system_response"] == "block"


def test_regression_failure_blocks(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    regression = json.loads(Path(refs["regression_result_ref"]).read_text(encoding="utf-8"))
    regression["failed_traces"] = 1
    regression["passed_traces"] = 0
    regression["overall_status"] = "fail"
    regression["regression_status"] = "fail"
    regression["results"][0]["passed"] = False
    regression["results"][0]["mismatch_summary"] = [{"field": "x", "baseline_value": 1, "current_value": 2}]
    Path(refs["regression_result_ref"]).write_text(json.dumps(regression), encoding="utf-8")

    result = run_done_certification(refs)
    assert result["final_status"] == "FAILED"
    assert result["system_response"] == "block"


def test_missing_artifact_blocks(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    Path(refs["certification_pack_ref"]).unlink()
    with pytest.raises(DoneCertificationError, match="file not found"):
        run_done_certification(refs)


def test_error_budget_exhausted_blocks(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    error_budget = json.loads(Path(refs["error_budget_ref"]).read_text(encoding="utf-8"))
    error_budget["budget_status"] = "exhausted"
    Path(refs["error_budget_ref"]).write_text(json.dumps(error_budget), encoding="utf-8")

    result = run_done_certification(refs)
    assert result["final_status"] == "FAILED"
    assert result["system_response"] == "block"


def test_fail_closed_violation_blocks(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    failure = json.loads(Path(refs["failure_injection_ref"]).read_text(encoding="utf-8"))
    failure["results"][0]["observed_outcome"] = "allow"
    failure["results"][0]["expected_outcome"] = "block"
    Path(refs["failure_injection_ref"]).write_text(json.dumps(failure), encoding="utf-8")

    result = run_done_certification(refs)
    assert result["final_status"] == "FAILED"
    assert result["system_response"] == "block"


def test_invalid_schema_blocks(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    replay = json.loads(Path(refs["replay_result_ref"]).read_text(encoding="utf-8"))
    replay["unknown_field"] = "unexpected"
    Path(refs["replay_result_ref"]).write_text(json.dumps(replay), encoding="utf-8")

    with pytest.raises(DoneCertificationError, match="failed schema validation"):
        run_done_certification(refs)


def test_trace_mismatch_blocks(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    control_decision = json.loads(Path(refs["policy_ref"]).read_text(encoding="utf-8"))
    control_decision["trace_id"] = "trace-mismatch-999"
    Path(refs["policy_ref"]).write_text(json.dumps(control_decision), encoding="utf-8")

    with pytest.raises(DoneCertificationError, match="PROVENANCE_TRACE_MISMATCH"):
        run_done_certification(refs)


def test_run_mismatch_fails_closed(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    control_decision = json.loads(Path(refs["policy_ref"]).read_text(encoding="utf-8"))
    control_decision["run_id"] = "run-mismatch-999"
    Path(refs["policy_ref"]).write_text(json.dumps(control_decision), encoding="utf-8")

    with pytest.raises(DoneCertificationError, match="PROVENANCE_RUN_MISMATCH"):
        run_done_certification(refs)


def test_explicit_cross_run_policy_allows_cross_run_reference(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    control_decision = json.loads(Path(refs["policy_ref"]).read_text(encoding="utf-8"))
    control_decision["run_id"] = "run-cross-run-allowed"
    Path(refs["policy_ref"]).write_text(json.dumps(control_decision), encoding="utf-8")

    result = run_done_certification(
        {
            **refs,
            "identity_policy": {"allow_cross_run_reference": True},
        }
    )
    assert result["final_status"] == "PASSED"


def test_missing_trace_on_required_artifact_fails_closed(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    regression = json.loads(Path(refs["regression_result_ref"]).read_text(encoding="utf-8"))
    regression["results"][0].pop("trace_id", None)
    Path(refs["regression_result_ref"]).write_text(json.dumps(regression), encoding="utf-8")

    with pytest.raises(DoneCertificationError, match="failed schema validation"):
        run_done_certification(refs)


def test_ambiguous_certification_pack_trace_refs_blocks(tmp_path: Path) -> None:
    refs = _write_inputs(tmp_path)
    certification_pack = json.loads(Path(refs["certification_pack_ref"]).read_text(encoding="utf-8"))
    replay = json.loads(Path(refs["replay_result_ref"]).read_text(encoding="utf-8"))
    certification_pack["provenance_trace_refs"]["trace_refs"] = [
        replay["trace_id"],
        f"{replay['trace_id']}-other",
    ]
    Path(refs["certification_pack_ref"]).write_text(json.dumps(certification_pack), encoding="utf-8")

    result = run_done_certification(refs)
    assert result["final_status"] == "FAILED"
    assert result["system_response"] == "block"
    assert any(reason.startswith("TRACE_LINKAGE_AMBIGUOUS:") for reason in result["blocking_reasons"])
    assert result["check_results"]["trace_linkage"]["passed"] is False
