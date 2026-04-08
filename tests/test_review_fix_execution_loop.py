from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.review_fix_execution_loop import (
    ReviewFixExecutionLoopError,
    run_review_fix_execution_cycle,
)
from spectrum_systems.modules.runtime.pqx_execution_policy import evaluate_pqx_execution_policy
from spectrum_systems.modules.runtime.pqx_required_context_enforcement import enforce_pqx_required_context


def _prepare_post_fix_review_inputs(repo_root: Path, *, validation_status: str = "passed") -> None:
    target = repo_root / "spectrum_systems/modules/review_queue_executor.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# stub\n", encoding="utf-8")

    output = repo_root / "artifacts/pqx_runs/run-001/output.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"status": "complete"}), encoding="utf-8")

    validation = repo_root / "artifacts/pqx_runs/run-001/test_results.json"
    validation.write_text(json.dumps({"status": validation_status}), encoding="utf-8")


def test_review_fix_execution_contract_examples_validate() -> None:
    for artifact_type in (
        "review_fix_execution_request_artifact",
        "review_fix_execution_result_artifact",
    ):
        validate_artifact(load_example(artifact_type), artifact_type)


def test_happy_path_executes_once_and_reruns_review_once(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _prepare_post_fix_review_inputs(repo_root, validation_status="passed")

    request = copy.deepcopy(load_example("review_fix_execution_request_artifact"))
    pqx_calls: list[str] = []

    def _pqx_executor(_: dict) -> dict:
        pqx_calls.append("called")
        return {"status": "complete", "execution_ref": "exec:run-001:AI-01:1"}

    result = run_review_fix_execution_cycle(
        request,
        output_dir=repo_root / "artifacts/reviews",
        repo_root=repo_root,
        review_docs_dir=repo_root / "docs/reviews",
        pqx_executor=_pqx_executor,
    )

    artifact = result["review_fix_execution_result_artifact"]
    assert len(pqx_calls) == 1
    assert artifact["status"] == "completed_safe_to_merge"
    assert artifact["loop_cycle_count"] == 1
    assert artifact["post_fix_review"]["attempted"] is True
    assert artifact["post_fix_review"]["verdict"] == "safe_to_merge"


def test_tpa_block_prevents_pqx_execution(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _prepare_post_fix_review_inputs(repo_root)
    request = copy.deepcopy(load_example("review_fix_execution_request_artifact"))
    request["tpa_slice_artifact"]["artifact"]["promotion_ready"] = False

    pqx_called = False

    def _pqx_executor(_: dict) -> dict:
        nonlocal pqx_called
        pqx_called = True
        return {"status": "complete"}

    result = run_review_fix_execution_cycle(
        request,
        output_dir=repo_root / "artifacts/reviews",
        repo_root=repo_root,
        review_docs_dir=repo_root / "docs/reviews",
        pqx_executor=_pqx_executor,
    )

    artifact = result["review_fix_execution_result_artifact"]
    assert artifact["status"] == "blocked_by_tpa"
    assert pqx_called is False


def test_tpa_missing_or_malformed_fails_closed(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _prepare_post_fix_review_inputs(repo_root)
    request = copy.deepcopy(load_example("review_fix_execution_request_artifact"))
    request["tpa_slice_artifact"].pop("phase")

    with pytest.raises(ReviewFixExecutionLoopError):
        run_review_fix_execution_cycle(
            request,
            output_dir=repo_root / "artifacts/reviews",
            repo_root=repo_root,
            review_docs_dir=repo_root / "docs/reviews",
            pqx_executor=lambda _: {"status": "complete"},
        )


def test_raw_prompt_bypass_is_rejected(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _prepare_post_fix_review_inputs(repo_root)
    request = copy.deepcopy(load_example("review_fix_execution_request_artifact"))
    request["raw_prompt_text"] = "execute this markdown"

    with pytest.raises(ReviewFixExecutionLoopError, match="raw prompt text"):
        run_review_fix_execution_cycle(
            request,
            output_dir=repo_root / "artifacts/reviews",
            repo_root=repo_root,
            review_docs_dir=repo_root / "docs/reviews",
            pqx_executor=lambda _: {"status": "complete"},
        )


def test_one_cycle_bound_stops_without_recursive_rerun(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _prepare_post_fix_review_inputs(repo_root, validation_status="failed")
    request = copy.deepcopy(load_example("review_fix_execution_request_artifact"))

    pqx_count = 0

    def _pqx_executor(_: dict) -> dict:
        nonlocal pqx_count
        pqx_count += 1
        return {"status": "complete", "execution_ref": "exec:run-001:AI-01:1"}

    result = run_review_fix_execution_cycle(
        request,
        output_dir=repo_root / "artifacts/reviews",
        repo_root=repo_root,
        review_docs_dir=repo_root / "docs/reviews",
        pqx_executor=_pqx_executor,
    )

    artifact = result["review_fix_execution_result_artifact"]
    assert pqx_count == 1
    assert artifact["status"] == "completed_fix_still_required"
    assert artifact["stopped"] is True


def test_safe_or_not_safe_paths_do_not_execute_when_no_fix_slice(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _prepare_post_fix_review_inputs(repo_root)
    request = copy.deepcopy(load_example("review_fix_execution_request_artifact"))
    request["fix_slices"] = []

    with pytest.raises(ReviewFixExecutionLoopError):
        run_review_fix_execution_cycle(
            request,
            output_dir=repo_root / "artifacts/reviews",
            repo_root=repo_root,
            review_docs_dir=repo_root / "docs/reviews",
            pqx_executor=lambda _: {"status": "complete"},
        )


def test_ss_hard_01_regression_governed_changes_require_pqx_context() -> None:
    decision = evaluate_pqx_execution_policy(
        changed_paths=["spectrum_systems/modules/review_fix_execution_loop.py"],
        execution_context="direct",
    )
    assert decision.status == "block"
    assert "GOVERNED_CHANGES_REQUIRE_PQX_CONTEXT" in decision.blocking_reasons


def test_ss_hard_02_regression_execution_mode_truth_enforced() -> None:
    wrapper = copy.deepcopy(load_example("codex_pqx_task_wrapper"))
    wrapper["execution_intent"]["mode"] = "exploration_only"
    wrapper["execution_intent"]["execution_context"] = "direct"
    wrapper["governance"]["pqx_required"] = True

    enforcement = enforce_pqx_required_context(
        classification="governed_pqx_required",
        changed_paths=["contracts/schemas/review_fix_execution_request_artifact.schema.json"],
        execution_context="direct",
        authority_evidence_ref=None,
        pqx_task_wrapper=wrapper,
    )
    assert enforcement.status == "block"
    assert "GOVERNED_REQUIRES_PQX_GOVERNED_CONTEXT" in enforcement.blocking_reasons
