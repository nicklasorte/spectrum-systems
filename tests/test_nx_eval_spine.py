"""NX-04..06: EVL spine consolidation + adversarial coverage.

These tests exercise the consolidated ``eval_spine`` module to ensure that:
  - missing required evals block (not warn)
  - indeterminate required evals freeze
  - failed schema/contradiction/policy results map to canonical reason codes
  - eval_to_control_signal preserves trace lineage
  - the spine never silently downgrades a fail-closed signal
"""

from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.eval_spine import (
    EvalSpineError,
    build_eval_summary,
    eval_to_control_signal,
    evaluate_artifact_family,
    normalize_eval_result,
    normalize_failure_reason,
    required_eval_lookup,
)


_REGISTRY = {
    "artifact_type": "required_eval_registry",
    "registry_id": "RER-NX-TEST",
    "artifact_version": "1.0.0",
    "schema_version": "1.0.0",
    "standards_version": "1.9.8",
    "policy_reference": {"policy_id": "p1", "policy_version": "2026-04-27"},
    "mappings": [
        {
            "artifact_family": "nx_test_family",
            "required_evals": [
                {"eval_id": "schema_eval", "eval_family": "judgment_eval", "mandatory_for_progression": True},
                {"eval_id": "evidence_eval", "eval_family": "judgment_eval", "mandatory_for_progression": True},
                {"eval_id": "policy_eval", "eval_family": "judgment_eval", "mandatory_for_progression": True},
            ],
        }
    ],
}


def _good_result(eval_id: str) -> dict:
    return {
        "eval_id": eval_id,
        "passed": True,
        "result_status": "pass",
        "score": 1.0,
        "trace_id": "trace-nx-1",
    }


def test_required_eval_lookup_returns_required_set() -> None:
    ids = required_eval_lookup(artifact_family="nx_test_family", registry=_REGISTRY)
    assert set(ids) == {"schema_eval", "evidence_eval", "policy_eval"}


def test_required_eval_lookup_unknown_family_blocks() -> None:
    with pytest.raises(EvalSpineError, match="missing required eval mapping"):
        required_eval_lookup(artifact_family="unknown_family", registry=_REGISTRY)


def test_required_eval_lookup_rejects_empty_family() -> None:
    with pytest.raises(EvalSpineError):
        required_eval_lookup(artifact_family="", registry=_REGISTRY)


def test_normalize_indeterminate_preserves_status() -> None:
    raw = {"eval_id": "x", "passed": None, "result_status": "indeterminate"}
    out = normalize_eval_result(raw)
    assert out["result_status"] == "indeterminate"
    assert out["passed"] is False


def test_normalize_invalid_status_blocks() -> None:
    with pytest.raises(EvalSpineError, match="invalid result_status"):
        normalize_eval_result({"eval_id": "x", "result_status": "maybe"})


def test_normalize_missing_eval_id_blocks() -> None:
    with pytest.raises(EvalSpineError, match="missing eval_id"):
        normalize_eval_result({"passed": True})


def test_normalize_failure_reason_canonical_aliases() -> None:
    assert normalize_failure_reason("missing_definition") == "missing_required_eval_definition"
    assert normalize_failure_reason("failed_required_eval") == "required_eval_failed"
    assert normalize_failure_reason("indeterminate_result") == "indeterminate_required_eval"


def test_normalize_failure_reason_heuristic_categories() -> None:
    assert normalize_failure_reason("eval missing definition") == "missing_required_eval_definition"
    assert normalize_failure_reason("policy mismatch detected") == "policy_mismatch"
    assert normalize_failure_reason("schema validation failed for foo") == "schema_validation_failed"
    assert normalize_failure_reason("evidence weak coverage") == "weak_evidence_coverage"
    assert normalize_failure_reason("contradiction in evidence") == "contradiction_signal"


def test_normalize_failure_reason_unknown_fails_closed_to_required_eval_failed() -> None:
    assert normalize_failure_reason("frobnicated something") == "required_eval_failed"


def test_eval_to_control_signal_block_requires_blocking_reason() -> None:
    out = eval_to_control_signal(
        {
            "decision": "block",
            "reason_code": "required_eval_failed",
            "blocking_reasons": ["x missing"],
            "trace": {"trace_id": "t1", "run_id": "r1"},
        }
    )
    assert out["decision"] == "block"
    assert out["reason_code"] == "required_eval_failed"
    assert "x missing" in out["blocking_reasons"]
    assert out["trace_id"] == "t1"
    assert out["run_id"] == "r1"


def test_eval_to_control_signal_block_synthesizes_reason_when_empty() -> None:
    out = eval_to_control_signal({"decision": "block", "reason_code": "required_eval_failed"})
    assert out["blocking_reasons"], "block decision must carry a blocking reason"


def test_eval_to_control_signal_unsupported_decision_blocks() -> None:
    with pytest.raises(EvalSpineError):
        eval_to_control_signal({"decision": "maybe"})


def test_eval_to_control_signal_accepts_complete_as_allow() -> None:
    out = eval_to_control_signal({"coverage_status": "complete", "block_reason": "none"})
    assert out["decision"] == "allow"
    assert out["reason_code"] == "none"


# ---- NX-05: Red-team eval blind-spot fixtures ----


def test_red_team_missing_required_eval_blocks() -> None:
    """A required eval that is missing from results must block."""
    result = evaluate_artifact_family(
        artifact_family="nx_test_family",
        eval_definitions=["schema_eval", "evidence_eval", "policy_eval"],
        eval_results=[
            _good_result("schema_eval"),
            _good_result("evidence_eval"),
            # policy_eval missing
        ],
        trace_id="trace-nx-2",
        run_id="run-nx-2",
        created_at="2026-04-27T00:00:00Z",
        registry=_REGISTRY,
    )
    assert result["control_handoff"]["decision"] == "block"
    assert result["control_handoff"]["reason_code"] == "missing_required_eval_result"


def test_red_team_indeterminate_required_eval_freezes() -> None:
    """An indeterminate required eval must freeze (not allow)."""
    result = evaluate_artifact_family(
        artifact_family="nx_test_family",
        eval_definitions=["schema_eval", "evidence_eval", "policy_eval"],
        eval_results=[
            _good_result("schema_eval"),
            _good_result("evidence_eval"),
            {"eval_id": "policy_eval", "passed": None, "result_status": "indeterminate"},
        ],
        trace_id="trace-nx-3",
        run_id="run-nx-3",
        created_at="2026-04-27T00:00:00Z",
        registry=_REGISTRY,
    )
    assert result["control_handoff"]["decision"] == "freeze"
    assert result["control_handoff"]["reason_code"] == "indeterminate_required_eval"


def test_red_team_failed_schema_eval_blocks() -> None:
    """A failing schema eval must block with required_eval_failed."""
    result = evaluate_artifact_family(
        artifact_family="nx_test_family",
        eval_definitions=["schema_eval", "evidence_eval", "policy_eval"],
        eval_results=[
            {
                "eval_id": "schema_eval",
                "passed": False,
                "result_status": "fail",
                "failure_reason": "schema_validation_failed",
            },
            _good_result("evidence_eval"),
            _good_result("policy_eval"),
        ],
        trace_id="trace-nx-4",
        run_id="run-nx-4",
        created_at="2026-04-27T00:00:00Z",
        registry=_REGISTRY,
    )
    assert result["control_handoff"]["decision"] == "block"


def test_red_team_unknown_artifact_family_blocks() -> None:
    """An unknown artifact family must block with missing_required_eval_mapping."""
    result = evaluate_artifact_family(
        artifact_family="ghost_family",
        eval_definitions=["schema_eval"],
        eval_results=[_good_result("schema_eval")],
        trace_id="trace-nx-5",
        run_id="run-nx-5",
        created_at="2026-04-27T00:00:00Z",
        registry=_REGISTRY,
    )
    assert result["control_handoff"]["decision"] == "block"
    assert result["control_handoff"]["reason_code"] == "missing_required_eval_mapping"


def test_red_team_missing_definition_blocks() -> None:
    """If a required eval is declared but no definition exists, block."""
    result = evaluate_artifact_family(
        artifact_family="nx_test_family",
        eval_definitions=["schema_eval", "evidence_eval"],  # policy_eval undeclared
        eval_results=[
            _good_result("schema_eval"),
            _good_result("evidence_eval"),
            _good_result("policy_eval"),
        ],
        trace_id="trace-nx-6",
        run_id="run-nx-6",
        created_at="2026-04-27T00:00:00Z",
        registry=_REGISTRY,
    )
    assert result["control_handoff"]["decision"] == "block"
    assert result["control_handoff"]["reason_code"] == "missing_required_eval_definition"


def test_red_team_all_passing_allows() -> None:
    """Sanity: with all required evals passing, the spine produces allow."""
    result = evaluate_artifact_family(
        artifact_family="nx_test_family",
        eval_definitions=["schema_eval", "evidence_eval", "policy_eval"],
        eval_results=[
            _good_result("schema_eval"),
            _good_result("evidence_eval"),
            _good_result("policy_eval"),
        ],
        trace_id="trace-nx-7",
        run_id="run-nx-7",
        created_at="2026-04-27T00:00:00Z",
        registry=_REGISTRY,
    )
    assert result["control_handoff"]["decision"] == "allow"
    assert result["control_handoff"]["reason_code"] == "none"


def test_build_eval_summary_blocks_when_missing() -> None:
    """The eval summary must mark slice 'blocked' when required IDs are missing."""
    summary = build_eval_summary(
        trace_id="trace-nx-8",
        artifact_family="nx_test_family",
        stage="post_pqx",
        required_eval_ids=["schema_eval", "policy_eval"],
        observed_eval_ids=["schema_eval"],
    )
    assert summary["status"] == "blocked"
    assert summary["fail_count"] == 1


def test_build_eval_summary_healthy_when_complete() -> None:
    summary = build_eval_summary(
        trace_id="trace-nx-9",
        artifact_family="nx_test_family",
        stage="post_pqx",
        required_eval_ids=["schema_eval"],
        observed_eval_ids=["schema_eval"],
    )
    assert summary["status"] == "healthy"
    assert summary["fail_count"] == 0


def test_build_eval_summary_rejects_blank_inputs() -> None:
    with pytest.raises(EvalSpineError):
        build_eval_summary(
            trace_id="",
            artifact_family="nx_test_family",
            stage="post_pqx",
            required_eval_ids=[],
            observed_eval_ids=[],
        )
