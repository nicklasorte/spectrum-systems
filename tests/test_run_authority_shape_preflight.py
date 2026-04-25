"""CLI and logic tests for scripts/run_authority_shape_preflight.py."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys
sys.path.insert(0, str(REPO_ROOT))

import scripts.run_authority_shape_preflight as asp


def test_scan_json_clean_file(tmp_path: Path) -> None:
    f = tmp_path / "clean.json"
    f.write_text(json.dumps({
        "artifact_type": "signal_record",
        "status": "warn",
        "payload": {"signal": "observe_only"},
    }), encoding="utf-8")
    violations = asp._scan_json(f, "clean.json")
    assert violations == []


def test_scan_json_authority_artifact_type(tmp_path: Path) -> None:
    f = tmp_path / "bad.json"
    f.write_text(json.dumps({
        "artifact_type": "control_decision_record",
        "status": "warn",
    }), encoding="utf-8")
    violations = asp._scan_json(f, "bad.json")
    assert any(v["rule"] == "authority_shape_artifact_type" for v in violations)


def test_scan_json_forbidden_field(tmp_path: Path) -> None:
    f = tmp_path / "bad_field.json"
    f.write_text(json.dumps({
        "artifact_type": "signal_record",
        "decision": "observe_only",
    }), encoding="utf-8")
    violations = asp._scan_json(f, "bad_field.json")
    assert any(v["rule"] == "forbidden_field" and v["token"] == "decision" for v in violations)


def test_scan_json_forbidden_value(tmp_path: Path) -> None:
    f = tmp_path / "bad_value.json"
    f.write_text(json.dumps({
        "artifact_type": "signal_record",
        "action": "allow",
    }), encoding="utf-8")
    violations = asp._scan_json(f, "bad_value.json")
    assert any(v["rule"] == "forbidden_value" and v["token"] == "allow" for v in violations)


def test_scan_md_forbidden_field(tmp_path: Path) -> None:
    f = tmp_path / "MET-test.md"
    f.write_text("The system control decision is warn.\n", encoding="utf-8")
    violations = asp._scan_md(f, "MET-test.md")
    assert any(v["rule"] == "forbidden_field" and v["token"] == "decision" for v in violations)


def test_scan_md_forbidden_value(tmp_path: Path) -> None:
    f = tmp_path / "MET-test.md"
    f.write_text("Dashboard trust posture is BLOCK.\n", encoding="utf-8")
    violations = asp._scan_md(f, "MET-test.md")
    assert any(v["rule"] == "forbidden_value" and v["token"] == "block" for v in violations)


def test_scan_md_boundary_description_excluded(tmp_path: Path) -> None:
    f = tmp_path / "MET-test.md"
    f.write_text("CDE decides the control path.\n", encoding="utf-8")
    violations = asp._scan_md(f, "MET-test.md")
    assert violations == []


def test_scan_md_sel_enforces_excluded(tmp_path: Path) -> None:
    f = tmp_path / "MET-test.md"
    f.write_text("SEL enforces the gate policy.\n", encoding="utf-8")
    violations = asp._scan_md(f, "MET-test.md")
    assert violations == []


def test_is_boundary_description_matches() -> None:
    assert asp._is_boundary_description("CDE decides the outcome.") is True
    assert asp._is_boundary_description("SEL enforces the contract.") is True
    assert asp._is_boundary_description("TPA adjudicates the dispute.") is True
    assert asp._is_boundary_description("GOV certifies the artifact.") is True
    assert asp._is_boundary_description("PRA certifies the record.") is True


def test_is_boundary_description_no_match() -> None:
    assert asp._is_boundary_description("The control decision is warn.") is False
    assert asp._is_boundary_description("Trust posture is BLOCK.") is False


def test_extract_json_keys_values_recursive() -> None:
    payload = {"a": {"decision": "allow"}, "items": [{"certified": True, "name": "x"}]}
    keys, values = asp._extract_json_keys_values(payload)
    assert "decision" in keys
    assert "certified" in keys
    assert "allow" in values


def test_main_passes_on_repo_state(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "result.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_authority_shape_preflight.py",
            "--suggest-only",
            "--output", str(out.relative_to(REPO_ROOT)) if out.is_relative_to(REPO_ROOT) else str(out),
        ],
    )
    monkeypatch.chdir(REPO_ROOT)
    import importlib
    importlib.reload(asp)
    result = asp.main()
    assert result == 0
