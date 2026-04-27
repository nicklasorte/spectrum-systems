import json
import subprocess
import sys
from pathlib import Path


def test_new_maintainer_can_triage_from_cli_output(tmp_path: Path) -> None:
    proof = {
        "final_status": "block",
        "canonical_blocking_category": "EVAL_FAILURE",
        "trace_summary": {"failed_stage": "eval", "owning_system": "EVL"},
        "execution_record_ref": "exec-1",
        "delta_summary": {"changed_evidence_refs": ["eval_summary_ref"]},
    }
    p = tmp_path / "proof.json"
    p.write_text(json.dumps(proof), encoding="utf-8")
    proc = subprocess.run([sys.executable, "scripts/print_loop_proof.py", "--loop-proof", str(p)], check=False, capture_output=True, text=True)
    out = proc.stdout
    assert "final_status: block" in out
    assert "owning_system: EVL" in out
    assert "canonical_reason_category: EVAL_FAILURE" in out
    assert "changed_evidence_summary: eval_summary_ref" in out
    assert "next_recommended_action:" in out
