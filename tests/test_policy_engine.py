import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "governance" / "policies" / "run-policy-engine.py"
REPORT_PATH = REPO_ROOT / "artifacts" / "policy-engine-report.json"
SUMMARY_PATH = REPO_ROOT / "artifacts" / "policy-engine-summary.md"
SEEDED_POLICIES = {f"GOV-00{i}" for i in range(1, 9)}
VALID_STATUSES = {"pass", "fail", "warning"}


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


def test_policy_engine_result_shape() -> None:
    """Every result record must contain the fields required for CI output."""
    report = _run_policy_engine()

    required_fields = {"policy_id", "severity", "status", "subject", "message", "evidence"}
    for result in report["results"]:
        missing = required_fields - result.keys()
        assert not missing, f"Result missing fields {missing}: {result}"
        assert result["status"] in VALID_STATUSES, f"Unexpected status '{result['status']}' in {result}"
        assert result["severity"] in {"error", "warning"}, (
            f"Unexpected severity '{result['severity']}' in {result}"
        )
        assert isinstance(result["evidence"], list)


def test_policy_engine_summary_markdown_has_sections() -> None:
    """The generated markdown summary must contain the key sections for human review."""
    _run_policy_engine()
    content = SUMMARY_PATH.read_text(encoding="utf-8")

    assert "# Policy Engine Summary" in content
    assert "## Error Findings" in content
    assert "## Warning Findings" in content
    assert "## Findings by Repo" in content


def test_policy_engine_no_error_severity_failures_on_example_manifests() -> None:
    """The example governance manifests that ship in this repo should not produce
    error-severity policy failures. Warnings are acceptable."""
    report = _run_policy_engine()
    error_failures = [
        r for r in report["results"]
        if r.get("severity") == "error" and r.get("status") == "fail"
    ]
    assert not error_failures, (
        "Error-severity policy failures detected on example manifests:\n"
        + "\n".join(
            f"  {r['policy_id']} | {r['subject']}: {r['message']}"
            for r in error_failures
        )
    )

