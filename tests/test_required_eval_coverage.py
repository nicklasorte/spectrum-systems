from __future__ import annotations

from spectrum_systems.modules.runtime.required_eval_coverage import (
    enforce_required_eval_coverage,
    load_required_eval_registry,
)


def _registry() -> dict:
    return load_required_eval_registry()


def test_required_eval_registry_loads_deterministically() -> None:
    first = _registry()
    second = _registry()
    assert first == second


def test_undeclared_artifact_family_blocks() -> None:
    output = enforce_required_eval_coverage(
        artifact_family="unknown_family",
        eval_definitions=["evidence_coverage"],
        eval_results=[{"eval_type": "evidence_coverage", "passed": True}],
        trace_id="trace-1",
        run_id="run-1",
        created_at="2026-04-04T00:00:00Z",
        registry=_registry(),
    )
    assert output["enforcement"]["decision"] == "block"
    assert output["enforcement"]["reason_code"] == "missing_required_eval_mapping"


def test_missing_required_eval_definition_blocks() -> None:
    output = enforce_required_eval_coverage(
        artifact_family="artifact_release_readiness",
        eval_definitions=["evidence_coverage", "policy_alignment"],
        eval_results=[
            {"eval_type": "evidence_coverage", "passed": True},
            {"eval_type": "policy_alignment", "passed": True},
        ],
        trace_id="trace-1",
        run_id="run-1",
        created_at="2026-04-04T00:00:00Z",
        registry=_registry(),
    )
    assert output["enforcement"]["decision"] == "block"
    assert output["enforcement"]["reason_code"] == "missing_required_eval_definition"


def test_missing_required_eval_result_blocks() -> None:
    output = enforce_required_eval_coverage(
        artifact_family="artifact_release_readiness",
        eval_definitions=["evidence_coverage", "policy_alignment", "replay_consistency"],
        eval_results=[
            {"eval_type": "evidence_coverage", "passed": True},
            {"eval_type": "policy_alignment", "passed": True},
        ],
        trace_id="trace-1",
        run_id="run-1",
        created_at="2026-04-04T00:00:00Z",
        registry=_registry(),
    )
    assert output["enforcement"]["decision"] == "block"
    assert output["enforcement"]["reason_code"] == "missing_required_eval_result"


def test_indeterminate_required_eval_freezes() -> None:
    output = enforce_required_eval_coverage(
        artifact_family="artifact_release_readiness",
        eval_definitions=["evidence_coverage", "policy_alignment", "replay_consistency"],
        eval_results=[
            {"eval_type": "evidence_coverage", "passed": True},
            {"eval_type": "policy_alignment", "passed": True},
            {"eval_type": "replay_consistency", "result_status": "indeterminate", "passed": None},
        ],
        trace_id="trace-1",
        run_id="run-1",
        created_at="2026-04-04T00:00:00Z",
        registry=_registry(),
    )
    assert output["enforcement"]["decision"] == "freeze"
    assert output["enforcement"]["reason_code"] == "indeterminate_required_eval"


def test_happy_path_allows_when_required_evals_present() -> None:
    output = enforce_required_eval_coverage(
        artifact_family="artifact_release_readiness",
        eval_definitions=["evidence_coverage", "policy_alignment", "replay_consistency"],
        eval_results=[
            {"eval_type": "evidence_coverage", "passed": True},
            {"eval_type": "policy_alignment", "passed": True},
            {"eval_type": "replay_consistency", "passed": True},
        ],
        trace_id="trace-1",
        run_id="run-1",
        created_at="2026-04-04T00:00:00Z",
        registry=_registry(),
    )
    assert output["enforcement"]["decision"] == "allow"
    assert output["coverage_registry"]["coverage_completeness_status"] == "complete"


def test_coverage_signal_is_deterministic() -> None:
    kwargs = {
        "artifact_family": "artifact_release_readiness",
        "eval_definitions": ["evidence_coverage", "policy_alignment", "replay_consistency"],
        "eval_results": [
            {"eval_type": "evidence_coverage", "passed": True},
            {"eval_type": "policy_alignment", "passed": True},
            {"eval_type": "replay_consistency", "passed": True},
        ],
        "trace_id": "trace-1",
        "run_id": "run-1",
        "created_at": "2026-04-04T00:00:00Z",
        "registry": _registry(),
    }
    first = enforce_required_eval_coverage(**kwargs)
    second = enforce_required_eval_coverage(**kwargs)
    assert first == second
