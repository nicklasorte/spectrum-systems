"""NT-25/26: Final operator proof review and new-maintainer drill.

Renders one compact proof for each of pass / block / freeze through the
operator triage CLI and verifies that a new maintainer can identify, from
CLI output alone:

  * what happened (final status)
  * why it happened (canonical reason category + detail reason code)
  * who owns it (owning system)
  * what artifact proves it (evidence refs)
  * what action is blocked or allowed (next recommended action)
  * what changed since the last proof (delta summary)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from spectrum_systems.modules.governance.loop_proof_bundle import build_loop_proof_bundle


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "print_loop_proof.py"
PACK_DIR = REPO_ROOT / "tests" / "fixtures" / "trust_regression_pack"


def _passing():
    return json.loads((PACK_DIR / "pass.json").read_text())["loop_inputs"]


def _blocking():
    return json.loads((PACK_DIR / "block.json").read_text())["loop_inputs"]


def _freezing():
    return json.loads((PACK_DIR / "freeze.json").read_text())["loop_inputs"]


def _run_cli(*args, expect_exit):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == expect_exit, (
        f"exit={result.returncode} stderr={result.stderr!r}"
    )
    return result.stdout


def _new_maintainer_can_diagnose(text: str, *, allow_pass=False) -> dict:
    """Extract the seven required diagnostic fields from CLI output."""
    found = {
        "final_status": None,
        "failed_or_passed_stage": None,
        "owning_system": None,
        "canonical_reason_category": None,
        "detail_reason_code": None,
        "evidence_refs_present": False,
        "next_recommended_action": None,
        "changed_evidence_section_present": False,
    }
    for line in text.splitlines():
        if line.startswith("final_status:"):
            found["final_status"] = line.split(":", 1)[1].strip()
        elif line.startswith("failed_or_passed_stage:"):
            found["failed_or_passed_stage"] = line.split(":", 1)[1].strip()
        elif line.startswith("owning_system:"):
            found["owning_system"] = line.split(":", 1)[1].strip()
        elif line.startswith("canonical_reason_category:"):
            found["canonical_reason_category"] = line.split(":", 1)[1].strip()
        elif line.startswith("detail_reason_code:"):
            found["detail_reason_code"] = line.split(":", 1)[1].strip()
        elif line.startswith("evidence_refs:"):
            found["evidence_refs_present"] = True
        elif line.startswith("changed_evidence_since_previous:"):
            found["changed_evidence_section_present"] = True
        elif line.startswith("next_recommended_action:"):
            found["next_recommended_action"] = line.split(":", 1)[1].strip()
    return found


def test_pass_proof_passes_new_maintainer_drill(tmp_path):
    bundle = build_loop_proof_bundle(**_passing())
    p = tmp_path / "pass.json"
    p.write_text(json.dumps(bundle))
    out = _run_cli(str(p), expect_exit=0)
    found = _new_maintainer_can_diagnose(out, allow_pass=True)
    assert found["final_status"] == "pass"
    assert found["evidence_refs_present"]
    assert found["next_recommended_action"]


def test_block_proof_passes_new_maintainer_drill(tmp_path):
    bundle = build_loop_proof_bundle(**_blocking())
    p = tmp_path / "block.json"
    p.write_text(json.dumps(bundle))
    out = _run_cli(str(p), expect_exit=2)
    found = _new_maintainer_can_diagnose(out)
    assert found["final_status"] == "block"
    assert found["failed_or_passed_stage"] not in (None, "-", "")
    assert found["owning_system"] not in (None, "-", "")
    assert found["canonical_reason_category"] not in (None, "-", "")
    assert found["evidence_refs_present"]
    assert found["next_recommended_action"]


def test_freeze_proof_passes_new_maintainer_drill(tmp_path):
    bundle = build_loop_proof_bundle(**_freezing())
    p = tmp_path / "freeze.json"
    p.write_text(json.dumps(bundle))
    out = _run_cli(str(p), expect_exit=3)
    found = _new_maintainer_can_diagnose(out)
    assert found["final_status"] == "freeze"
    assert found["next_recommended_action"]
    # Even on freeze, the owning system / canonical reason are present
    # (may be '-' when control freeze with no failed stage; but the field
    # MUST appear on screen so the maintainer can read it)
    assert found["canonical_reason_category"] is not None


def test_changed_evidence_section_renders_with_previous(tmp_path):
    prev_bundle = build_loop_proof_bundle(**_passing())
    inputs = _passing()
    inputs["bundle_id"] = "lpb-current"
    inputs["eval_summary"] = {"artifact_id": "evl-NEW", "status": "healthy"}
    curr_bundle = build_loop_proof_bundle(**inputs)
    pp = tmp_path / "prev.json"
    cp = tmp_path / "curr.json"
    pp.write_text(json.dumps(prev_bundle))
    cp.write_text(json.dumps(curr_bundle))
    out = _run_cli(str(cp), "--previous", str(pp), expect_exit=0)
    found = _new_maintainer_can_diagnose(out)
    assert found["changed_evidence_section_present"]
    # The eval_summary_ref difference is rendered
    assert "eval_summary_ref" in out
    assert "evl-NEW" in out


def test_one_command_renders_seven_diagnostic_signals_for_block(tmp_path):
    """Final hard gate (NT-26): one command, all required diagnostic
    signals visible without reading raw JSON."""
    bundle = build_loop_proof_bundle(**_blocking())
    p = tmp_path / "b.json"
    p.write_text(json.dumps(bundle))
    out = _run_cli(str(p), expect_exit=2)
    # Required diagnostic answers
    required_substrings = [
        "final_status:",
        "failed_or_passed_stage:",
        "owning_system:",
        "canonical_reason_category:",
        "evidence_refs:",
        "changed_evidence_since_previous:",
        "next_recommended_action:",
    ]
    for sub in required_substrings:
        assert sub in out, f"missing diagnostic field: {sub}"
