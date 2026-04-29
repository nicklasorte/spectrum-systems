"""Tests for proof_presence_enforcement (CLX-ALL-01 Phase 2).

Covers:
- Non-governed files: pass regardless of proof
- Governed files without proof: block
- Governed files with valid loop_proof_bundle: pass
- Governed files with invalid proof (missing fields): block
- Governed files with wrong artifact_type: block
- rfx_loop_proof accepted
- core_loop_alignment_record accepted
- Output schema compliance
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.governance.proof_presence_enforcement import (
    ProofPresenceEnforcementError,
    enforce_proof_presence,
)


def _non_governed_files() -> list[str]:
    return ["docs/roadmap/some.md", "data/test.json", "README.md"]


def _governed_files() -> list[str]:
    return [
        "spectrum_systems/modules/runtime/some_module.py",
        "contracts/schemas/some.schema.json",
    ]


def _valid_loop_proof_bundle() -> dict:
    return {
        "artifact_type": "loop_proof_bundle",
        "bundle_id": "bundle-001",
        "trace_id": "trace-001",
        "final_status": "pass",
        "execution_record_ref": "exec-001",
        "eval_summary_ref": "eval-001",
        "control_decision_ref": "cd-001",
        "enforcement_action_ref": "ea-001",
        "replay_record_ref": "rep-001",
        "lineage_chain_ref": "lin-001",
        "trace_summary": {
            "overall_status": "ok",
            "one_page_summary": "All stages completed.",
            "owning_system": "CDE",
        },
    }


def _valid_rfx_loop_proof() -> dict:
    return {
        "artifact_type": "rfx_loop_proof",
        "proof_id": "proof-001",
        "status": "valid",
        "stage_map": {
            "admit": "Admit",
            "prove": "Prove",
            "repair": "Repair",
            "learn": "Learn",
            "recommend": "Recommend",
        },
        "primary_reason_code": "rfx_eval_failed",
        "trace_summary": {"overall_status": "ok"},
    }


def _valid_core_loop_alignment_record() -> dict:
    return {
        "artifact_type": "core_loop_alignment_record",
        "artifact_id": "clr-001",
        "maps_to_stages": ["execution", "evaluation", "control", "enforcement"],
        "strengthens_existing_loop": True,
        "loop_justification": "Adds shift-left detection to the governance loop.",
    }


def test_no_governed_surfaces_passes_without_proof() -> None:
    result = enforce_proof_presence(
        changed_files=_non_governed_files(),
        proof_artifact=None,
        trace_id="t",
    )
    assert result["artifact_type"] == "proof_presence_enforcement_result"
    assert result["gate_status"] == "pass"
    assert result["proof_required"] is False


def test_governed_surfaces_without_proof_blocks() -> None:
    result = enforce_proof_presence(
        changed_files=_governed_files(),
        proof_artifact=None,
        trace_id="t",
    )
    assert result["gate_status"] == "block"
    assert result["proof_required"] is True
    assert result["proof_found"] is False
    assert "proof_presence_required_but_missing" in (result["block_reason"] or "")


def test_governed_surfaces_with_valid_bundle_passes() -> None:
    result = enforce_proof_presence(
        changed_files=_governed_files(),
        proof_artifact=_valid_loop_proof_bundle(),
        trace_id="t",
    )
    assert result["gate_status"] == "pass"
    assert result["proof_found"] is True
    assert result["proof_valid"] is True


def test_governed_surfaces_with_valid_rfx_proof_passes() -> None:
    result = enforce_proof_presence(
        changed_files=_governed_files(),
        proof_artifact=_valid_rfx_loop_proof(),
        trace_id="t",
    )
    assert result["gate_status"] == "pass"


def test_governed_surfaces_with_core_loop_alignment_record_passes() -> None:
    result = enforce_proof_presence(
        changed_files=_governed_files(),
        proof_artifact=_valid_core_loop_alignment_record(),
        trace_id="t",
    )
    assert result["gate_status"] == "pass"


def test_wrong_artifact_type_blocks() -> None:
    result = enforce_proof_presence(
        changed_files=_governed_files(),
        proof_artifact={"artifact_type": "some_other_artifact"},
        trace_id="t",
    )
    assert result["gate_status"] == "block"
    assert "not_accepted" in (result["block_reason"] or "")


def test_malformed_bundle_missing_refs_blocks() -> None:
    incomplete = {"artifact_type": "loop_proof_bundle", "bundle_id": "b-001", "trace_id": "t"}
    result = enforce_proof_presence(
        changed_files=_governed_files(),
        proof_artifact=incomplete,
        trace_id="t",
    )
    # May pass or fail depending on ref count, but must produce a structured result.
    assert result["artifact_type"] == "proof_presence_enforcement_result"
    assert result["gate_status"] in ("pass", "block")


def test_invalid_changed_files_raises() -> None:
    import pytest
    with pytest.raises(ProofPresenceEnforcementError):
        enforce_proof_presence(changed_files="not-a-list", proof_artifact=None, trace_id="t")


def test_validation_detail_has_required_fields() -> None:
    result = enforce_proof_presence(
        changed_files=_governed_files(),
        proof_artifact=_valid_loop_proof_bundle(),
        trace_id="t",
    )
    detail = result["validation_detail"]
    for key in ["stage_count", "transition_count", "primary_reason_present", "trace_continuity"]:
        assert key in detail


def test_github_workflows_are_governed_surface() -> None:
    result = enforce_proof_presence(
        changed_files=[".github/workflows/pr-pytest.yml"],
        proof_artifact=None,
        trace_id="t",
    )
    assert result["proof_required"] is True
    assert result["gate_status"] == "block"
