"""Tests for governed prompt queue repair prompt generation and queue attachment."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import load_example
from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    Priority,
    RepairPromptGenerationError,
    RiskLevel,
    WorkItemStatus,
    attach_repair_prompt_to_work_item,
    generate_repair_prompt_artifact,
    make_work_item,
    validate_repair_prompt_artifact,
)
from spectrum_systems.modules.prompt_queue.findings_artifact_io import FindingsArtifactValidationError  # noqa: E402


class FixedClock:
    def __init__(self, values: list[str]):
        self._values = [datetime.fromisoformat(v.replace("Z", "+00:00")) for v in values]

    def __call__(self):
        if not self._values:
            return datetime(2026, 3, 22, 0, 0, 0, tzinfo=timezone.utc)
        return self._values.pop(0)


def _work_item(status: WorkItemStatus = WorkItemStatus.FINDINGS_PARSED) -> dict:
    item = make_work_item(
        work_item_id="wi-001",
        prompt_id="prompt-gpq-001",
        title="Repair prompt generation",
        priority=Priority.HIGH,
        risk_level=RiskLevel.HIGH,
        repo="spectrum-systems",
        branch="feature/repair-prompt",
        scope_paths=["spectrum_systems/modules/prompt_queue"],
        clock=FixedClock(["2026-03-22T00:00:00Z"]),
    )
    item["status"] = status.value
    return item


def _fail_findings() -> dict:
    findings = load_example("prompt_queue_review_findings")
    findings["review_decision"] = "FAIL"
    findings["required_fixes"] = [
        {
            "finding_id": "required_fixes-1",
            "summary": "Fix required path",
            "body": "Apply deterministic fix in `spectrum_systems/modules/prompt_queue/findings_queue_integration.py`.",
            "severity": "high",
            "file_references": [
                "spectrum_systems/modules/prompt_queue/findings_queue_integration.py",
                "tests/test_prompt_queue_review_parsing.py",
            ],
            "source_section": "required_fixes",
        }
    ]
    findings["optional_improvements"] = [
        {
            "finding_id": "optional_improvements-1",
            "summary": "Optional cleanup",
            "body": "Defer optional cleanup to a follow-up patch.",
            "severity": "low",
            "file_references": ["spectrum_systems/modules/prompt_queue/review_parser.py"],
            "source_section": "optional_improvements",
        }
    ]
    return findings


def test_fail_findings_generate_valid_repair_prompt_artifact():
    artifact = generate_repair_prompt_artifact(
        work_item=_work_item(),
        findings_artifact=_fail_findings(),
        source_findings_artifact_path="artifacts/prompt_queue/findings/wi-001.findings.json",
        clock=FixedClock(["2026-03-22T00:10:00Z"]),
    )
    validate_repair_prompt_artifact(artifact)
    assert artifact["prompt_generation_status"] == "generated"
    assert artifact["review_decision"] == "FAIL"


def test_pass_findings_do_not_generate_repair_prompt_artifact():
    findings = _fail_findings()
    findings["review_decision"] = "PASS"
    with pytest.raises(RepairPromptGenerationError):
        generate_repair_prompt_artifact(
            work_item=_work_item(),
            findings_artifact=findings,
            source_findings_artifact_path="artifacts/prompt_queue/findings/wi-001.findings.json",
            clock=FixedClock(["2026-03-22T00:10:00Z"]),
        )


def test_malformed_findings_artifact_fails_closed():
    findings = _fail_findings()
    findings.pop("required_fixes")
    with pytest.raises(FindingsArtifactValidationError):
        generate_repair_prompt_artifact(
            work_item=_work_item(),
            findings_artifact=findings,
            source_findings_artifact_path="artifacts/prompt_queue/findings/wi-001.findings.json",
            clock=FixedClock(["2026-03-22T00:10:00Z"]),
        )


def test_provider_metadata_is_preserved_in_repair_prompt_artifact():
    findings = _fail_findings()
    findings["review_provider"] = "codex"
    findings["fallback_used"] = True
    findings["fallback_reason"] = "usage_limit"

    artifact = generate_repair_prompt_artifact(
        work_item=_work_item(),
        findings_artifact=findings,
        source_findings_artifact_path="artifacts/prompt_queue/findings/wi-001.findings.json",
        clock=FixedClock(["2026-03-22T00:10:00Z"]),
    )

    assert artifact["review_provider"] == "codex"
    assert artifact["fallback_used"] is True
    assert artifact["fallback_reason"] == "usage_limit"


def test_required_fixes_are_prioritized_over_optional_improvements():
    artifact = generate_repair_prompt_artifact(
        work_item=_work_item(),
        findings_artifact=_fail_findings(),
        source_findings_artifact_path="artifacts/prompt_queue/findings/wi-001.findings.json",
        clock=FixedClock(["2026-03-22T00:10:00Z"]),
    )

    required_idx = artifact["prompt_text"].find("Required fixes")
    optional_idx = artifact["prompt_text"].find("Not in scope")
    assert required_idx >= 0
    assert optional_idx >= 0
    assert required_idx < optional_idx
    assert "optional_improvements-1" in "\n".join(artifact["bounded_not_in_scope"])


def test_generated_prompt_includes_bounded_sections():
    artifact = generate_repair_prompt_artifact(
        work_item=_work_item(),
        findings_artifact=_fail_findings(),
        source_findings_artifact_path="artifacts/prompt_queue/findings/wi-001.findings.json",
        clock=FixedClock(["2026-03-22T00:10:00Z"]),
    )

    for section in (
        "Motivation",
        "Scope",
        "Required fixes",
        "Likely files involved",
        "Tests to run",
        "Implementation constraints",
        "Not in scope",
        "Mandatory delivery contract",
    ):
        assert section in artifact["prompt_text"]


def test_queue_work_item_update_occurs_after_successful_generation():
    artifact = generate_repair_prompt_artifact(
        work_item=_work_item(),
        findings_artifact=_fail_findings(),
        source_findings_artifact_path="artifacts/prompt_queue/findings/wi-001.findings.json",
        clock=FixedClock(["2026-03-22T00:10:00Z"]),
    )
    updated = attach_repair_prompt_to_work_item(
        _work_item(),
        repair_prompt_artifact_path="artifacts/prompt_queue/repair_prompts/wi-001.repair_prompt.json",
        clock=FixedClock(["2026-03-22T00:10:01Z"]),
    )

    assert artifact["repair_prompt_artifact_id"].startswith("repair-prompt-wi-001")
    assert updated["repair_prompt_artifact_path"].endswith("wi-001.repair_prompt.json")
    assert updated["status"] == WorkItemStatus.REPAIR_PROMPT_GENERATED.value


def test_repair_prompt_artifact_example_validates_against_schema():
    validate_repair_prompt_artifact(load_example("prompt_queue_repair_prompt"))
