"""NT-25..26: Final operator proof review + new maintainer review test.

Generates one compact loop proof for each of pass / block / freeze, runs
each through the operator triage CLI, and asserts every required
diagnostic answer is present in the rendered output. Then NT-26 simulates
a new maintainer who has only the CLI output, the proof bundle, and the
evidence index — and confirms they can answer the six required questions.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from spectrum_systems.modules.governance.certification_delta import (
    compute_certification_delta,
)
from spectrum_systems.modules.governance.certification_evidence_index import (
    build_certification_evidence_index,
)
from spectrum_systems.modules.governance.loop_proof_bundle import (
    build_loop_proof_bundle,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "print_loop_proof.py"


@pytest.fixture(scope="module")
def cli_module():
    spec = importlib.util.spec_from_file_location("print_loop_proof", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["print_loop_proof"] = module
    spec.loader.exec_module(module)
    return module


def _write_json(tmp: Path, name: str, payload: dict) -> Path:
    p = tmp / name
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def _build_pass_proof():
    return build_loop_proof_bundle(
        bundle_id="lpb-final-pass",
        trace_id="tFIN-PASS",
        run_id="rFIN",
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


def _build_block_proof():
    return build_loop_proof_bundle(
        bundle_id="lpb-final-block",
        trace_id="tFIN-BLOCK",
        run_id="rFIN",
        execution_record={
            "artifact_id": "exec-1",
            "artifact_type": "pqx_slice_execution_record",
            "status": "ok",
        },
        output_artifact={"artifact_id": "out-1", "artifact_type": "eval_summary"},
        eval_summary={
            "artifact_id": "evl-bad",
            "status": "blocked",
            "block_reason": "missing_required_eval_result",
        },
        control_decision={
            "decision_id": "cde-blk",
            "decision": "block",
            "reason_code": "missing_required_eval_result",
        },
        enforcement_action={
            "enforcement_id": "sel-blk",
            "enforcement_action": "deny_execution",
        },
        replay_record={"replay_id": "rpl-1", "artifact_id": "rpl-1", "status": "healthy"},
        lineage_summary={"summary_id": "lin-1", "artifact_id": "lin-1", "status": "healthy"},
    )


def _build_freeze_proof():
    return build_loop_proof_bundle(
        bundle_id="lpb-final-frz",
        trace_id="tFIN-FRZ",
        run_id="rFIN",
        execution_record={
            "artifact_id": "exec-1",
            "artifact_type": "pqx_slice_execution_record",
            "status": "ok",
        },
        output_artifact={"artifact_id": "out-1", "artifact_type": "eval_summary"},
        eval_summary={"artifact_id": "evl-1", "status": "healthy"},
        control_decision={"decision_id": "cde-frz", "decision": "freeze"},
        enforcement_action={
            "enforcement_id": "sel-frz",
            "enforcement_action": "require_manual_review",
        },
        replay_record={"replay_id": "rpl-1", "artifact_id": "rpl-1", "status": "healthy"},
        lineage_summary={"summary_id": "lin-1", "artifact_id": "lin-1", "status": "healthy"},
    )


# ---- NT-25: render each proof through the CLI ----


def test_pass_proof_renders_with_all_diagnostic_lines(
    cli_module, tmp_path: Path, capsys
) -> None:
    bundle = _build_pass_proof()
    bp = _write_json(tmp_path, "bundle.json", bundle)
    code = cli_module.main(["--bundle", str(bp)])
    out = capsys.readouterr().out
    assert code == 0
    assert "final_status: pass" in out
    assert "owning_system: -" in out  # pass path has no failed stage
    assert "EVIDENCE REFS" in out
    # All required ref keys present (value present or '-')
    for key in (
        "execution_record_ref",
        "output_artifact_ref",
        "eval_summary_ref",
        "control_decision_ref",
        "enforcement_action_ref",
        "replay_record_ref",
        "lineage_chain_ref",
        "certification_evidence_index_ref",
    ):
        assert f"{key}:" in out


def test_block_proof_renders_with_canonical_reason_and_owner(
    cli_module, tmp_path: Path, capsys
) -> None:
    bundle = _build_block_proof()
    bp = _write_json(tmp_path, "bundle.json", bundle)
    code = cli_module.main(["--bundle", str(bp)])
    out = capsys.readouterr().out
    assert code == 1
    assert "final_status: block" in out
    assert "failed_stage: eval" in out
    assert "owning_system: EVL" in out
    # Canonical category should be one of the known finite set
    assert any(
        cat in out
        for cat in (
            "EVAL_FAILURE",
            "MISSING_ARTIFACT",
            "CERTIFICATION_GAP",
        )
    )
    assert "next_recommended_action:" in out
    # Detail reason preserved alongside the canonical category
    assert "detail_reason_code:" in out


def test_freeze_proof_renders_freeze_status(
    cli_module, tmp_path: Path, capsys
) -> None:
    bundle = _build_freeze_proof()
    bp = _write_json(tmp_path, "bundle.json", bundle)
    code = cli_module.main(["--bundle", str(bp)])
    out = capsys.readouterr().out
    assert code == 1
    assert "final_status: freeze" in out


# ---- NT-26: new maintainer review ----


def test_new_maintainer_can_diagnose_block_from_cli_only(
    cli_module, tmp_path: Path, capsys
) -> None:
    """A new maintainer has access only to the CLI output, the proof
    bundle file, and the evidence index file. They must answer:
      1. what happened?      (final_status + owning_system + canonical_reason)
      2. why did it happen?  (detail_reason_code)
      3. who owns it?        (owning_system)
      4. what artifact proves it? (failure_trace_ref / eval_summary_ref)
      5. what action is blocked or allowed? (final_status)
      6. next fix?           (next_recommended_action)
    """
    bundle = _build_block_proof()
    cei = build_certification_evidence_index(
        index_id="cei-final-block",
        trace_id=bundle["trace_id"],
        eval_summary={
            "artifact_id": "evl-bad",
            "status": "blocked",
            "block_reason": "missing_required_eval_result",
        },
        lineage_summary={"artifact_id": "lin-1", "status": "healthy"},
        replay_summary={"artifact_id": "rpl-1", "status": "healthy"},
        control_decision={"decision_id": "cde-blk", "decision": "block"},
        enforcement_action={
            "enforcement_id": "sel-blk",
            "enforcement_action": "deny_execution",
        },
        authority_shape_preflight={"artifact_id": "asp-1", "status": "pass"},
        registry_validation={"artifact_id": "reg-1", "status": "pass", "violations": []},
        artifact_tier_validation={
            "validation_id": "tier-1",
            "decision": "allow",
            "reason_code": "TIER_OK",
        },
    )
    bp = _write_json(tmp_path, "bundle.json", bundle)
    cp = _write_json(tmp_path, "cei.json", cei)
    code = cli_module.main(
        ["--bundle", str(bp), "--evidence-index", str(cp)]
    )
    out = capsys.readouterr().out

    # Q1: what happened
    assert "final_status: block" in out
    # Q2: why
    assert "detail_reason_code:" in out
    assert "canonical_reason_category:" in out
    # Q3: who owns it
    assert "owning_system: EVL" in out
    # Q4: what artifact proves it (eval_summary_ref points to evl-bad)
    assert "eval_summary_ref: evl-bad" in out
    # Q5: action blocked/allowed
    assert code == 1
    # Q6: next fix
    assert "next_recommended_action:" in out


def test_new_maintainer_sees_changed_evidence_via_delta(
    cli_module, tmp_path: Path, capsys
) -> None:
    """Delta must be visible to the new maintainer in CLI output."""
    bundle = _build_pass_proof()
    prev_cei = {
        "artifact_type": "certification_evidence_index",
        "references": {"eval_summary_ref": "evl-old"},
    }
    curr_cei = {
        "artifact_type": "certification_evidence_index",
        "references": {"eval_summary_ref": "evl-1"},
    }
    delta = compute_certification_delta(
        delta_id="d-final",
        previous_index=prev_cei,
        current_index=curr_cei,
    )
    bp = _write_json(tmp_path, "bundle.json", bundle)
    dp = _write_json(tmp_path, "delta.json", delta)
    cli_module.main(["--bundle", str(bp), "--delta", str(dp)])
    out = capsys.readouterr().out

    assert "CERTIFICATION DELTA" in out
    assert "overall_delta_risk: high" in out
    assert "changed_digest: 1" in out


def test_new_maintainer_compact_output_under_one_page_when_passing(
    cli_module, tmp_path: Path, capsys
) -> None:
    """A passing proof's CLI output must remain operator-readable in
    one screen — the human readable budget bounds the rendered text."""
    bundle = _build_pass_proof()
    bp = _write_json(tmp_path, "bundle.json", bundle)
    cli_module.main(["--bundle", str(bp)])
    out = capsys.readouterr().out
    # Budget is generous but bounded: under a typical operator screen.
    assert len(out) < 6000
