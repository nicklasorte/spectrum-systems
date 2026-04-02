from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

from spectrum_systems.modules.runtime.control_surface_obedience import (
    ControlSurfaceObedienceError,
    evaluate_control_surface_obedience,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_EXAMPLES = _REPO_ROOT / "contracts" / "examples"

_REQUIRED_SURFACES = [
    "sequence_transition_promotion",
    "done_certification_gate",
    "trust_spine_invariant_validation",
]


def _required_surface_entry(surface_id: str) -> dict[str, Any]:
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
            "covering_test_files": ["tests/test_control_surface_obedience.py"],
            "critical_test_names": ["test_obedience_happy_path_allows"],
            "coverage_status": "covered",
        },
    }


def _manifest() -> dict[str, Any]:
    return {
        "artifact_type": "control_surface_manifest",
        "schema_version": "1.0.0",
        "manifest_status": "complete",
        "deterministic_build_identity": "csm-0123456789abcdef",
        "surfaces": [_required_surface_entry(surface_id) for surface_id in _REQUIRED_SURFACES],
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


def _enforcement() -> dict[str, Any]:
    return {
        "artifact_type": "control_surface_enforcement_result",
        "schema_version": "1.0.0",
        "manifest_ref": "manifest.json",
        "manifest_identity": "csm-0123456789abcdef",
        "enforcement_status": "PASS",
        "required_surface_policy_version": "1.0.0",
        "required_surfaces_evaluated": _REQUIRED_SURFACES,
        "missing_required_surfaces": [],
        "surfaces_missing_invariants": [],
        "surfaces_missing_test_coverage": [],
        "blocking_reasons": [],
        "coverage_summary": {
            "required_surface_count": 3,
            "required_surface_present_count": 3,
            "required_surface_invariant_covered_count": 3,
            "required_surface_test_covered_count": 3,
            "blocking_gaps_present": False,
        },
        "deterministic_enforcement_id": "cse-0123456789abcdef",
        "trace": {
            "producer": "spectrum_systems.modules.runtime.control_surface_enforcement",
            "policy_ref": "CON-030.required_surfaces.v1",
            "manifest_schema_version": "1.0.0",
        },
    }


def _done_certification() -> dict[str, Any]:
    return json.loads((_EXAMPLES / "done_certification_record.json").read_text(encoding="utf-8"))


def _promotion_decision(allowed: bool = True) -> dict[str, Any]:
    return {
        "target_state": "promoted",
        "allowed": allowed,
        "reason": "deterministic-test",
        "consumed_signals": [
            "trust_spine_invariant_validation",
            "done_certification_gate",
        ],
    }


def _invariant_result(passed: bool = True) -> dict[str, Any]:
    return {
        "passed": passed,
        "blocking_reasons": [] if passed else ["TRUST_SPINE_THRESHOLD_CONTEXT_MISMATCH"],
    }


def test_obedience_happy_path_allows() -> None:
    result = evaluate_control_surface_obedience(
        manifest=_manifest(),
        manifest_ref="manifest.json",
        enforcement_result=_enforcement(),
        enforcement_result_ref="enforcement.json",
        invariant_result=_invariant_result(True),
        invariant_result_ref="invariant.json",
        done_certification_record=_done_certification(),
        done_certification_ref="done_certification.json",
        promotion_decision=_promotion_decision(True),
        promotion_decision_ref="promotion.json",
    )
    assert result["overall_decision"] == "ALLOW"
    assert result["blocking_reasons"] == []


def test_invariant_contradiction_blocks_when_downstream_allows() -> None:
    done = _done_certification()
    done["final_status"] = "PASSED"
    done["system_response"] = "allow"
    result = evaluate_control_surface_obedience(
        manifest=_manifest(),
        manifest_ref="manifest.json",
        enforcement_result=_enforcement(),
        enforcement_result_ref="enforcement.json",
        invariant_result=_invariant_result(False),
        invariant_result_ref="invariant.json",
        done_certification_record=done,
        done_certification_ref="done_certification.json",
        promotion_decision=_promotion_decision(True),
        promotion_decision_ref="promotion.json",
    )
    assert result["overall_decision"] == "BLOCK"
    assert any("invariant failed" in reason for reason in result["blocking_reasons"])


def test_promotion_contradiction_blocks() -> None:
    done = _done_certification()
    done["final_status"] = "FAILED"
    done["system_response"] = "block"
    done["blocking_reasons"] = ["regression failed"]
    result = evaluate_control_surface_obedience(
        manifest=_manifest(),
        manifest_ref="manifest.json",
        enforcement_result=_enforcement(),
        enforcement_result_ref="enforcement.json",
        invariant_result=_invariant_result(True),
        invariant_result_ref="invariant.json",
        done_certification_record=done,
        done_certification_ref="done_certification.json",
        promotion_decision=_promotion_decision(True),
        promotion_decision_ref="promotion.json",
    )
    assert result["overall_decision"] == "BLOCK"
    assert any("promotion allowed despite failed done certification" in reason for reason in result["blocking_reasons"])


def test_missing_evidence_fails_closed() -> None:
    promotion = _promotion_decision(True)
    promotion.pop("consumed_signals")
    result = evaluate_control_surface_obedience(
        manifest=_manifest(),
        manifest_ref="manifest.json",
        enforcement_result=_enforcement(),
        enforcement_result_ref="enforcement.json",
        invariant_result=_invariant_result(True),
        invariant_result_ref="invariant.json",
        done_certification_record=_done_certification(),
        done_certification_ref="done_certification.json",
        promotion_decision=promotion,
        promotion_decision_ref="promotion.json",
    )
    assert result["overall_decision"] == "BLOCK"
    assert any("missing" in reason for reason in result["blocking_reasons"])


def test_malformed_input_fails_closed() -> None:
    with pytest.raises(ControlSurfaceObedienceError, match="failed schema validation"):
        bad_manifest = _manifest()
        bad_manifest.pop("schema_version")
        evaluate_control_surface_obedience(
            manifest=bad_manifest,
            manifest_ref="manifest.json",
            enforcement_result=_enforcement(),
            enforcement_result_ref="enforcement.json",
            invariant_result=_invariant_result(True),
            invariant_result_ref="invariant.json",
            done_certification_record=_done_certification(),
            done_certification_ref="done_certification.json",
            promotion_decision=_promotion_decision(True),
            promotion_decision_ref="promotion.json",
        )


def test_cli_exit_non_zero_on_block(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    enforcement_path = tmp_path / "enforcement.json"
    invariant_path = tmp_path / "invariant.json"
    done_path = tmp_path / "done.json"
    promotion_path = tmp_path / "promotion.json"
    manifest_path.write_text(json.dumps(_manifest()), encoding="utf-8")
    enforcement_path.write_text(json.dumps(_enforcement()), encoding="utf-8")
    invariant_path.write_text(json.dumps(_invariant_result(False)), encoding="utf-8")
    done_path.write_text(json.dumps(_done_certification()), encoding="utf-8")
    promotion_path.write_text(json.dumps(_promotion_decision(True)), encoding="utf-8")

    cmd = [
        sys.executable,
        "scripts/run_control_surface_obedience.py",
        "--manifest",
        str(manifest_path),
        "--enforcement-result",
        str(enforcement_path),
        "--invariant-result",
        str(invariant_path),
        "--done-certification",
        str(done_path),
        "--promotion-decision",
        str(promotion_path),
        "--output-dir",
        str(tmp_path / "out"),
    ]
    proc = subprocess.run(cmd, cwd=_REPO_ROOT, capture_output=True, text=True, check=False)
    assert proc.returncode == 2
    result = json.loads((tmp_path / "out" / "control_surface_obedience_result.json").read_text(encoding="utf-8"))
    assert result["overall_decision"] == "BLOCK"
