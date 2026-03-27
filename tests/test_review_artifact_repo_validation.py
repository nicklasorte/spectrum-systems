from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "validate_review_artifacts.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def _valid_review_payload(review_id: str) -> dict[str, object]:
    return {
        "review_id": review_id,
        "module": "validator_alignment",
        "review_type": "repo_level",
        "review_date": "2026-03-27",
        "reviewer": "Codex",
        "decision": "FAIL",
        "trust_assessment": "medium",
        "status": "final",
        "scope": ["scripts/validate_review_artifacts.py"],
        "related_plan": "docs/review-actions/PLAN-PQX-FIX-REVIEW-VALIDATOR-ALIGNMENT-2026-03-27.md",
        "critical_findings": [
            {
                "id": "F-001",
                "severity": "high",
                "file": "scripts/validate_review_artifacts.py",
                "function": "validate_artifact_pair",
                "failure_mode": "Synthetic failure mode for validator test.",
                "impact": "Synthetic impact for deterministic test coverage.",
                "minimal_fix": "Synthetic minimal fix for deterministic test coverage.",
            }
        ],
        "required_fixes": [
            {
                "fix_id": "FIX-001",
                "description": "Synthetic fix for deterministic test coverage.",
                "priority": "P1",
            }
        ],
        "watch_items": ["Synthetic watch item."],
        "failure_mode_summary": "Synthetic summary for deterministic validator test coverage.",
    }


def _write_valid_markdown(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "---",
                "module: validator_alignment",
                "review_type: repo_level",
                "review_date: 2026-03-27",
                "reviewer: Codex",
                "decision: FAIL",
                "trust_assessment: medium",
                "status: final",
                "related_plan: docs/review-actions/PLAN-PQX-FIX-REVIEW-VALIDATOR-ALIGNMENT-2026-03-27.md",
                "---",
                "",
                "## Scope",
                "- Synthetic scope.",
                "",
                "## Decision",
                "- Synthetic decision.",
                "",
                "## Trust Assessment",
                "- Synthetic trust assessment.",
                "",
                "## Critical Findings",
                "- Synthetic finding.",
                "",
                "## Required Fixes",
                "- Synthetic fix.",
                "",
                "## Optional Improvements",
                "- Synthetic optional item.",
                "",
                "## Failure Mode Summary",
                "- Synthetic summary.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_repo_level_validator_passes_current_artifacts() -> None:
    result = _run()
    assert result.returncode == 0, (
        "Expected current governed review artifacts to pass repo-level validation.\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_repo_level_validator_fails_invalid_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / "2026-03-27-invalid-validator-artifact.json"
    payload = _valid_review_payload("REV-VALIDATOR-INVALID-TEST")
    payload.pop("related_plan")
    artifact.write_text(json.dumps(payload), encoding="utf-8")

    markdown = artifact.with_suffix(".md")
    _write_valid_markdown(markdown)

    result = _run(str(artifact))
    assert result.returncode != 0, "Expected invalid artifact to fail repo-level validation"
    assert "FAIL" in result.stdout


def test_repo_level_validator_fails_missing_markdown_pair(tmp_path: Path) -> None:
    artifact = tmp_path / "2026-03-27-missing-markdown-pair.json"
    payload = _valid_review_payload("REV-VALIDATOR-MISSING-MD-TEST")
    artifact.write_text(json.dumps(payload), encoding="utf-8")

    result = _run(str(artifact))
    assert result.returncode != 0, "Expected missing markdown companion to fail repo-level validation"
    assert "missing markdown companion" in result.stdout
