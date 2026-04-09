from __future__ import annotations

import copy
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.review_fix_execution_loop import (
    ReviewFixExecutionLoopError,
    run_review_fix_execution_cycle,
)
from spectrum_systems.modules.runtime.lineage_authenticity import compute_payload_digest
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


def _attach_tpa_authenticity(request: dict, *, attestation: str | None = None) -> None:
    artifact = request["tpa_slice_artifact"]
    artifact["request_id"] = request["request_id"]
    payload_digest = compute_payload_digest(dict(artifact))
    issuer = "TPA"
    key_id = "tpa-hs256-v1"
    audience = "pqx_repo_write_boundary"
    scope = f"repo_write_lineage:tpa_slice_artifact:{request['request_id']}:{artifact['trace_id']}"
    now = datetime.now(timezone.utc).replace(microsecond=0)
    issued_at = now.isoformat().replace("+00:00", "Z")
    expires_at = (now + timedelta(minutes=15)).isoformat().replace("+00:00", "Z")
    lineage_token_id = "lin-1234567890abcdef12345678"
    secret = os.environ["SPECTRUM_LINEAGE_AUTH_SECRET_TPA"]
    computed_attestation = hmac.new(
        secret.encode("utf-8"),
        f"{issuer}|{key_id}|{payload_digest}|{audience}|{scope}|{issued_at}|{expires_at}|{lineage_token_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    artifact["authenticity"] = {
        "issuer": "TPA",
        "key_id": key_id,
        "payload_digest": payload_digest,
        "audience": audience,
        "scope": scope,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "lineage_token_id": lineage_token_id,
        "attestation": attestation or computed_attestation,
    }


def test_review_fix_execution_contract_examples_validate() -> None:
    for artifact_type in (
        "review_fix_execution_request_artifact",
        "review_fix_execution_result_artifact",
        "review_operator_handoff_artifact",
    ):
        validate_artifact(load_example(artifact_type), artifact_type)


def test_happy_path_executes_once_and_reruns_review_once(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _prepare_post_fix_review_inputs(repo_root, validation_status="passed")

    request = copy.deepcopy(load_example("review_fix_execution_request_artifact"))
    _attach_tpa_authenticity(request)
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
    assert artifact["operator_handoff_ref"] is None
    assert artifact["loop_cycle_count"] == 1
    assert artifact["post_fix_review"]["attempted"] is True
    assert artifact["post_fix_review"]["verdict"] == "safe_to_merge"
    assert "review_operator_handoff_artifact" not in result


def test_tpa_gate_rejects_forged_artifact(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _prepare_post_fix_review_inputs(repo_root, validation_status="passed")
    request = copy.deepcopy(load_example("review_fix_execution_request_artifact"))
    request["tpa_slice_artifact"].pop("authenticity", None)
    with pytest.raises(ReviewFixExecutionLoopError, match="authenticity invalid"):
        run_review_fix_execution_cycle(
            request,
            output_dir=repo_root / "artifacts/reviews",
            repo_root=repo_root,
            review_docs_dir=repo_root / "docs/reviews",
            pqx_executor=lambda _: {"status": "complete"},
        )


def test_tpa_gate_rejects_fake_signature(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _prepare_post_fix_review_inputs(repo_root, validation_status="passed")
    request = copy.deepcopy(load_example("review_fix_execution_request_artifact"))
    _attach_tpa_authenticity(request, attestation="0" * 64)
    with pytest.raises(ReviewFixExecutionLoopError, match="authenticity invalid"):
        run_review_fix_execution_cycle(
            request,
            output_dir=repo_root / "artifacts/reviews",
            repo_root=repo_root,
            review_docs_dir=repo_root / "docs/reviews",
            pqx_executor=lambda _: {"status": "complete"},
        )


def test_tpa_gate_accepts_valid_tpa_artifact(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _prepare_post_fix_review_inputs(repo_root, validation_status="passed")
    request = copy.deepcopy(load_example("review_fix_execution_request_artifact"))
    _attach_tpa_authenticity(request)
    result = run_review_fix_execution_cycle(
        request,
        output_dir=repo_root / "artifacts/reviews",
        repo_root=repo_root,
        review_docs_dir=repo_root / "docs/reviews",
        pqx_executor=lambda _: {"status": "complete", "execution_ref": "exec:run-001:AI-01:1"},
    )
    assert result["review_fix_execution_result_artifact"]["status"] == "completed_safe_to_merge"


def test_pqx_fix_execution_rejects_forged_tpa_gate(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _prepare_post_fix_review_inputs(repo_root, validation_status="passed")
    request = copy.deepcopy(load_example("review_fix_execution_request_artifact"))
    _attach_tpa_authenticity(request)
    request["request_id"] = "forged-request-id"
    with pytest.raises(ReviewFixExecutionLoopError, match="request binding mismatch"):
        run_review_fix_execution_cycle(
            request,
            output_dir=repo_root / "artifacts/reviews",
            repo_root=repo_root,
            review_docs_dir=repo_root / "docs/reviews",
            pqx_executor=lambda _: {"status": "complete"},
        )


def test_fix_reentry_triggers_review(tmp_path: Path) -> None:
    test_happy_path_executes_once_and_reruns_review_once(tmp_path)


def test_tpa_block_prevents_pqx_execution(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _prepare_post_fix_review_inputs(repo_root)
    request = copy.deepcopy(load_example("review_fix_execution_request_artifact"))
    request["tpa_slice_artifact"]["artifact"]["promotion_ready"] = False
    _attach_tpa_authenticity(request)

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
    assert artifact["operator_handoff_ref"] is not None
    handoff = result["review_operator_handoff_artifact"]
    assert handoff["handoff_reason"] == "tpa_blocked"
    assert handoff["recommended_next_action"] == "manual_review_required"
    assert result["review_handoff_disposition_artifact"]["provenance"]["classified_by_system"] == "TLC"
    assert result["review_handoff_disposition_artifact"]["provenance"]["execution_triggered"] is False
    validate_artifact(handoff, "review_operator_handoff_artifact")


def test_tpa_missing_or_malformed_fails_closed(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _prepare_post_fix_review_inputs(repo_root)
    request = copy.deepcopy(load_example("review_fix_execution_request_artifact"))
    _attach_tpa_authenticity(request)
    request["tpa_slice_artifact"].pop("phase")

    with pytest.raises(ReviewFixExecutionLoopError):
        run_review_fix_execution_cycle(
            request,
            output_dir=repo_root / "artifacts/reviews",
            repo_root=repo_root,
            review_docs_dir=repo_root / "docs/reviews",
            pqx_executor=lambda _: {"status": "complete"},
        )


def test_rqx_never_calls_pqx_directly(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _prepare_post_fix_review_inputs(repo_root)
    request = copy.deepcopy(load_example("review_fix_execution_request_artifact"))
    request["tpa_slice_artifact"]["artifact"]["promotion_ready"] = False
    _attach_tpa_authenticity(request)
    called = False

    def _pqx_executor(_: dict) -> dict:
        nonlocal called
        called = True
        return {"status": "complete"}

    result = run_review_fix_execution_cycle(
        request,
        output_dir=repo_root / "artifacts/reviews",
        repo_root=repo_root,
        review_docs_dir=repo_root / "docs/reviews",
        pqx_executor=_pqx_executor,
    )
    assert called is False
    assert result["review_fix_execution_result_artifact"]["status"] == "blocked_by_tpa"


def test_rqx_never_executes_fixes(tmp_path: Path) -> None:
    test_rqx_never_calls_pqx_directly(tmp_path)


def test_pqx_rejects_non_tpa_fix_execution(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _prepare_post_fix_review_inputs(repo_root)
    request = copy.deepcopy(load_example("review_fix_execution_request_artifact"))
    _attach_tpa_authenticity(request)
    request["tpa_slice_artifact"]["artifact"]["review_signal_refs"] = []

    with pytest.raises(ReviewFixExecutionLoopError, match="tpa gate must bind"):
        run_review_fix_execution_cycle(
            request,
            output_dir=repo_root / "artifacts/reviews",
            repo_root=repo_root,
            review_docs_dir=repo_root / "docs/reviews",
            pqx_executor=lambda _: {"status": "complete"},
        )


def test_fix_requires_tpa_gate(tmp_path: Path) -> None:
    test_pqx_rejects_non_tpa_fix_execution(tmp_path)


def test_rqx_routes_fix_slice_to_tpa(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _prepare_post_fix_review_inputs(repo_root)
    request = copy.deepcopy(load_example("review_fix_execution_request_artifact"))
    _attach_tpa_authenticity(request)
    request["fix_slices"][0]["review_result_ref"] = "review_result_artifact:different-review"

    with pytest.raises(ReviewFixExecutionLoopError, match="must match source_review_result_ref"):
        run_review_fix_execution_cycle(
            request,
            output_dir=repo_root / "artifacts/reviews",
            repo_root=repo_root,
            review_docs_dir=repo_root / "docs/reviews",
            pqx_executor=lambda _: {"status": "complete"},
        )


def test_rqx_routes_fix_to_tpa(tmp_path: Path) -> None:
    test_rqx_routes_fix_slice_to_tpa(tmp_path)


def test_raw_prompt_bypass_is_rejected(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _prepare_post_fix_review_inputs(repo_root)
    request = copy.deepcopy(load_example("review_fix_execution_request_artifact"))
    _attach_tpa_authenticity(request)
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
    _attach_tpa_authenticity(request)

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
    handoff = result["review_operator_handoff_artifact"]
    assert handoff["post_cycle_verdict"] == "fix_required"
    assert handoff["handoff_reason"] == "post_cycle_fix_still_required"
    assert handoff["recommended_next_action"] == "schedule_follow_on_cycle"
    assert handoff["source_review_result_ref"] == artifact["post_fix_review"]["review_result_ref"]
    assert handoff["source_review_fix_execution_result_ref"] == (
        f"review_fix_execution_result_artifact:{artifact['result_id']}"
    )
    assert handoff["trace_linkage"]["request_ref"] == artifact["request_ref"]
    assert handoff["provenance"]["emitted_by_system"] == "RQX"
    assert handoff["provenance"]["auto_reentry_triggered"] is False
    validate_artifact(handoff, "review_operator_handoff_artifact")


def test_not_safe_to_merge_emits_operator_handoff(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _prepare_post_fix_review_inputs(repo_root, validation_status="passed")
    request = copy.deepcopy(load_example("review_fix_execution_request_artifact"))
    _attach_tpa_authenticity(request)
    request["post_fix_review_request_artifact"]["changed_files"].append("missing/file.py")

    result = run_review_fix_execution_cycle(
        request,
        output_dir=repo_root / "artifacts/reviews",
        repo_root=repo_root,
        review_docs_dir=repo_root / "docs/reviews",
        pqx_executor=lambda _: {"status": "complete", "execution_ref": "exec:run-001:AI-01:1"},
    )

    artifact = result["review_fix_execution_result_artifact"]
    assert artifact["status"] == "completed_not_safe_to_merge"
    handoff = result["review_operator_handoff_artifact"]
    assert handoff["post_cycle_verdict"] == "not_safe_to_merge"
    assert handoff["handoff_reason"] == "post_cycle_not_safe_to_merge"
    assert handoff["recommended_next_action"] == "escalate_to_owner"


def test_checkpoint_missing_emits_operator_handoff(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _prepare_post_fix_review_inputs(repo_root, validation_status="passed")
    request = copy.deepcopy(load_example("review_fix_execution_request_artifact"))
    _attach_tpa_authenticity(request)
    request["checkpoint_required"] = True
    request["checkpoint_ref"] = None

    result = run_review_fix_execution_cycle(
        request,
        output_dir=repo_root / "artifacts/reviews",
        repo_root=repo_root,
        review_docs_dir=repo_root / "docs/reviews",
        pqx_executor=lambda _: {"status": "complete", "execution_ref": "exec:run-001:AI-01:1"},
    )

    artifact = result["review_fix_execution_result_artifact"]
    handoff = result["review_operator_handoff_artifact"]
    assert artifact["status"] == "blocked_checkpoint_missing"
    assert handoff["handoff_reason"] == "checkpoint_required"
    assert handoff["recommended_next_action"] == "request_checkpoint_decision"


def test_handoff_emission_does_not_trigger_additional_execution(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _prepare_post_fix_review_inputs(repo_root, validation_status="failed")
    request = copy.deepcopy(load_example("review_fix_execution_request_artifact"))
    _attach_tpa_authenticity(request)
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

    assert pqx_count == 1
    assert result["review_fix_execution_result_artifact"]["status"] == "completed_fix_still_required"
    assert result["review_operator_handoff_artifact"]["provenance"]["auto_reentry_triggered"] is False
    assert result["review_handoff_disposition_artifact"]["provenance"]["execution_triggered"] is False
    assert result["review_handoff_disposition_artifact"]["provenance"]["rqx_cycle_reentry_triggered"] is False


def test_unresolved_stops_execution(tmp_path: Path) -> None:
    test_handoff_emission_does_not_trigger_additional_execution(tmp_path)


def test_safe_or_not_safe_paths_do_not_execute_when_no_fix_slice(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _prepare_post_fix_review_inputs(repo_root)
    request = copy.deepcopy(load_example("review_fix_execution_request_artifact"))
    _attach_tpa_authenticity(request)
    request["fix_slices"] = []

    with pytest.raises(ReviewFixExecutionLoopError):
        run_review_fix_execution_cycle(
            request,
            output_dir=repo_root / "artifacts/reviews",
            repo_root=repo_root,
            review_docs_dir=repo_root / "docs/reviews",
            pqx_executor=lambda _: {"status": "complete"},
        )


def test_run_review_fix_execution_cycle_rejects_forged_tpa_gate(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _prepare_post_fix_review_inputs(repo_root)
    request = copy.deepcopy(load_example("review_fix_execution_request_artifact"))
    _attach_tpa_authenticity(request)
    request["tpa_slice_artifact"]["artifact"]["promotion_ready"] = False

    with pytest.raises(ReviewFixExecutionLoopError, match="authenticity invalid"):
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
