"""D3L-MASTER-01 Phase 4 — maturity report tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import build_d3l_maturity_report as builder

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def temp_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(builder, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(builder, "CONTRACT_PATH", tmp_path / "artifacts" / "tls" / "d3l_registry_contract.json")
    monkeypatch.setattr(builder, "EVIDENCE_PATH", tmp_path / "artifacts" / "tls" / "system_evidence_attachment.json")
    monkeypatch.setattr(builder, "TRUST_GAP_PATH", tmp_path / "artifacts" / "tls" / "system_trust_gap_report.json")
    monkeypatch.setattr(builder, "FRESHNESS_GATE_PATH", tmp_path / "artifacts" / "tls" / "d3l_priority_freshness_gate.json")
    return tmp_path


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _contract(active: list[str]) -> dict:
    return {
        "artifact_type": "d3l_registry_contract",
        "phase": "D3L-MASTER-01",
        "schema_version": "d3l-master-01.v1",
        "active_system_ids": active,
        "future_system_ids": [],
        "deprecated_or_merged_system_ids": [],
        "excluded_ids": [],
        "ranking_universe": active,
        "maturity_universe": active,
        "forbidden_node_examples": [],
        "rules": [],
    }


def test_fail_closed_when_contract_missing(temp_repo: Path) -> None:
    report = builder.build_maturity_report()
    assert report["status"] == "fail-closed"
    assert "contract_missing" in report["blocking_reasons"]


def test_all_active_systems_have_rows(temp_repo: Path) -> None:
    active = ["AEX", "EVL", "CDE", "SEL"]
    _write(temp_repo / "artifacts" / "tls" / "d3l_registry_contract.json", _contract(active))
    _write(temp_repo / "artifacts" / "tls" / "system_evidence_attachment.json", {
        "systems": [{"system_id": sid, "has_evidence": True, "evidence_count": 50} for sid in active],
    })
    _write(temp_repo / "artifacts" / "tls" / "system_trust_gap_report.json", {
        "systems": [{"system_id": sid, "trust_state": "ready_signal", "failing_signals": []} for sid in active],
    })
    _write(temp_repo / "artifacts" / "tls" / "d3l_priority_freshness_gate.json", {"status": "ok"})
    report = builder.build_maturity_report()
    assert report["status"] == "ok"
    assert len(report["rows"]) == len(active)
    assert all(row["level"] == 4 for row in report["rows"])


def test_missing_evidence_drops_to_level_0(temp_repo: Path) -> None:
    active = ["AEX"]
    _write(temp_repo / "artifacts" / "tls" / "d3l_registry_contract.json", _contract(active))
    _write(temp_repo / "artifacts" / "tls" / "system_evidence_attachment.json", {"systems": []})
    _write(temp_repo / "artifacts" / "tls" / "system_trust_gap_report.json", {"systems": []})
    _write(temp_repo / "artifacts" / "tls" / "d3l_priority_freshness_gate.json", {"status": "ok"})
    report = builder.build_maturity_report()
    aex = report["rows"][0]
    assert aex["level"] == 0
    assert aex["level_label"] == "Unknown"


def test_stale_freshness_caps_at_level_3(temp_repo: Path) -> None:
    active = ["AEX"]
    _write(temp_repo / "artifacts" / "tls" / "d3l_registry_contract.json", _contract(active))
    _write(temp_repo / "artifacts" / "tls" / "system_evidence_attachment.json", {
        "systems": [{"system_id": "AEX", "has_evidence": True, "evidence_count": 99}],
    })
    _write(temp_repo / "artifacts" / "tls" / "system_trust_gap_report.json", {
        "systems": [{"system_id": "AEX", "trust_state": "ready_signal", "failing_signals": []}],
    })
    _write(temp_repo / "artifacts" / "tls" / "d3l_priority_freshness_gate.json", {"status": "fail-closed"})
    report = builder.build_maturity_report()
    aex = report["rows"][0]
    assert aex["level"] == 3
    assert report["staleness_caps_applied"] >= 1


def test_two_structural_failures_drop_to_level_1(temp_repo: Path) -> None:
    active = ["EVL"]
    _write(temp_repo / "artifacts" / "tls" / "d3l_registry_contract.json", _contract(active))
    _write(temp_repo / "artifacts" / "tls" / "system_evidence_attachment.json", {
        "systems": [{"system_id": "EVL", "has_evidence": True, "evidence_count": 99}],
    })
    _write(temp_repo / "artifacts" / "tls" / "system_trust_gap_report.json", {
        "systems": [{
            "system_id": "EVL", "trust_state": "freeze_signal",
            "failing_signals": ["missing_lineage", "missing_observability", "missing_enforcement_signal"],
        }],
    })
    _write(temp_repo / "artifacts" / "tls" / "d3l_priority_freshness_gate.json", {"status": "ok"})
    report = builder.build_maturity_report()
    evl = report["rows"][0]
    assert evl["level"] == 1
    assert evl["key_gap"] == "missing_enforcement_signal"
