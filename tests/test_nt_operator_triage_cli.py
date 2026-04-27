"""NT-13..15: Operator triage CLI — render + red team + fix.

Verifies that ``scripts/print_loop_proof.py`` correctly summarizes pass /
block / freeze / corrupt / missing-evidence loop proof bundles, returns
canonical exit codes, and surfaces canonical reason categories.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from spectrum_systems.modules.governance.loop_proof_bundle import build_loop_proof_bundle


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "print_loop_proof.py"


def _passing_inputs():
    return dict(
        bundle_id="lpb-pass",
        trace_id="tPASS",
        run_id="rPASS",
        execution_record={
            "artifact_id": "exec-1",
            "artifact_type": "pqx_slice_execution_record",
            "status": "ok",
        },
        output_artifact={"artifact_id": "out-1", "artifact_type": "eval_summary"},
        eval_summary={"artifact_id": "evl-1", "status": "healthy"},
        control_decision={"decision_id": "cde-1", "decision": "allow"},
        enforcement_action={
            "enforcement_id": "sel-1",
            "enforcement_action": "allow_execution",
        },
        replay_record={"replay_id": "rpl-1", "artifact_id": "rpl-1", "status": "healthy"},
        lineage_summary={"summary_id": "lin-1", "artifact_id": "lin-1", "status": "healthy"},
    )


def _write(path: Path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def _run(args, expect_exit=None):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    if expect_exit is not None:
        assert result.returncode == expect_exit, (
            f"exit={result.returncode}, stdout={result.stdout!r}, stderr={result.stderr!r}"
        )
    return result


def test_pass_proof_exits_zero_and_renders_pass(tmp_path):
    bundle = build_loop_proof_bundle(**_passing_inputs())
    p = tmp_path / "pass.json"
    _write(p, bundle)
    res = _run([str(p)], expect_exit=0)
    assert "final_status:               pass" in res.stdout
    assert "owning_system" in res.stdout
    assert "canonical_reason_category" in res.stdout
    assert "evidence_refs:" in res.stdout
    assert "exec-1" in res.stdout


def test_block_proof_exits_two_and_surfaces_canonical_reason(tmp_path):
    inputs = _passing_inputs()
    inputs["bundle_id"] = "lpb-block"
    inputs["trace_id"] = "tBLOCK"
    inputs["eval_summary"] = {
        "artifact_id": "evl-bad",
        "status": "blocked",
        "block_reason": "missing_required_eval_result",
    }
    inputs["control_decision"] = {
        "decision_id": "cde-blk",
        "decision": "block",
        "reason_code": "missing_required_eval_result",
    }
    inputs["enforcement_action"] = {
        "enforcement_id": "sel-blk",
        "enforcement_action": "deny_execution",
    }
    bundle = build_loop_proof_bundle(**inputs)
    p = tmp_path / "block.json"
    _write(p, bundle)
    res = _run([str(p)], expect_exit=2)
    assert "final_status:               block" in res.stdout
    # Canonical reason surfaced
    assert "canonical_reason_category:" in res.stdout
    # Failed stage surfaced
    assert "failed_or_passed_stage:" in res.stdout
    # Next action present
    assert "next_recommended_action:" in res.stdout


def test_freeze_proof_exits_three(tmp_path):
    inputs = _passing_inputs()
    inputs["bundle_id"] = "lpb-frz"
    inputs["trace_id"] = "tFRZ"
    inputs["control_decision"] = {"decision_id": "cde-frz", "decision": "freeze"}
    bundle = build_loop_proof_bundle(**inputs)
    p = tmp_path / "freeze.json"
    _write(p, bundle)
    res = _run([str(p)], expect_exit=3)
    assert "final_status:               freeze" in res.stdout


def test_corrupt_json_exits_four(tmp_path):
    p = tmp_path / "corrupt.json"
    p.write_text("not json at all{", encoding="utf-8")
    res = _run([str(p)], expect_exit=4)
    assert "CORRUPT" in res.stderr


def test_missing_required_field_exits_four(tmp_path):
    p = tmp_path / "incomplete.json"
    _write(p, {"artifact_type": "loop_proof_bundle", "bundle_id": "x"})  # missing trace_id, final_status
    res = _run([str(p)], expect_exit=4)
    assert "CORRUPT_OR_MISSING_REQUIRED" in res.stderr


def test_missing_file_exits_four(tmp_path):
    res = _run([str(tmp_path / "absent.json")], expect_exit=4)
    assert "CORRUPT" in res.stderr or "not found" in res.stderr


def test_wrong_artifact_type_exits_four(tmp_path):
    p = tmp_path / "wrong_type.json"
    _write(
        p,
        {
            "artifact_type": "not_a_loop_proof",
            "bundle_id": "x",
            "trace_id": "y",
            "final_status": "pass",
        },
    )
    res = _run([str(p)], expect_exit=4)
    assert "CORRUPT" in res.stderr


def test_optional_certification_index_renders(tmp_path):
    bundle = build_loop_proof_bundle(**_passing_inputs())
    cei = {
        "artifact_type": "certification_evidence_index",
        "index_id": "cei-1",
        "trace_id": "tPASS",
        "status": "ready",
        "blocking_reason_canonical": "CERT_OK",
        "references": {},
    }
    bp = tmp_path / "pass.json"
    cp = tmp_path / "cei.json"
    _write(bp, bundle)
    _write(cp, cei)
    res = _run([str(bp), "--certification-evidence-index", str(cp)], expect_exit=0)
    assert "cert_index_status:          ready" in res.stdout
    assert "cert_index_block_canonical: CERT_OK" in res.stdout


def test_changed_evidence_since_previous_renders(tmp_path):
    inputs = _passing_inputs()
    bundle_prev = build_loop_proof_bundle(**inputs)
    inputs["bundle_id"] = "lpb-curr"
    inputs["eval_summary"] = {"artifact_id": "evl-NEW", "status": "healthy"}
    bundle_curr = build_loop_proof_bundle(**inputs)
    pp = tmp_path / "prev.json"
    cp = tmp_path / "curr.json"
    _write(pp, bundle_prev)
    _write(cp, bundle_curr)
    res = _run([str(cp), "--previous", str(pp)], expect_exit=0)
    assert "changed_evidence_since_previous:" in res.stdout
    # The eval_summary_ref changed
    assert "eval_summary_ref" in res.stdout


def test_unknown_canonical_reason_renders_unknown(tmp_path):
    """Bundle with an exotic detail_reason_code should not crash; CLI
    must render a stable category placeholder."""
    bundle = build_loop_proof_bundle(**_passing_inputs())
    bundle["primary_reason_code"] = "totally_invented_code"
    bundle["final_status"] = "block"
    bundle["canonical_blocking_category"] = None
    p = tmp_path / "unknown.json"
    _write(p, bundle)
    res = _run([str(p)], expect_exit=2)
    # Either resolves to '-' (no canonical_blocking_category) or 'UNKNOWN'
    assert "canonical_reason_category:" in res.stdout
    assert "totally_invented_code" in res.stdout


def test_bloated_bundle_renders_size_warning(tmp_path):
    bundle = build_loop_proof_bundle(**_passing_inputs())
    bundle["human_readable"] = "X" * 7000  # exceeds 6000 budget
    p = tmp_path / "bloat.json"
    _write(p, bundle)
    res = _run([str(p)], expect_exit=0)
    # Size validation surface visible
    assert "size_validation:" in res.stdout
    assert "size_block_reasons:" in res.stdout


def test_stable_ordering_of_evidence_refs(tmp_path):
    bundle = build_loop_proof_bundle(**_passing_inputs())
    p = tmp_path / "pass.json"
    _write(p, bundle)
    res = _run([str(p)], expect_exit=0)
    # Order is stable: execution before eval before control before enforcement
    out = res.stdout
    assert out.index("execution_record_ref") < out.index("eval_summary_ref")
    assert out.index("eval_summary_ref") < out.index("control_decision_ref")
    assert out.index("control_decision_ref") < out.index("enforcement_action_ref")
