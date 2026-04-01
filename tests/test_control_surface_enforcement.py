from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.control_surface_enforcement import (
    ControlSurfaceEnforcementError,
    evaluate_control_surface_enforcement,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_EXAMPLE_MANIFEST = _REPO_ROOT / "contracts" / "examples" / "control_surface_manifest.json"

_REQUIRED_SURFACES = [
    "evaluation_control_runtime",
    "replay_governance_gate",
    "sequence_transition_promotion",
    "trust_spine_invariant_validation",
    "done_certification_gate",
    "contract_preflight_gate",
]


def _required_surface_entry(surface_id: str) -> dict:
    return {
        "surface_id": surface_id,
        "surface_name": surface_id,
        "surface_category": "governance_validation",
        "owning_module": "scripts.run_contract_preflight",
        "entrypoint_function": "main",
        "decision_scope": "deterministic scope",
        "enforcement_scope": "deterministic enforcement",
        "artifact_types_consumed": ["artifact_a"],
        "artifact_types_emitted": ["artifact_b"],
        "required_refs": ["ref_a"],
        "optional_refs": [],
        "fail_closed": True,
        "promotion_blocking": True,
        "certification_blocking": True,
        "invariant_coverage": {
            "invariants_applied": ["invariant_present"],
            "invariant_source_module": "spectrum_systems.modules.runtime.trust_spine_invariants",
            "invariant_enforcement_mode": "hard_block",
            "invariant_blocking_effect": "block",
        },
        "test_coverage": {
            "covering_test_files": ["tests/test_contract_preflight.py"],
            "critical_test_names": ["test_dummy"],
            "coverage_status": "covered",
        },
    }


def _valid_manifest() -> dict:
    return {
        "artifact_type": "control_surface_manifest",
        "schema_version": "1.0.0",
        "manifest_status": "complete",
        "deterministic_build_identity": "csm-0123456789abcdef",
        "surfaces": [_required_surface_entry(surface_id) for surface_id in sorted(_REQUIRED_SURFACES)],
        "gap_signals": {
            "uncovered_surfaces": [],
            "surfaces_missing_invariants": [],
            "surfaces_missing_required_refs": [],
            "surfaces_missing_targeted_tests": [],
            "contradictory_surface_metadata": [],
        },
        "summary": {
            "total_surfaces": len(_REQUIRED_SURFACES),
            "fully_covered_surfaces": len(_REQUIRED_SURFACES),
            "partially_covered_surfaces": 0,
            "uncovered_surfaces_count": 0,
            "blocking_gaps_present": False,
        },
    }


def test_enforcement_valid_manifest_passes_and_is_deterministic() -> None:
    manifest = _valid_manifest()
    first = evaluate_control_surface_enforcement(manifest=manifest, manifest_ref="contracts/examples/control_surface_manifest.json")
    second = evaluate_control_surface_enforcement(manifest=deepcopy(manifest), manifest_ref="contracts/examples/control_surface_manifest.json")

    assert first == second
    assert first["enforcement_status"] == "PASS"
    assert first["blocking_reasons"] == []


def test_enforcement_blocks_when_required_surface_missing() -> None:
    manifest = _valid_manifest()
    manifest["surfaces"] = [s for s in manifest["surfaces"] if s["surface_id"] != "done_certification_gate"]
    manifest["summary"]["total_surfaces"] = len(manifest["surfaces"])

    result = evaluate_control_surface_enforcement(manifest=manifest, manifest_ref="manifest.json")
    assert result["enforcement_status"] == "BLOCK"
    assert "done_certification_gate" in result["missing_required_surfaces"]
    assert "REQUIRED_SURFACES_MISSING" in result["blocking_reasons"]


def test_enforcement_blocks_when_required_surface_invariants_missing() -> None:
    manifest = _valid_manifest()
    for surface in manifest["surfaces"]:
        if surface["surface_id"] == "replay_governance_gate":
            surface["invariant_coverage"]["invariants_applied"] = []
            break

    result = evaluate_control_surface_enforcement(manifest=manifest, manifest_ref="manifest.json")
    assert result["enforcement_status"] == "BLOCK"
    assert result["surfaces_missing_invariants"] == ["replay_governance_gate"]


def test_enforcement_blocks_when_required_surface_test_coverage_missing() -> None:
    manifest = _valid_manifest()
    for surface in manifest["surfaces"]:
        if surface["surface_id"] == "contract_preflight_gate":
            surface["test_coverage"]["coverage_status"] = "partially_covered"
            break

    result = evaluate_control_surface_enforcement(manifest=manifest, manifest_ref="manifest.json")
    assert result["enforcement_status"] == "BLOCK"
    assert result["surfaces_missing_test_coverage"] == ["contract_preflight_gate"]


def test_enforcement_malformed_manifest_fails_closed() -> None:
    manifest = _valid_manifest()
    manifest.pop("schema_version")
    with pytest.raises(ControlSurfaceEnforcementError, match="manifest failed schema validation"):
        evaluate_control_surface_enforcement(manifest=manifest, manifest_ref="manifest.json")


def test_cli_exits_non_zero_on_blocking_result(tmp_path: Path) -> None:
    output_manifest = tmp_path / "control_surface_manifest.json"
    output_manifest.write_text(_EXAMPLE_MANIFEST.read_text(encoding="utf-8"), encoding="utf-8")
    cmd = [
        sys.executable,
        "scripts/run_control_surface_enforcement.py",
        "--manifest",
        str(output_manifest),
        "--output-dir",
        str(tmp_path / "out"),
    ]
    proc = subprocess.run(cmd, cwd=_REPO_ROOT, capture_output=True, text=True, check=False)
    assert proc.returncode != 0
    result = json.loads((tmp_path / "out" / "control_surface_enforcement_result.json").read_text(encoding="utf-8"))
    assert result["enforcement_status"] == "BLOCK"
