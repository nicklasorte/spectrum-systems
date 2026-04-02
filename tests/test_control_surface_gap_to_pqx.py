from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.control_surface_gap_to_pqx import (
    ControlSurfaceGapToPQXError,
    convert_gaps_to_pqx_work_items,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_gap_result() -> dict:
    return json.loads((_REPO_ROOT / "contracts" / "examples" / "control_surface_gap_result.json").read_text(encoding="utf-8"))


def test_pqx_conversion_correctness() -> None:
    gap_result = _load_gap_result()
    work_items = convert_gaps_to_pqx_work_items(gap_result)

    assert len(work_items) == len(gap_result["gaps"])
    for item in work_items:
        assert item["work_item_id"].startswith("PQX-WORK-")
        assert item["control_surface"]
        assert item["required_action_type"]
        assert item["source_artifact_refs"]


def test_deterministic_work_item_ids() -> None:
    gap_result = _load_gap_result()
    first = convert_gaps_to_pqx_work_items(gap_result)
    second = convert_gaps_to_pqx_work_items(gap_result)

    assert [row["work_item_id"] for row in first] == [row["work_item_id"] for row in second]


def test_ok_status_returns_empty_items() -> None:
    gap_result = _load_gap_result()
    gap_result["status"] = "ok"
    gap_result["gaps"] = []

    assert convert_gaps_to_pqx_work_items(gap_result) == []


def test_fail_closed_on_malformed_gap_result() -> None:
    gap_result = _load_gap_result()
    gap_result.pop("gap_result_id")

    with pytest.raises(ControlSurfaceGapToPQXError, match="schema validation"):
        convert_gaps_to_pqx_work_items(gap_result)


def test_fail_closed_on_status_gap_mismatch() -> None:
    gap_result = _load_gap_result()
    gap_result["status"] = "ok"

    with pytest.raises(ControlSurfaceGapToPQXError, match="status=ok"):
        convert_gaps_to_pqx_work_items(gap_result)
