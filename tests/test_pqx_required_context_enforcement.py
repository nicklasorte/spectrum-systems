from __future__ import annotations

from spectrum_systems.modules.runtime.pqx_required_context_enforcement import enforce_pqx_required_context


def _governed_wrapper() -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "artifact_type": "codex_pqx_task_wrapper",
        "wrapper_id": "wrap-1",
        "task_identity": {
            "task_id": "task-1",
            "run_id": "run-1",
            "step_id": "AI-01",
            "step_name": "Do governed work",
        },
        "task_source": {"source_type": "codex_prompt", "prompt": "run"},
        "execution_intent": {"execution_context": "pqx_governed", "mode": "governed"},
        "governance": {
            "classification": "governed_pqx_required",
            "pqx_required": True,
            "authority_state": "authoritative_governed_pqx",
            "authority_resolution": "explicit_pqx_context",
            "authority_evidence_ref": "data/pqx_runs/AI-01/run-1.pqx_slice_execution_record.json",
            "contract_preflight_result_artifact_path": "outputs/contract_preflight/contract_preflight_result_artifact.json",
        },
        "changed_paths": ["contracts/schemas/roadmap_eligibility_artifact.schema.json"],
        "metadata": {
            "requested_at": "2026-04-02T00:00:00Z",
            "dependencies": [],
            "policy_version": "1.0.0",
            "authority_notes": None,
        },
        "pqx_execution_request": {
            "schema_version": "1.1.0",
            "run_id": "run-1",
            "step_id": "AI-01",
            "step_name": "Do governed work",
            "dependencies": [],
            "requested_at": "2026-04-02T00:00:00Z",
            "prompt": "run",
            "roadmap_version": "docs/roadmaps/system_roadmap.md",
            "row_snapshot": {
                "row_index": 0,
                "step_id": "AI-01",
                "step_name": "Do governed work",
                "dependencies": [],
                "status": "ready",
            },
        },
    }


def test_governed_wrapped_task_with_valid_context_allows() -> None:
    result = enforce_pqx_required_context(
        classification="governed_pqx_required",
        execution_context="pqx_governed",
        changed_paths=["contracts/schemas/roadmap_eligibility_artifact.schema.json"],
        pqx_task_wrapper=_governed_wrapper(),
    ).to_dict()
    assert result["status"] == "allow"
    assert result["wrapper_present"] is True
    assert result["wrapper_context_valid"] is True
    assert result["authority_context_valid"] is True
    assert result["authority_state"] == "authoritative_governed_pqx"
    assert result["requires_pqx_execution"] is True
    assert result["enforcement_decision"] == "allow"


def test_governed_missing_wrapper_blocks_fail_closed() -> None:
    result = enforce_pqx_required_context(
        classification="governed_pqx_required",
        execution_context="pqx_governed",
        changed_paths=["contracts/schemas/roadmap_eligibility_artifact.schema.json"],
        authority_evidence_ref="data/pqx_runs/AI-01/run-1.pqx_slice_execution_record.json",
    ).to_dict()
    assert result["status"] == "block"
    assert "GOVERNED_REQUIRES_PQX_TASK_WRAPPER" in result["blocking_reasons"]


def test_governed_malformed_authority_ref_blocks() -> None:
    result = enforce_pqx_required_context(
        classification="governed_pqx_required",
        execution_context="pqx_governed",
        changed_paths=["contracts/schemas/roadmap_eligibility_artifact.schema.json"],
        pqx_task_wrapper=_governed_wrapper(),
        authority_evidence_ref="outputs/not-a-record.json",
    ).to_dict()
    assert result["status"] == "block"
    assert "MALFORMED_OR_MISSING_GOVERNED_AUTHORITY_EVIDENCE_REF" in result["blocking_reasons"]


def test_governed_contradictory_posture_blocks() -> None:
    result = enforce_pqx_required_context(
        classification="governed_pqx_required",
        execution_context="direct",
        changed_paths=["contracts/schemas/roadmap_eligibility_artifact.schema.json"],
        pqx_task_wrapper=_governed_wrapper(),
    ).to_dict()
    assert result["status"] == "block"
    assert "GOVERNED_REQUIRES_PQX_GOVERNED_CONTEXT" in result["blocking_reasons"]


def test_exploration_only_non_authoritative_without_wrapper_allowed() -> None:
    result = enforce_pqx_required_context(
        classification="exploration_only_or_non_governed",
        execution_context="exploration",
        changed_paths=["docs/vision.md"],
    ).to_dict()
    assert result["status"] == "allow"
    assert result["wrapper_present"] is False
    assert result["authority_context_valid"] is True
    assert result["requires_pqx_execution"] is False


def test_governed_commit_range_without_context_allows_pending_execution() -> None:
    result = enforce_pqx_required_context(
        classification="governed_pqx_required",
        execution_context="unspecified",
        changed_paths=["contracts/schemas/roadmap_eligibility_artifact.schema.json"],
        preflight_mode="commit_range_inspection",
    ).to_dict()
    assert result["status"] == "allow"
    assert result["authority_state"] == "unknown_pending_execution"
    assert result["requires_pqx_execution"] is True
    assert result["blocking_reasons"] == []


def test_governed_commit_range_with_explicit_direct_context_blocks() -> None:
    result = enforce_pqx_required_context(
        classification="governed_pqx_required",
        execution_context="direct",
        changed_paths=["contracts/schemas/roadmap_eligibility_artifact.schema.json"],
        preflight_mode="commit_range_inspection",
    ).to_dict()
    assert result["status"] == "block"
    assert "GOVERNED_REQUIRES_PQX_GOVERNED_CONTEXT" in result["blocking_reasons"]
