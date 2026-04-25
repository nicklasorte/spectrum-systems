"""Tests verifying authority shape violations include actionable repair guidance.

When the preflight finds a violation, the message field must contain enough
context for a developer to understand what to rename or replace. These tests
verify that the violation schema is consistent and informative by injecting
known-bad artifacts into the scanner.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

import sys
sys.path.insert(0, str(REPO_ROOT))

import scripts.run_authority_shape_preflight as asp


def _make_artifact(tmp_path: Path, name: str, payload: dict) -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_authority_shape_violation_has_message(tmp_path: Path) -> None:
    f = _make_artifact(tmp_path, "bad.json", {"artifact_type": "control_decision_record"})
    violations = asp._scan_json(f, "bad.json")
    assert len(violations) > 0
    for v in violations:
        assert "message" in v and len(v["message"]) > 0


def test_authority_shape_violation_message_suggests_signal_vocabulary(tmp_path: Path) -> None:
    f = _make_artifact(tmp_path, "bad.json", {"artifact_type": "control_decision_record"})
    violations = asp._scan_json(f, "bad.json")
    shape_violations = [v for v in violations if v["rule"] == "authority_shape_artifact_type"]
    assert shape_violations, "expected at least one authority_shape_artifact_type violation"
    assert "signal/observation" in shape_violations[0]["message"]


def test_forbidden_field_violation_names_the_field(tmp_path: Path) -> None:
    f = _make_artifact(tmp_path, "bad.json", {
        "artifact_type": "signal_record",
        "decision": "observe_only",
    })
    violations = asp._scan_json(f, "bad.json")
    field_violations = [v for v in violations if v["rule"] == "forbidden_field"]
    assert field_violations
    assert field_violations[0]["token"] == "decision"
    assert "decision" in field_violations[0]["message"]


def test_forbidden_value_violation_names_the_value(tmp_path: Path) -> None:
    f = _make_artifact(tmp_path, "bad.json", {
        "artifact_type": "signal_record",
        "status": "allow",
    })
    violations = asp._scan_json(f, "bad.json")
    value_violations = [v for v in violations if v["rule"] == "forbidden_value"]
    assert value_violations
    assert value_violations[0]["token"] == "allow"
    assert "allow" in value_violations[0]["message"]


def test_md_violation_includes_context_snippet(tmp_path: Path) -> None:
    f = tmp_path / "MET-test.md"
    line = "The system control decision is blocked by the policy gate."
    f.write_text(line + "\n", encoding="utf-8")
    violations = asp._scan_md(f, "MET-test.md")
    assert len(violations) > 0
    for v in violations:
        assert "context" in v
        assert len(v["context"]) > 0


def test_md_violation_includes_line_number(tmp_path: Path) -> None:
    f = tmp_path / "MET-test.md"
    f.write_text("# Header\n\nThe control decision is warn.\n", encoding="utf-8")
    violations = asp._scan_md(f, "MET-test.md")
    assert len(violations) > 0
    for v in violations:
        assert "line" in v
        assert isinstance(v["line"], int)
        assert v["line"] > 0


def test_repair_path_uses_signal_vocabulary(tmp_path: Path) -> None:
    """Renamed artifacts in current repo state must not trigger violations."""
    for name, payload in [
        ("control_signal_record.json", {
            "artifact_type": "control_signal_record",
            "payload": {"signal": "observe_only"},
        }),
        ("trust_policy_signal_record.json", {
            "artifact_type": "trust_policy_signal_record",
            "payload": {"trust_signal": "warn"},
        }),
        ("sel_signal_record.json", {
            "artifact_type": "sel_signal_record",
            "payload": {"action": "observe_only"},
        }),
    ]:
        f = _make_artifact(tmp_path, name, payload)
        violations = asp._scan_json(f, name)
        assert violations == [], (
            f"{name} should produce no violations but got: {violations}"
        )


def test_enforcement_prefix_still_triggers_violation(tmp_path: Path) -> None:
    f = _make_artifact(tmp_path, "bad.json", {"artifact_type": "enforcement_action_record"})
    violations = asp._scan_json(f, "bad.json")
    assert any(v["rule"] == "authority_shape_artifact_type" for v in violations)
