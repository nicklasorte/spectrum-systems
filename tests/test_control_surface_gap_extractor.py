from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.control_surface_gap_extractor import (
    ControlSurfaceGapExtractionError,
    extract_control_surface_gaps,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_example(name: str) -> dict:
    return json.loads((_REPO_ROOT / "contracts" / "examples" / f"{name}.json").read_text(encoding="utf-8"))


def _valid_inputs() -> tuple[dict, dict, dict]:
    manifest = _load_example("control_surface_manifest")
    manifest["manifest_status"] = "complete"
    manifest["gap_signals"]["surfaces_missing_targeted_tests"] = []
    manifest["summary"]["blocking_gaps_present"] = False
    manifest["summary"]["partially_covered_surfaces"] = 0
    manifest["summary"]["uncovered_surfaces_count"] = 0
    base_surface = deepcopy(manifest["surfaces"][0])
    for surface_id in ("trust_spine_invariant_validation", "done_certification_gate", "sequence_transition_promotion"):
        cloned = deepcopy(base_surface)
        cloned["surface_id"] = surface_id
        cloned["surface_name"] = surface_id
        manifest["surfaces"].append(cloned)
    manifest["summary"]["total_surfaces"] = len(manifest["surfaces"])

    enforcement = _load_example("control_surface_enforcement_result")
    enforcement["enforcement_status"] = "PASS"
    enforcement["missing_required_surfaces"] = []
    enforcement["surfaces_missing_invariants"] = []
    enforcement["surfaces_missing_test_coverage"] = []
    enforcement["blocking_reasons"] = []
    enforcement["coverage_summary"]["blocking_gaps_present"] = False

    obedience = _load_example("control_surface_obedience_result")
    obedience["overall_decision"] = "ALLOW"
    obedience["missing_obedience_evidence"] = []
    obedience["contradictory_obedience_evidence"] = []
    obedience["blocking_reasons"] = []
    for row in obedience["surface_results"]:
        row["status"] = "PASS"
        row["runtime_obeyed"] = True
        row["missing_evidence"] = []
        row["contradictions"] = []
    return manifest, enforcement, obedience


def test_missing_test_coverage_creates_gap() -> None:
    manifest, enforcement, obedience = _valid_inputs()
    manifest["gap_signals"]["surfaces_missing_targeted_tests"] = ["contract_preflight_gate"]

    result = extract_control_surface_gaps(manifest, enforcement, obedience)
    assert result["status"] == "gaps_detected"
    assert any(g["gap_type"] == "missing_test" and g["control_surface"] == "contract_preflight_gate" for g in result["gaps"])


def test_invariant_violation_creates_gap() -> None:
    manifest, enforcement, obedience = _valid_inputs()
    enforcement["enforcement_status"] = "BLOCK"
    enforcement["surfaces_missing_invariants"] = ["contract_preflight_gate"]
    enforcement["blocking_reasons"] = ["REQUIRED_SURFACES_INVARIANTS_MISSING"]

    result = extract_control_surface_gaps(manifest, enforcement, obedience)
    assert any(g["gap_type"] == "invariant_violation" for g in result["gaps"])


def test_obedience_failure_creates_blocker_gap() -> None:
    manifest, enforcement, obedience = _valid_inputs()
    obedience["overall_decision"] = "BLOCK"
    obedience["surface_results"][0]["surface_id"] = "contract_preflight_gate"
    obedience["surface_results"][0]["status"] = "BLOCK"
    obedience["surface_results"][0]["runtime_obeyed"] = False
    obedience["blocking_reasons"] = ["contract_preflight_gate:blocked"]

    result = extract_control_surface_gaps(manifest, enforcement, obedience)
    blocker_gaps = [g for g in result["gaps"] if g["severity"] == "blocker"]
    assert blocker_gaps


def test_deduplicates_identical_gaps() -> None:
    manifest, enforcement, obedience = _valid_inputs()
    obedience["surface_results"].append(deepcopy(obedience["surface_results"][0]))
    obedience["surface_results"][0]["surface_id"] = "contract_preflight_gate"
    obedience["surface_results"][0]["status"] = "BLOCK"
    obedience["surface_results"][0]["runtime_obeyed"] = False
    obedience["surface_results"][-1]["surface_id"] = "contract_preflight_gate"
    obedience["surface_results"][-1]["status"] = "BLOCK"
    obedience["surface_results"][-1]["runtime_obeyed"] = False

    result = extract_control_surface_gaps(manifest, enforcement, obedience)
    matches = [g for g in result["gaps"] if g["gap_type"] == "obedience_missing" and g["control_surface"] == "contract_preflight_gate" and g["severity"] == "blocker"]
    assert len(matches) == 1


def test_deterministic_ids() -> None:
    manifest, enforcement, obedience = _valid_inputs()
    manifest["gap_signals"]["surfaces_missing_targeted_tests"] = ["contract_preflight_gate"]

    first = extract_control_surface_gaps(manifest, enforcement, obedience)
    second = extract_control_surface_gaps(deepcopy(manifest), deepcopy(enforcement), deepcopy(obedience))
    assert first["gap_result_id"] == second["gap_result_id"]
    assert [g["gap_id"] for g in first["gaps"]] == [g["gap_id"] for g in second["gaps"]]


def test_fail_closed_on_missing_control_surface_mapping() -> None:
    manifest, enforcement, obedience = _valid_inputs()
    enforcement["missing_required_surfaces"] = ["nonexistent_surface"]
    enforcement["enforcement_status"] = "BLOCK"

    with pytest.raises(ControlSurfaceGapExtractionError, match="mapping missing"):
        extract_control_surface_gaps(manifest, enforcement, obedience)


def test_fail_closed_on_malformed_input() -> None:
    manifest, enforcement, obedience = _valid_inputs()
    manifest.pop("schema_version")

    with pytest.raises(ControlSurfaceGapExtractionError, match="failed schema validation"):
        extract_control_surface_gaps(manifest, enforcement, obedience)
