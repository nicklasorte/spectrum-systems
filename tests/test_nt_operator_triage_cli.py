import json
import subprocess
import sys


def test_cli_pass_and_block_exit_codes(tmp_path) -> None:
    pass_path = tmp_path / "pass.json"
    pass_path.write_text(json.dumps({"final_status": "pass", "trace_summary": {}}), encoding="utf-8")
    block_path = tmp_path / "block.json"
    block_path.write_text(json.dumps({"final_status": "block", "trace_summary": {"failed_stage": "eval", "owning_system": "EVL"}}), encoding="utf-8")

    cmd = [sys.executable, "scripts/print_loop_proof.py", "--loop-proof", str(pass_path)]
    ok = subprocess.run(cmd, check=False, capture_output=True, text=True)
    assert ok.returncode == 0
    assert "final_status: pass" in ok.stdout

    bad = subprocess.run([sys.executable, "scripts/print_loop_proof.py", "--loop-proof", str(block_path)], check=False, capture_output=True, text=True)
    assert bad.returncode != 0
    assert "final_status: block" in bad.stdout
