from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _eval_case_payload() -> dict[str, object]:
    return {
        "artifact_type": "eval_case",
        "schema_version": "1.0.0",
        "run_id": "run-1",
        "trace_id": "11111111-1111-4111-8111-111111111111",
        "eval_case_id": "authority-language-case",
        "input_artifact_refs": ["docs/review-actions/PLAN-HRD-002-2026-04-28.md"],
        "expected_output_spec": {
            "eval_name": "authority_language_compliance:v1",
            "target_paths": ["docs/review-actions/PLAN-HRD-002-2026-04-28.md"],
        },
        "scoring_rubric": {},
        "evaluation_type": "deterministic",
        "created_from": "manual",
    }


def test_run_eval_case_authority_language_compliance_fails_on_reserved_verb(tmp_path: Path) -> None:
    case_path = tmp_path / "eval_case.json"
    out_path = tmp_path / "eval_result.json"
    case_path.write_text(json.dumps(_eval_case_payload()), encoding="utf-8")

    proc = subprocess.run(
        ["python", "scripts/run_eval_case.py", "--case", str(case_path), "--output", str(out_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    result = json.loads(out_path.read_text(encoding="utf-8"))
    assert result["result_status"] == "fail"
    assert "authority_language_violation_non_authority_artifact" in result["failure_modes"]
