import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "governance" / "policies" / "run-policy-engine.py"
REPORT_PATH = REPO_ROOT / "artifacts" / "policy-engine-report.json"
SUMMARY_PATH = REPO_ROOT / "artifacts" / "policy-engine-summary.md"
SEEDED_POLICIES = {f"GOV-00{i}" for i in range(1, 9)}


def _run_policy_engine() -> dict:
    subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        check=True,
        cwd=str(REPO_ROOT),
    )
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def test_policy_engine_produces_outputs() -> None:
    if REPORT_PATH.exists():
        REPORT_PATH.unlink()
    if SUMMARY_PATH.exists():
        SUMMARY_PATH.unlink()

    report = _run_policy_engine()

    assert REPORT_PATH.exists()
    assert SUMMARY_PATH.exists()

    assert "summary" in report and "results" in report
    assert report["summary"]["policies_evaluated"] == len(report["results"])

    results_sorted = sorted(report["results"], key=lambda r: (r["policy_id"], r["subject"]))
    assert report["results"] == results_sorted

    policy_ids = {result["policy_id"] for result in report["results"]}
    assert SEEDED_POLICIES.issubset(policy_ids)

    summary = report["summary"]
    assert isinstance(summary["errors"], int)
    assert isinstance(summary["warnings"], int)
    assert isinstance(summary["repos_checked"], int)
