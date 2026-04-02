from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.control_surface_enforcement import evaluate_control_surface_enforcement
from spectrum_systems.modules.runtime.control_surface_manifest import build_control_surface_manifest
from spectrum_systems.modules.runtime.trust_spine_evidence_cohesion import (
    TrustSpineEvidenceCohesionError,
    evaluate_trust_spine_evidence_cohesion,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _base_inputs() -> tuple[dict, dict[str, str]]:
    manifest = build_control_surface_manifest()
    enforcement = evaluate_control_surface_enforcement(manifest=manifest, manifest_ref="manifest.json")
    enforcement["enforcement_status"] = "PASS"
    enforcement["blocking_reasons"] = []

    obedience = json.loads((_REPO_ROOT / "contracts" / "examples" / "control_surface_obedience_result.json").read_text(encoding="utf-8"))
    obedience["manifest_ref"] = "manifest.json"
    obedience["manifest_identity"] = manifest["deterministic_build_identity"]
    obedience["enforcement_result_ref"] = "enforcement.json"
    obedience["enforcement_result_id"] = enforcement["deterministic_enforcement_id"]
    obedience["evaluated_surfaces"] = [
        "sequence_transition_promotion",
        "done_certification_gate",
        "trust_spine_invariant_validation",
    ]
    obedience["surface_results"] = [
        {
            "surface_id": sid,
            "declared_in_manifest": True,
            "required_by_enforcement": True,
            "runtime_obeyed": True,
            "status": "PASS",
            "evidence_refs": ["manifest.json", "enforcement.json", "invariant.json", "done.json"],
            "missing_evidence": [],
            "contradictions": [],
        }
        for sid in obedience["evaluated_surfaces"]
    ]
    obedience["overall_decision"] = "ALLOW"
    obedience["blocking_reasons"] = []
    obedience["missing_obedience_evidence"] = []
    obedience["contradictory_obedience_evidence"] = []

    invariant_result = {
        "passed": True,
        "blocking_reasons": [],
        "categories_checked": ["threshold_context_consistency"],
        "evaluated_surfaces": {"target_surface": "certification"},
    }

    done = json.loads((_REPO_ROOT / "contracts" / "examples" / "done_certification_record.json").read_text(encoding="utf-8"))
    done["input_refs"]["enforcement_result_ref"] = "enforcement.json"
    done["input_refs"]["trust_spine_evidence_cohesion_result_ref"] = "cohesion.json"
    done["final_status"] = "PASSED"
    done["system_response"] = "allow"
    done["blocking_reasons"] = []
    done["trust_spine_evidence_completeness_result"]["authority_path_mode"] = "active_runtime"

    artifacts = {
        "manifest": manifest,
        "enforcement_result": enforcement,
        "obedience_result": obedience,
        "invariant_result": invariant_result,
        "done_certification_record": done,
    }
    refs = {
        "manifest_ref": "manifest.json",
        "enforcement_result_ref": "enforcement.json",
        "obedience_result_ref": "obedience.json",
        "invariant_result_ref": "invariant.json",
        "done_certification_ref": "done.json",
    }
    return artifacts, refs


def test_valid_cohesive_chain_passes() -> None:
    artifacts, refs = _base_inputs()
    result = evaluate_trust_spine_evidence_cohesion(artifacts=artifacts, refs=refs)
    assert result["overall_decision"] == "ALLOW"
    assert result["blocking_reasons"] == []


def test_surface_mismatch_blocks() -> None:
    artifacts, refs = _base_inputs()
    artifacts["obedience_result"]["evaluated_surfaces"] = ["sequence_transition_promotion"]
    result = evaluate_trust_spine_evidence_cohesion(artifacts=artifacts, refs=refs)
    assert result["overall_decision"] == "BLOCK"
    assert "surface_set_mismatch" in result["contradiction_categories"]


def test_policy_truth_context_mismatch_blocks() -> None:
    artifacts, refs = _base_inputs()
    artifacts["done_certification_record"]["trust_spine_evidence_completeness_result"]["authority_path_mode"] = "legacy_compatibility"
    result = evaluate_trust_spine_evidence_cohesion(artifacts=artifacts, refs=refs)
    assert result["overall_decision"] == "BLOCK"
    assert "policy_context_mismatch" in result["contradiction_categories"]


def test_enforcement_vs_obedience_contradiction_blocks() -> None:
    artifacts, refs = _base_inputs()
    artifacts["enforcement_result"]["enforcement_status"] = "BLOCK"
    artifacts["obedience_result"]["overall_decision"] = "ALLOW"
    result = evaluate_trust_spine_evidence_cohesion(artifacts=artifacts, refs=refs)
    assert "enforcement_obedience_contradiction" in result["contradiction_categories"]


def test_invariant_vs_certification_contradiction_blocks() -> None:
    artifacts, refs = _base_inputs()
    artifacts["invariant_result"]["passed"] = False
    artifacts["done_certification_record"]["final_status"] = "PASSED"
    artifacts["done_certification_record"]["system_response"] = "allow"
    result = evaluate_trust_spine_evidence_cohesion(artifacts=artifacts, refs=refs)
    assert "invariant_certification_contradiction" in result["contradiction_categories"]


def test_missing_required_evidence_blocks() -> None:
    artifacts, refs = _base_inputs()
    refs.pop("invariant_result_ref")
    result = evaluate_trust_spine_evidence_cohesion(artifacts=artifacts, refs=refs)
    assert result["overall_decision"] == "BLOCK"
    assert "missing_required_evidence" in result["contradiction_categories"]


def test_malformed_input_fails_closed() -> None:
    artifacts, refs = _base_inputs()
    artifacts["invariant_result"]["passed"] = "not-bool"
    with pytest.raises(TrustSpineEvidenceCohesionError, match="must be a boolean"):
        evaluate_trust_spine_evidence_cohesion(artifacts=artifacts, refs=refs)


def test_deterministic_output_shape_and_id() -> None:
    artifacts, refs = _base_inputs()
    first = evaluate_trust_spine_evidence_cohesion(artifacts=artifacts, refs=refs)
    second = evaluate_trust_spine_evidence_cohesion(artifacts=artifacts, refs=refs)
    assert first == second
    assert first["deterministic_cohesion_id"].startswith("tsec-")
