from __future__ import annotations

from spectrum_systems.modules.runtime.rmp.rmp_dependency_validator import validate_dependency_graph
from spectrum_systems.modules.runtime.rmp.rmp_status_realizer import realize_status


def test_status_requires_evidence() -> None:
    result = realize_status({"batch_id": "LOOP-09", "status": "implemented"}, {"code": False, "tests": False, "artifacts": False})
    assert not result["ok"]
    assert "status_without_code" in result["reason_codes"]


def test_dependency_engine_detects_missing_and_cycle() -> None:
    result = validate_dependency_graph(
        [
            {"batch_id": "A", "depends_on": ["B"]},
            {"batch_id": "B", "depends_on": ["A"]},
            {"batch_id": "C"},
        ]
    )
    assert not result["ok"]
    assert any(code.startswith("circular_dependency") for code in result["reason_codes"])
    assert "missing_depends_on:C" in result["reason_codes"]
