"""D3L-MASTER-01 Phase 5 — alignment artifact tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import build_d3l_rank_maturity_alignment as alignment_builder


@pytest.fixture
def temp_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(alignment_builder, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(alignment_builder, "RANKING_PATH", tmp_path / "artifacts" / "tls" / "d3l_ranking_report.json")
    monkeypatch.setattr(alignment_builder, "MATURITY_PATH", tmp_path / "artifacts" / "tls" / "d3l_maturity_report.json")
    return tmp_path


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_fail_closed_when_inputs_missing(temp_repo: Path) -> None:
    report = alignment_builder.build_alignment_report()
    assert report["status"] == "fail-closed"
    assert "ranking_report_missing" in report["blocking_reasons"]
    assert "maturity_report_missing" in report["blocking_reasons"]


def test_alignment_ok_when_top3_at_lowest(temp_repo: Path) -> None:
    _write(temp_repo / "artifacts" / "tls" / "d3l_ranking_report.json", {
        "top_3": [{"system_id": "AEX"}, {"system_id": "EVL"}, {"system_id": "CDE"}],
    })
    _write(temp_repo / "artifacts" / "tls" / "d3l_maturity_report.json", {
        "rows": [
            {"system_id": "AEX", "level": 1},
            {"system_id": "EVL", "level": 1},
            {"system_id": "CDE", "level": 1},
            {"system_id": "SEL", "level": 4},
        ],
    })
    report = alignment_builder.build_alignment_report()
    assert report["status"] == "ok"
    assert report["alignment"]["ok"] is True


def test_alignment_warning_when_top3_above_lowest(temp_repo: Path) -> None:
    _write(temp_repo / "artifacts" / "tls" / "d3l_ranking_report.json", {
        "top_3": [{"system_id": "AEX"}, {"system_id": "EVL"}, {"system_id": "CDE"}],
    })
    _write(temp_repo / "artifacts" / "tls" / "d3l_maturity_report.json", {
        "rows": [
            {"system_id": "AEX", "level": 4},
            {"system_id": "EVL", "level": 4},
            {"system_id": "CDE", "level": 4},
            {"system_id": "SEL", "level": 0},
        ],
    })
    report = alignment_builder.build_alignment_report()
    assert report["alignment"]["ok"] is False
    assert "AEX" in report["alignment"]["top_3_above_lowest_maturity"]
    assert report["alignment"]["lowest_maturity_level"] == 0


def test_no_re_ranking(temp_repo: Path) -> None:
    """Alignment helper must never reorder ranking input."""
    top3_before = [{"system_id": "AEX"}, {"system_id": "EVL"}, {"system_id": "CDE"}]
    _write(temp_repo / "artifacts" / "tls" / "d3l_ranking_report.json", {"top_3": top3_before})
    _write(temp_repo / "artifacts" / "tls" / "d3l_maturity_report.json", {
        "rows": [{"system_id": "AEX", "level": 4}, {"system_id": "SEL", "level": 0}],
    })
    alignment_builder.build_alignment_report()
    # Re-read after evaluation and assert the order is unchanged.
    after = json.loads((temp_repo / "artifacts" / "tls" / "d3l_ranking_report.json").read_text())
    assert [r["system_id"] for r in after["top_3"]] == ["AEX", "EVL", "CDE"]
