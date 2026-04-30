"""CLP-02 — Tests asserting AGL fail-closes on missing/blocking CLP evidence.

These tests exercise ``build_agent_core_loop_record`` with the new
``agent_pr_ready_result_ref`` parameter introduced by CLP-02. The AGL
record must:

- BLOCK when no CLP artifact is supplied for a repo-mutating slice
- BLOCK when CLP gate_status=block
- BLOCK when the agent_pr_ready_result is not_ready
- treat an invalid agent_pr_ready_result_ref the same as missing
"""

from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.agent_core_loop_proof import (
    build_agent_core_loop_record,
)
from spectrum_systems.modules.runtime.core_loop_pre_pr_gate import (
    REQUIRED_CHECK_NAMES,
    build_check,
    build_gate_result,
)
from spectrum_systems.modules.runtime.core_loop_pre_pr_gate_policy import (
    DEFAULT_POLICY_REL_PATH,
    build_agent_pr_ready_result,
    evaluate_pr_ready,
    load_policy,
)

ROOT = Path(__file__).resolve().parents[1]


def _write_clp(tmp_path: Path, *, gate_status: str = "pass") -> Path:
    if gate_status == "pass":
        checks = [
            build_check(
                check_name=name,
                command="echo ok",
                status="pass",
                output_ref=f"outputs/{name}.json",
            )
            for name in REQUIRED_CHECK_NAMES
        ]
    else:
        checks = [
            build_check(
                check_name=name,
                command="echo ok",
                status="pass",
                output_ref=f"outputs/{name}.json",
            )
            for name in REQUIRED_CHECK_NAMES
            if name != "authority_shape_preflight"
        ] + [
            build_check(
                check_name="authority_shape_preflight",
                command="echo blocking",
                status="block",
                output_ref="outputs/authority_shape_preflight.json",
                failure_class="authority_shape_violation",
                reason_codes=["authority_shape_review_language_lint"],
            )
        ]
    artifact = build_gate_result(
        work_item_id="W",
        agent_type="claude",
        repo_mutating=True,
        base_ref="origin/main",
        head_ref="HEAD",
        changed_files=["scripts/x.py"],
        checks=checks,
    )
    path = tmp_path / "clp.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")
    return path


def _write_pr_ready(tmp_path: Path, *, status: str, clp_path: Path) -> Path:
    policy = load_policy(ROOT / DEFAULT_POLICY_REL_PATH)
    if status == "ready":
        clp_payload = json.loads(clp_path.read_text(encoding="utf-8"))
        evaluation = evaluate_pr_ready(policy=policy, clp_result=clp_payload)
    elif status == "not_ready":
        evaluation = evaluate_pr_ready(
            policy=policy, clp_result=None, repo_mutating=True
        )
    else:
        evaluation = {
            "pr_ready_status": status,
            "reason_codes": ["custom_reason"],
            "required_follow_up": [],
            "clp_gate_status": None,
            "human_review_required": status == "human_review_required",
            "repo_mutating": True,
        }
    artifact = build_agent_pr_ready_result(
        work_item_id="W",
        agent_type="claude",
        policy_ref=DEFAULT_POLICY_REL_PATH,
        clp_result_ref=str(clp_path),
        evaluation=evaluation,
    )
    validate_artifact(artifact, "agent_pr_ready_result")
    path = tmp_path / "agent_pr_ready_result.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Missing/invalid evidence
# ---------------------------------------------------------------------------


def test_missing_clp_blocks_repo_mutating():
    rec = build_agent_core_loop_record(
        "CLP-02-AGL-NO-CLP",
        "claude",
        source_artifact=None,
        clp_evidence_artifact=None,
        agent_pr_ready_result_ref=None,
    )
    assert rec["compliance_status"] == "BLOCK"
    reason_codes = {a["reason_code"] for a in rec["learning_actions"]}
    assert "clp_evidence_missing" in reason_codes
    validate_artifact(rec, "agent_core_loop_run_record")


def test_clp_block_blocks_agl(tmp_path):
    clp = _write_clp(tmp_path, gate_status="block")
    rec = build_agent_core_loop_record(
        "CLP-02-AGL-CLP-BLOCK",
        "claude",
        source_artifact=None,
        clp_evidence_artifact=str(clp),
    )
    assert rec["compliance_status"] == "BLOCK"
    reason_codes = {a["reason_code"] for a in rec["learning_actions"]}
    assert any(
        "authority_shape" in code or code == "clp_gate_block" for code in reason_codes
    )


# ---------------------------------------------------------------------------
# PR-ready guard integration
# ---------------------------------------------------------------------------


def test_pr_ready_not_ready_blocks_agl(tmp_path):
    clp = _write_clp(tmp_path, gate_status="pass")
    pr_ready = _write_pr_ready(tmp_path, status="not_ready", clp_path=clp)
    rec = build_agent_core_loop_record(
        "CLP-02-AGL-NOT-READY",
        "claude",
        source_artifact=None,
        clp_evidence_artifact=str(clp),
        agent_pr_ready_result_ref=str(pr_ready),
    )
    assert rec["compliance_status"] == "BLOCK"
    actions = rec["learning_actions"]
    assert any(a["action_type"] == "resolve_pr_ready_block" for a in actions)


def test_pr_ready_ready_keeps_existing_compliance(tmp_path):
    """A ready guard should not flip a passing AGL to BLOCK by itself."""
    clp = _write_clp(tmp_path, gate_status="pass")
    pr_ready = _write_pr_ready(tmp_path, status="ready", clp_path=clp)
    rec = build_agent_core_loop_record(
        "CLP-02-AGL-READY",
        "claude",
        source_artifact=None,
        clp_evidence_artifact=str(clp),
        agent_pr_ready_result_ref=str(pr_ready),
    )
    # PQX leg has no CLP mapping, so AGL still BLOCKs on missing PQX evidence
    # (correct fail-closed behavior — CLP cannot certify PQX execution
    # closure). The test only asserts the guard did not introduce a NEW
    # not_ready action.
    actions = rec["learning_actions"]
    assert not any(
        a["action_type"] == "resolve_pr_ready_block" for a in actions
    )


def test_pr_ready_invalid_artifact_blocks_agl(tmp_path):
    clp = _write_clp(tmp_path, gate_status="pass")
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"artifact_type": "not_pr_ready"}), encoding="utf-8")
    rec = build_agent_core_loop_record(
        "CLP-02-AGL-INVALID-PR-READY",
        "claude",
        source_artifact=None,
        clp_evidence_artifact=str(clp),
        agent_pr_ready_result_ref=str(bad),
    )
    assert rec["compliance_status"] == "BLOCK"
    reason_codes = {a["reason_code"] for a in rec["learning_actions"]}
    assert "agent_pr_ready_evidence_invalid" in reason_codes


def test_agl_authority_scope_remains_observation_only(tmp_path):
    clp = _write_clp(tmp_path, gate_status="pass")
    pr_ready = _write_pr_ready(tmp_path, status="ready", clp_path=clp)
    rec = build_agent_core_loop_record(
        "CLP-02-AGL-AUTHORITY",
        "claude",
        source_artifact=None,
        clp_evidence_artifact=str(clp),
        agent_pr_ready_result_ref=str(pr_ready),
    )
    assert rec["authority_scope"] == "observation_only"
    blob = json.dumps(rec).lower()
    assert '"approved"' not in blob
    assert '"certified"' not in blob
    assert '"promoted"' not in blob
    assert '"enforced"' not in blob
