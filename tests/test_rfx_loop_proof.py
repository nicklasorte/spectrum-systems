from __future__ import annotations

import json
import subprocess
import sys

from spectrum_systems.modules.runtime.rfx_loop_proof import build_rfx_loop_proof


def _valid_proof() -> dict:
    return {
        "proof_id": "proof-1",
        "run_id": "run-1",
        "trace_id": "trace-1",
        "owner_context": "RFX",
        "failure_ref": "f",
        "eval_ref": "e",
        "repair_ref": "p",
        "learn_ref": "l",
        "recommend_ref": "r",
        "failing_stage": "prove",
        "reason_codes": ["rfx_eval_failed"],
        "repair_hint": "run targeted fix",
    }


def test_rt_n01_missing_required_field_fails_then_revalidate() -> None:
    bad = build_rfx_loop_proof(proof={"proof_id": "proof-1"})
    assert "rfx_loop_proof_missing_required_field" in bad["reason_codes_emitted"]

    good = build_rfx_loop_proof(proof=_valid_proof())
    assert good["status"] == "valid"


def test_rt_n02_reason_flood_fails_then_revalidate() -> None:
    bad_proof = _valid_proof()
    bad_proof["reason_codes"] = ["a", "b", "c", "d"]
    bad = build_rfx_loop_proof(proof=bad_proof)
    assert "rfx_loop_proof_reason_flood" in bad["reason_codes_emitted"]
    assert bad["primary_reason_code"] == "a"

    good = build_rfx_loop_proof(proof=_valid_proof())
    assert "rfx_loop_proof_reason_flood" not in good["reason_codes_emitted"]


def test_rt_n03_hidden_failing_stage_fails_then_revalidate() -> None:
    bad_proof = _valid_proof()
    bad_proof["failing_stage"] = ""
    bad = build_rfx_loop_proof(proof=bad_proof)
    assert "rfx_loop_proof_failing_stage_missing" in bad["reason_codes_emitted"]

    good = build_rfx_loop_proof(proof=_valid_proof())
    assert good["failing_stage"] == "Prove"


def test_rt_n04_cli_missing_owner_or_hint_fails_then_revalidate(tmp_path) -> None:
    bad_proof = _valid_proof()
    bad_proof["owner_context"] = ""
    bad_proof["repair_hint"] = ""
    rendered = build_rfx_loop_proof(proof=bad_proof)

    bad_path = tmp_path / "bad.json"
    bad_path.write_text(json.dumps(rendered), encoding="utf-8")

    bad_run = subprocess.run(
        [sys.executable, "scripts/print_rfx_loop_proof.py", "--proof", str(bad_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert bad_run.returncode == 1

    good_path = tmp_path / "good.json"
    good_path.write_text(json.dumps(build_rfx_loop_proof(proof=_valid_proof())), encoding="utf-8")
    good_run = subprocess.run(
        [sys.executable, "scripts/print_rfx_loop_proof.py", "--proof", str(good_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert good_run.returncode == 0
    assert "owner_context: RFX" in good_run.stdout
