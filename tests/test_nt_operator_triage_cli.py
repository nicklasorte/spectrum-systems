"""NT-13..15: Operator triage CLI drill.

Tests the print_loop_proof.py CLI against pass / block / freeze /
corrupt / missing / stale / bloated / unknown-reason scenarios.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "print_loop_proof.py"


@pytest.fixture(scope="module")
def cli_module():
    spec = importlib.util.spec_from_file_location("print_loop_proof", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["print_loop_proof"] = module
    spec.loader.exec_module(module)
    return module


def _write_json(tmp_path: Path, name: str, payload: dict) -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def _passing_bundle() -> dict:
    return {
        "artifact_type": "loop_proof_bundle",
        "schema_version": "1.0.0",
        "bundle_id": "lpb-cli-pass",
        "trace_id": "tCLI-PASS",
        "run_id": "rCLI",
        "final_status": "pass",
        "canonical_blocking_category": None,
        "execution_record_ref": "exec-1",
        "output_artifact_ref": "out-1",
        "eval_summary_ref": "evl-1",
        "control_decision_ref": "cde-1",
        "enforcement_action_ref": "sel-1",
        "replay_record_ref": "rpl-1",
        "lineage_chain_ref": "lin-1",
        "certification_evidence_index_ref": "cei-1",
        "failure_trace_ref": None,
        "trace_summary": {
            "overall_status": "ok",
            "failed_stage": None,
            "owning_system": None,
            "one_page_summary": (
                "FAILURE TRACE — trace_id=tCLI-PASS\n"
                "overall_status: ok\n"
                "failed_stage: -\n"
                "canonical_category: -\n"
                "detail_reason_code: -\n"
                "next_recommended_action: -"
            ),
        },
        "human_readable": "LOOP PROOF BUNDLE — pass",
    }


def _block_bundle(reason: str = "EVAL_FAILURE", detail: str = "missing_required_eval_result") -> dict:
    one_page = (
        "FAILURE TRACE — trace_id=tCLI-BLOCK\n"
        "overall_status: failed\n"
        "failed_stage: eval\n"
        "owning_system: EVL\n"
        f"canonical_category: {reason}\n"
        f"detail_reason_code: {detail}\n"
        "next_recommended_action: Run required evals."
    )
    return {
        "artifact_type": "loop_proof_bundle",
        "bundle_id": "lpb-cli-block",
        "trace_id": "tCLI-BLOCK",
        "run_id": "r-blk",
        "final_status": "block",
        "canonical_blocking_category": reason,
        "execution_record_ref": "exec-2",
        "output_artifact_ref": "out-2",
        "eval_summary_ref": "evl-bad",
        "control_decision_ref": "cde-2",
        "enforcement_action_ref": "sel-2",
        "replay_record_ref": None,
        "lineage_chain_ref": "lin-2",
        "certification_evidence_index_ref": "cei-2",
        "failure_trace_ref": "ft-2",
        "trace_summary": {
            "overall_status": "failed",
            "failed_stage": "eval",
            "owning_system": "EVL",
            "one_page_summary": one_page,
        },
        "human_readable": "LOOP PROOF BUNDLE — block",
    }


def _freeze_bundle() -> dict:
    b = _block_bundle()
    b["bundle_id"] = "lpb-cli-frz"
    b["trace_id"] = "tCLI-FRZ"
    b["final_status"] = "freeze"
    b["canonical_blocking_category"] = "CERTIFICATION_GAP"
    return b


# ---- NT-13/14: pass / block / freeze / unknown ----


def test_pass_bundle_renders_and_exits_zero(cli_module, tmp_path: Path) -> None:
    bundle_path = _write_json(tmp_path, "bundle.json", _passing_bundle())
    code = cli_module.main(["--bundle", str(bundle_path)])
    assert code == 0


def test_block_bundle_exits_one(cli_module, tmp_path: Path) -> None:
    bundle_path = _write_json(tmp_path, "bundle.json", _block_bundle())
    code = cli_module.main(["--bundle", str(bundle_path)])
    assert code == 1


def test_freeze_bundle_exits_one(cli_module, tmp_path: Path) -> None:
    bundle_path = _write_json(tmp_path, "bundle.json", _freeze_bundle())
    code = cli_module.main(["--bundle", str(bundle_path)])
    assert code == 1


def test_unknown_canonical_reason_exits_three(cli_module, tmp_path: Path) -> None:
    b = _block_bundle()
    b["canonical_blocking_category"] = "UNKNOWN"
    bundle_path = _write_json(tmp_path, "bundle.json", b)
    code = cli_module.main(["--bundle", str(bundle_path)])
    assert code == 3


def test_corrupt_bundle_exits_two(cli_module, tmp_path: Path) -> None:
    bundle_path = tmp_path / "corrupt.json"
    bundle_path.write_text("{not json", encoding="utf-8")
    code = cli_module.main(["--bundle", str(bundle_path)])
    assert code == 2


def test_missing_bundle_exits_two(cli_module, tmp_path: Path) -> None:
    code = cli_module.main(["--bundle", str(tmp_path / "does_not_exist.json")])
    assert code == 2


def test_wrong_artifact_type_exits_two(cli_module, tmp_path: Path) -> None:
    not_proof = {"artifact_type": "something_else", "final_status": "pass"}
    p = _write_json(tmp_path, "bundle.json", not_proof)
    code = cli_module.main(["--bundle", str(p)])
    assert code == 2


def test_unknown_final_status_exits_two(cli_module, tmp_path: Path) -> None:
    b = _passing_bundle()
    b["final_status"] = "weird"
    p = _write_json(tmp_path, "bundle.json", b)
    code = cli_module.main(["--bundle", str(p)])
    assert code == 2


# ---- NT-14: stale freshness blocks ----


def test_stale_freshness_blocks_pass_bundle(cli_module, tmp_path: Path) -> None:
    bundle_path = _write_json(tmp_path, "bundle.json", _passing_bundle())
    fresh_path = _write_json(
        tmp_path,
        "freshness.json",
        {
            "artifact_type": "trust_artifact_freshness_audit",
            "audit_id": "aud-x",
            "status": "stale",
            "canonical_reason": "TRUST_FRESHNESS_STALE_DIGEST_MISMATCH",
            "stale_kinds": ["certification_evidence_index"],
            "unknown_kinds": [],
            "items": [],
        },
    )
    code = cli_module.main(
        ["--bundle", str(bundle_path), "--freshness", str(fresh_path)]
    )
    assert code == 1


def test_evidence_index_inconsistency_exits_two(cli_module, tmp_path: Path) -> None:
    """Bundle says pass but cert index says blocked → corrupt."""
    bundle_path = _write_json(tmp_path, "bundle.json", _passing_bundle())
    cei_path = _write_json(
        tmp_path,
        "cei.json",
        {
            "artifact_type": "certification_evidence_index",
            "index_id": "cei-bad",
            "status": "blocked",
            "blocking_reason_canonical": "CERTIFICATION_GAP",
        },
    )
    code = cli_module.main(
        ["--bundle", str(bundle_path), "--evidence-index", str(cei_path)]
    )
    assert code == 2


# ---- NT-14: rendering legibility ----


def test_renderer_includes_required_diagnostic_lines(
    cli_module, tmp_path: Path, capsys
) -> None:
    bundle_path = _write_json(tmp_path, "bundle.json", _block_bundle())
    cei_path = _write_json(
        tmp_path,
        "cei.json",
        {
            "artifact_type": "certification_evidence_index",
            "index_id": "cei-2",
            "status": "blocked",
            "blocking_reason_canonical": "EVAL_FAILURE",
            "blocking_detail_codes": ["CERT_MISSING_EVAL_PASS"],
            "missing_references": ["enforcement_action_ref"],
        },
    )
    cli_module.main(
        ["--bundle", str(bundle_path), "--evidence-index", str(cei_path)]
    )
    out = capsys.readouterr().out
    # A new maintainer can answer all six questions from the printed text.
    assert "final_status: block" in out
    assert "failed_stage: eval" in out
    assert "owning_system: EVL" in out
    assert "canonical_reason_category: EVAL_FAILURE" in out
    assert "detail_reason_code: missing_required_eval_result" in out
    assert "eval_summary_ref: evl-bad" in out
    assert "next_recommended_action: Run required evals." in out
    # Ordering is stable: SUMMARY appears before EVIDENCE REFS appears
    # before ONE-PAGE TRACE.
    assert out.index("LOOP PROOF — SUMMARY") < out.index("EVIDENCE REFS")
    assert out.index("EVIDENCE REFS") < out.index("ONE-PAGE TRACE")


def test_renderer_includes_delta_when_provided(
    cli_module, tmp_path: Path, capsys
) -> None:
    bundle_path = _write_json(tmp_path, "bundle.json", _passing_bundle())
    delta_path = _write_json(
        tmp_path,
        "delta.json",
        {
            "artifact_type": "certification_delta",
            "overall_delta_risk": "low",
            "added_refs": ["new-ref"],
            "removed_refs": [],
            "changed_digest": [],
            "changed_status": [],
            "changed_reason": [],
            "changed_owner": [],
            "unchanged_refs": ["evl-1", "lin-1"],
        },
    )
    cli_module.main(["--bundle", str(bundle_path), "--delta", str(delta_path)])
    out = capsys.readouterr().out
    assert "CERTIFICATION DELTA" in out
    assert "overall_delta_risk: low" in out
    assert "added: 1" in out


def test_renderer_freshness_section_when_provided(
    cli_module, tmp_path: Path, capsys
) -> None:
    bundle_path = _write_json(tmp_path, "bundle.json", _passing_bundle())
    fresh_path = _write_json(
        tmp_path,
        "freshness.json",
        {
            "artifact_type": "trust_artifact_freshness_audit",
            "audit_id": "aud-1",
            "status": "current",
            "canonical_reason": "TRUST_FRESHNESS_OK",
            "stale_kinds": [],
            "unknown_kinds": [],
        },
    )
    cli_module.main(
        ["--bundle", str(bundle_path), "--freshness", str(fresh_path)]
    )
    out = capsys.readouterr().out
    assert "PROOF FRESHNESS" in out
    assert "status: current" in out


# ---- NT-15: stable, no business logic added ----


def test_renderer_does_not_invent_data(cli_module, tmp_path: Path, capsys) -> None:
    """If a bundle has only a final_status and no trace_summary, the
    renderer must surface placeholders ('-') rather than fabricated state."""
    minimal = {
        "artifact_type": "loop_proof_bundle",
        "bundle_id": "lpb-min",
        "trace_id": "tMIN",
        "final_status": "pass",
    }
    p = _write_json(tmp_path, "bundle.json", minimal)
    code = cli_module.main(["--bundle", str(p)])
    assert code == 0
    out = capsys.readouterr().out
    assert "failed_stage: -" in out
    assert "owning_system: -" in out
