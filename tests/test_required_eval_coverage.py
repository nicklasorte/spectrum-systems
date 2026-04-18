from __future__ import annotations

from spectrum_systems.modules.runtime.required_eval_coverage import (
    enforce_required_eval_coverage,
    load_required_eval_registry,
)


def _registry() -> dict:
    return load_required_eval_registry()


def _enf01_eval_results(
    *,
    include_complexity: bool = True,
    include_loop: bool = True,
    include_debug: bool = True,
    parallel_loop: bool = False,
    loop_mapping_indeterminate: bool = False,
    missing_trace: bool = False,
    unclear_debug_expectation: bool = False,
    duplicate_of_system: str | None = None,
    duplicate_status: str = "approved",
) -> list[dict]:
    evals: list[dict] = []
    if include_complexity:
        evals.append(
            {
                "eval_id": "complexity_justification_valid",
                "passed": True,
                "complexity_justification_record": {
                    "failure_prevented": "silent progression without failure prevention evidence",
                    "signal_improved": "required_eval_precondition_coverage_rate",
                    "measurable_metric": "required_eval_precondition_coverage_rate",
                    "why_not_existing_owner": "No existing owner artifact captures explicit complexity precondition evidence for this surface.",
                    "duplicate_of_system": duplicate_of_system,
                    "justification_status": duplicate_status,
                },
            }
        )
    if include_loop:
        evals.append(
            {
                "eval_id": "core_loop_alignment_valid",
                "passed": True,
                "core_loop_alignment_record": {
                    "maps_to_stages": ["execution", "evaluation", "control", "enforcement"],
                    "strengthens_existing_loop": True,
                    "introduces_parallel_loop": parallel_loop,
                    "loop_impact_score": 0.84,
                    "loop_mapping_status": "indeterminate" if loop_mapping_indeterminate else "deterministic",
                },
            }
        )
    if include_debug:
        evals.append(
            {
                "eval_id": "debuggability_valid",
                "passed": True,
                "debuggability_record": {
                    "trace_complete": not missing_trace,
                    "lineage_complete": True,
                    "replay_expected": True,
                    "replay_supported": True,
                    "failure_modes_defined": ["missing_required_eval_artifact"],
                    "reason_codes_defined": True,
                    "debug_expectations_clear": not unclear_debug_expectation,
                },
            }
        )
    return evals


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


def test_enf01_missing_complexity_justification_blocks_progression() -> None:
    output = enforce_required_eval_coverage(
        artifact_family="system_change_governance",
        eval_definitions=["complexity_justification_valid", "core_loop_alignment_valid", "debuggability_valid"],
        eval_results=_enf01_eval_results(include_complexity=False),
        trace_id="trace-enf01",
        run_id="run-enf01",
        created_at="2026-04-18T00:00:00Z",
        registry=_registry(),
    )
    assert output["enforcement"]["decision"] == "block"
    assert output["enforcement"]["reason_code"] == "missing_required_eval_result"


def test_enf01_missing_loop_alignment_blocks_progression() -> None:
    output = enforce_required_eval_coverage(
        artifact_family="system_change_governance",
        eval_definitions=["complexity_justification_valid", "core_loop_alignment_valid", "debuggability_valid"],
        eval_results=_enf01_eval_results(include_loop=False),
        trace_id="trace-enf01",
        run_id="run-enf01",
        created_at="2026-04-18T00:00:00Z",
        registry=_registry(),
    )
    assert output["enforcement"]["decision"] == "block"
    assert output["enforcement"]["reason_code"] == "missing_required_eval_result"


def test_enf01_missing_debuggability_record_blocks_progression() -> None:
    output = enforce_required_eval_coverage(
        artifact_family="system_change_governance",
        eval_definitions=["complexity_justification_valid", "core_loop_alignment_valid", "debuggability_valid"],
        eval_results=_enf01_eval_results(include_debug=False),
        trace_id="trace-enf01",
        run_id="run-enf01",
        created_at="2026-04-18T00:00:00Z",
        registry=_registry(),
    )
    assert output["enforcement"]["decision"] == "block"
    assert output["enforcement"]["reason_code"] == "missing_required_eval_result"


def test_enf01_parallel_loop_introduction_blocks_progression() -> None:
    output = enforce_required_eval_coverage(
        artifact_family="system_change_governance",
        eval_definitions=["complexity_justification_valid", "core_loop_alignment_valid", "debuggability_valid"],
        eval_results=_enf01_eval_results(parallel_loop=True),
        trace_id="trace-enf01",
        run_id="run-enf01",
        created_at="2026-04-18T00:00:00Z",
        registry=_registry(),
    )
    assert output["enforcement"]["decision"] == "block"
    assert output["enforcement"]["reason_code"] == "required_eval_failed"


def test_enf01_indeterminate_loop_mapping_freezes_progression() -> None:
    output = enforce_required_eval_coverage(
        artifact_family="system_change_governance",
        eval_definitions=["complexity_justification_valid", "core_loop_alignment_valid", "debuggability_valid"],
        eval_results=_enf01_eval_results(loop_mapping_indeterminate=True),
        trace_id="trace-enf01",
        run_id="run-enf01",
        created_at="2026-04-18T00:00:00Z",
        registry=_registry(),
    )
    assert output["enforcement"]["decision"] == "freeze"
    assert output["enforcement"]["reason_code"] == "indeterminate_required_eval"


def test_enf01_missing_trace_lineage_replay_reason_codes_blocks_or_freezes() -> None:
    eval_results = _enf01_eval_results(missing_trace=True)
    eval_results[2]["debuggability_record"]["lineage_complete"] = False
    eval_results[2]["debuggability_record"]["replay_supported"] = None
    eval_results[2]["debuggability_record"]["reason_codes_defined"] = False

    output = enforce_required_eval_coverage(
        artifact_family="system_change_governance",
        eval_definitions=["complexity_justification_valid", "core_loop_alignment_valid", "debuggability_valid"],
        eval_results=eval_results,
        trace_id="trace-enf01",
        run_id="run-enf01",
        created_at="2026-04-18T00:00:00Z",
        registry=_registry(),
    )
    assert output["enforcement"]["decision"] in {"block", "freeze"}
    assert output["enforcement"]["decision"] == "block"


def test_enf01_unclear_debug_expectations_freezes_progression() -> None:
    output = enforce_required_eval_coverage(
        artifact_family="system_change_governance",
        eval_definitions=["complexity_justification_valid", "core_loop_alignment_valid", "debuggability_valid"],
        eval_results=_enf01_eval_results(unclear_debug_expectation=True),
        trace_id="trace-enf01",
        run_id="run-enf01",
        created_at="2026-04-18T00:00:00Z",
        registry=_registry(),
    )
    assert output["enforcement"]["decision"] == "freeze"
    assert output["enforcement"]["reason_code"] == "indeterminate_required_eval"


def test_enf01_duplicate_system_signal_blocks_progression() -> None:
    output = enforce_required_eval_coverage(
        artifact_family="system_change_governance",
        eval_definitions=["complexity_justification_valid", "core_loop_alignment_valid", "debuggability_valid"],
        eval_results=_enf01_eval_results(duplicate_of_system="existing_runtime_system", duplicate_status="approved"),
        trace_id="trace-enf01",
        run_id="run-enf01",
        created_at="2026-04-18T00:00:00Z",
        registry=_registry(),
    )
    assert output["enforcement"]["decision"] == "block"
    assert any("duplicate ownership signal" in reason for reason in output["enforcement"]["blocking_reasons"])


def test_enf01_all_required_artifacts_and_evals_allow_progression() -> None:
    output = enforce_required_eval_coverage(
        artifact_family="system_change_governance",
        eval_definitions=["complexity_justification_valid", "core_loop_alignment_valid", "debuggability_valid"],
        eval_results=_enf01_eval_results(),
        trace_id="trace-enf01",
        run_id="run-enf01",
        created_at="2026-04-18T00:00:00Z",
        registry=_registry(),
    )
    assert output["enforcement"]["decision"] == "allow"
    assert output["enforcement"]["reason_code"] == "none"
