"""D3L-MASTER-01 Phase 3 — ranking report tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import build_d3l_ranking_report as ranking_builder

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def temp_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(ranking_builder, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        ranking_builder, "PRIORITY_PATH",
        tmp_path / "artifacts" / "system_dependency_priority_report.json",
    )
    monkeypatch.setattr(
        ranking_builder, "PRIORITY_TLS_PATH",
        tmp_path / "artifacts" / "tls" / "system_dependency_priority_report.json",
    )
    monkeypatch.setattr(
        ranking_builder, "CONTRACT_PATH",
        tmp_path / "artifacts" / "tls" / "d3l_registry_contract.json",
    )
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
        "future_system_ids": ["ABX"],
        "deprecated_or_merged_system_ids": ["HNX"],
        "excluded_ids": ["ABX", "HNX"],
        "ranking_universe": active,
        "maturity_universe": active,
        "forbidden_node_examples": ["H01"],
        "rules": [],
    }


def _priority(rows: list[dict]) -> dict:
    return {
        "schema_version": "tls-04.v1",
        "phase": "TLS-04",
        "ranked_systems": [],
        "global_ranked_systems": rows,
        "top_5": rows[:5],
        "requested_candidate_ranking": [],
        "generated_at": "2026-04-28T07:00:00Z",
    }


def test_fail_closed_when_priority_missing(temp_repo: Path) -> None:
    _write(temp_repo / "artifacts" / "tls" / "d3l_registry_contract.json", _contract(["EVL"]))
    report = ranking_builder.build_ranking_report()
    assert report["status"] == "fail-closed"
    assert "priority_artifact_missing" in report["blocking_reasons"]


def test_fail_closed_when_contract_missing(temp_repo: Path) -> None:
    _write(
        temp_repo / "artifacts" / "system_dependency_priority_report.json",
        _priority([{"system_id": "EVL", "rank": 1}]),
    )
    report = ranking_builder.build_ranking_report()
    assert report["status"] == "fail-closed"
    assert "contract_missing" in report["blocking_reasons"]


def test_excludes_non_active_and_includes_missing(temp_repo: Path) -> None:
    active = ["EVL", "CDE", "TPA", "SEL"]
    rows = [
        {"system_id": "EVL", "rank": 1},
        {"system_id": "H01", "rank": 2},
        {"system_id": "ABX", "rank": 3},
        {"system_id": "CDE", "rank": 4},
        {"system_id": "HNX", "rank": 5},
    ]
    _write(temp_repo / "artifacts" / "system_dependency_priority_report.json", _priority(rows))
    _write(temp_repo / "artifacts" / "tls" / "d3l_registry_contract.json", _contract(active))
    report = ranking_builder.build_ranking_report()
    assert report["status"] == "ok"
    assert report["excluded_from_priority"] == ["H01", "ABX", "HNX"]
    full_ids = [r["system_id"] for r in report["full"]]
    assert full_ids[:2] == ["EVL", "CDE"]
    assert "TPA" in full_ids and "SEL" in full_ids
    missing = [r for r in report["full"] if not r["is_in_priority_artifact"]]
    assert sorted(r["system_id"] for r in missing) == ["SEL", "TPA"]


def test_top3_top10_are_slices(temp_repo: Path) -> None:
    active = [f"S{n}" for n in range(15)]
    rows = [{"system_id": sid, "rank": i + 1} for i, sid in enumerate(active[:12])]
    _write(temp_repo / "artifacts" / "system_dependency_priority_report.json", _priority(rows))
    _write(temp_repo / "artifacts" / "tls" / "d3l_registry_contract.json", _contract(active))
    report = ranking_builder.build_ranking_report()
    assert [r["system_id"] for r in report["top_3"]] == active[:3]
    assert [r["system_id"] for r in report["top_10"]] == active[:10]
