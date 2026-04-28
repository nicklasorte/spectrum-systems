"""D3L-MASTER-01 Phase 6 — MVP graph artifact tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import build_d3l_mvp_graph as builder


@pytest.fixture
def temp_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(builder, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(builder, "CONTRACT_PATH", tmp_path / "artifacts" / "tls" / "d3l_registry_contract.json")
    return tmp_path


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _full_contract() -> dict:
    return {
        "active_system_ids": [
            "AEX", "PQX", "EVL", "TPA", "CDE", "SEL", "CTX", "PRM",
            "HOP", "JDX", "JSX", "FRE", "RIL", "RAX", "OBS", "SLO",
        ],
        "ranking_universe": [],
        "maturity_universe": [],
    }


def test_no_warnings_when_contract_full(temp_repo: Path) -> None:
    _write(temp_repo / "artifacts" / "tls" / "d3l_registry_contract.json", _full_contract())
    report = builder.build_mvp_graph_report()
    assert report["warnings"] == []
    for v in report["validated_mappings"]:
        assert v["rejected_systems"] == []


def test_warning_when_contract_partial(temp_repo: Path) -> None:
    _write(temp_repo / "artifacts" / "tls" / "d3l_registry_contract.json", {
        "active_system_ids": ["AEX", "EVL"],
    })
    report = builder.build_mvp_graph_report()
    assert any(w.startswith("mvp_box_rejected_mapping") for w in report["warnings"])


def test_warning_when_contract_missing(temp_repo: Path) -> None:
    report = builder.build_mvp_graph_report()
    assert "mvp_graph_contract_missing" in report["warnings"]


def test_mvp_box_ids_disjoint_from_system_ids(temp_repo: Path) -> None:
    _write(temp_repo / "artifacts" / "tls" / "d3l_registry_contract.json", _full_contract())
    report = builder.build_mvp_graph_report()
    box_ids = {b["id"] for b in report["boxes"]}
    contract = json.loads((temp_repo / "artifacts" / "tls" / "d3l_registry_contract.json").read_text())
    active_ids = set(contract["active_system_ids"])
    assert box_ids.isdisjoint(active_ids)


def test_edges_reference_defined_boxes(temp_repo: Path) -> None:
    _write(temp_repo / "artifacts" / "tls" / "d3l_registry_contract.json", _full_contract())
    report = builder.build_mvp_graph_report()
    box_ids = {b["id"] for b in report["boxes"]}
    for e in report["edges"]:
        assert e["from"] in box_ids
        assert e["to"] in box_ids
