"""D3L-MASTER-01 Phase 1 — priority freshness gate artifact tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import build_d3l_priority_freshness_gate as gate_builder

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture
def temp_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(gate_builder, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        gate_builder, "PRIORITY_PATH",
        tmp_path / "artifacts" / "system_dependency_priority_report.json",
    )
    monkeypatch.setattr(
        gate_builder, "PRIORITY_TLS_PATH",
        tmp_path / "artifacts" / "tls" / "system_dependency_priority_report.json",
    )
    monkeypatch.setattr(
        gate_builder, "CONTRACT_PATH",
        tmp_path / "artifacts" / "tls" / "d3l_registry_contract.json",
    )
    return tmp_path


def _valid_priority(generated_at: str = "2026-04-28T07:30:00Z") -> dict:
    return {
        "schema_version": "tls-04.v1",
        "phase": "TLS-04",
        "ranked_systems": [],
        "global_ranked_systems": [
            {"system_id": "EVL"}, {"system_id": "CDE"},
        ],
        "top_5": [{"system_id": "EVL"}, {"system_id": "CDE"}],
        "requested_candidate_ranking": [],
        "generated_at": generated_at,
    }


def _valid_contract() -> dict:
    return {
        "artifact_type": "d3l_registry_contract",
        "phase": "D3L-MASTER-01",
        "schema_version": "d3l-master-01.v1",
        "active_system_ids": ["EVL", "CDE", "TPA"],
        "ranking_universe": ["EVL", "CDE", "TPA"],
        "maturity_universe": ["EVL", "CDE", "TPA"],
        "future_system_ids": [],
        "deprecated_or_merged_system_ids": [],
        "excluded_ids": [],
        "forbidden_node_examples": ["H01"],
        "rules": [],
    }


def test_gate_ok_when_artifact_fresh(temp_repo: Path) -> None:
    _write(temp_repo / "artifacts" / "system_dependency_priority_report.json", _valid_priority())
    _write(temp_repo / "artifacts" / "tls" / "d3l_registry_contract.json", _valid_contract())
    gate = gate_builder.build_gate(now_iso="2026-04-28T08:00:00Z", stale_hours=24)
    assert gate["status"] == "ok"
    assert gate["blocking_reasons"] == []
    assert gate["checks"]["valid_json"] is True
    assert gate["checks"]["schema_valid"] is True
    assert gate["checks"]["freshness"]["stale"] is False
    assert gate["checks"]["ranking_universe"]["ok"] is True


def test_gate_missing_artifact(temp_repo: Path) -> None:
    _write(temp_repo / "artifacts" / "tls" / "d3l_registry_contract.json", _valid_contract())
    gate = gate_builder.build_gate(now_iso="2026-04-28T08:00:00Z", stale_hours=24)
    assert gate["status"] == "fail-closed"
    assert "priority_artifact_missing" in gate["blocking_reasons"]


def test_gate_stale_2018(temp_repo: Path) -> None:
    _write(
        temp_repo / "artifacts" / "system_dependency_priority_report.json",
        _valid_priority(generated_at="2018-01-01T00:00:00Z"),
    )
    _write(temp_repo / "artifacts" / "tls" / "d3l_registry_contract.json", _valid_contract())
    gate = gate_builder.build_gate(now_iso="2026-04-28T08:00:00Z", stale_hours=24)
    assert gate["status"] == "fail-closed"
    assert any("older_than_24h" in r for r in gate["blocking_reasons"])


def test_gate_invalid_json(temp_repo: Path) -> None:
    p = temp_repo / "artifacts" / "system_dependency_priority_report.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("not-json", encoding="utf-8")
    _write(temp_repo / "artifacts" / "tls" / "d3l_registry_contract.json", _valid_contract())
    gate = gate_builder.build_gate(now_iso="2026-04-28T08:00:00Z", stale_hours=24)
    assert gate["checks"]["valid_json"] is False
    assert gate["status"] == "fail-closed"


def test_gate_non_active_in_top5(temp_repo: Path) -> None:
    bad = _valid_priority()
    bad["top_5"] = [{"system_id": "H01"}]
    _write(temp_repo / "artifacts" / "system_dependency_priority_report.json", bad)
    _write(temp_repo / "artifacts" / "tls" / "d3l_registry_contract.json", _valid_contract())
    gate = gate_builder.build_gate(now_iso="2026-04-28T08:00:00Z", stale_hours=24)
    assert gate["status"] == "fail-closed"
    assert any("non_active_in_top_5" in r for r in gate["blocking_reasons"])
