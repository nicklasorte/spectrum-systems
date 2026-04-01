"""Deterministic control-surface manifest builder (CON-029)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class ControlSurfaceManifestError(ValueError):
    """Raised when control surface manifest generation fails closed."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _required_path_exists(path: str) -> bool:
    return (_repo_root() / path).is_file()


def _sorted_strings(values: List[str]) -> List[str]:
    return sorted(set(values))


def _canonical_hash(payload: Dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _surface_catalog() -> List[Dict[str, Any]]:
    return [
        {
            "surface_id": "evaluation_control_runtime",
            "surface_name": "Evaluation Control Decision",
            "surface_category": "runtime_decision",
            "owning_module": "spectrum_systems.modules.runtime.evaluation_control",
            "entrypoint_function": "build_evaluation_control_decision",
            "decision_scope": "map replay/failure signals into fail-closed control decision",
            "enforcement_scope": "runtime control allow/warn/freeze/block authority",
            "artifact_types_consumed": ["replay_result", "failure_eval_case", "failure_policy_binding"],
            "artifact_types_emitted": ["evaluation_control_decision"],
            "required_refs": ["replay_result.trace_id", "replay_result.replay_run_id", "error_budget_status"],
            "optional_refs": ["failure_policy_binding", "threshold_context"],
            "fail_closed": True,
            "promotion_blocking": True,
            "certification_blocking": True,
            "invariant_coverage": {
                "invariants_applied": ["threshold_context_consistency", "policy_authority_consistency"],
                "invariant_source_module": "spectrum_systems.modules.runtime.trust_spine_invariants",
                "invariant_enforcement_mode": "hard_block",
                "invariant_blocking_effect": "deny or block propagation on contradiction",
            },
            "test_coverage": {
                "covering_test_files": ["tests/test_evaluation_control.py"],
                "critical_test_names": [
                    "test_non_replay_input_fails_closed",
                    "test_invalid_trace_linkage_fails_closed",
                    "test_budget_exhausted_forces_non_allow_response",
                ],
                "coverage_status": "covered",
            },
        },
        {
            "surface_id": "replay_governance_gate",
            "surface_name": "Replay Governance Decision",
            "surface_category": "runtime_decision",
            "owning_module": "spectrum_systems.modules.runtime.replay_governance",
            "entrypoint_function": "build_replay_governance_decision",
            "decision_scope": "derive replay governance response from replay analysis + policy",
            "enforcement_scope": "review/quarantine/block influence on downstream execution",
            "artifact_types_consumed": ["replay_decision_analysis", "replay_governance_policy"],
            "artifact_types_emitted": ["replay_governance_decision"],
            "required_refs": ["decision_consistency.status", "reproducibility_score"],
            "optional_refs": ["environment_context", "replay_artifact_ids"],
            "fail_closed": True,
            "promotion_blocking": True,
            "certification_blocking": False,
            "invariant_coverage": {
                "invariants_applied": [],
                "invariant_source_module": "",
                "invariant_enforcement_mode": "none",
                "invariant_blocking_effect": "none",
            },
            "test_coverage": {
                "covering_test_files": ["tests/test_replay_governance.py"],
                "critical_test_names": [],
                "coverage_status": "partially_covered",
            },
        },
        {
            "surface_id": "sequence_transition_promotion",
            "surface_name": "Sequence Transition Promotion Gate",
            "surface_category": "promotion_certification",
            "owning_module": "spectrum_systems.orchestration.sequence_transition_policy",
            "entrypoint_function": "evaluate_sequence_transition",
            "decision_scope": "deterministic promotion transition allow/block",
            "enforcement_scope": "promotion-state transition authorization",
            "artifact_types_consumed": ["sequence_manifest", "replay_result", "evaluation_control_decision", "enforcement_result", "eval_coverage_summary"],
            "artifact_types_emitted": ["sequence_transition_decision"],
            "required_refs": ["done_certification_input_refs.replay_result_ref", "done_certification_input_refs.policy_ref", "done_certification_input_refs.enforcement_result_ref", "done_certification_input_refs.eval_coverage_summary_ref"],
            "optional_refs": ["control_loop_gate_proof", "hard_gate_falsification_record_path"],
            "fail_closed": True,
            "promotion_blocking": True,
            "certification_blocking": False,
            "invariant_coverage": {
                "invariants_applied": [
                    "threshold_context_consistency",
                    "policy_authority_consistency",
                    "replay_enforcement_promotion_alignment",
                    "coverage_promotion_alignment",
                    "gate_proof_truthfulness",
                ],
                "invariant_source_module": "spectrum_systems.modules.runtime.trust_spine_invariants",
                "invariant_enforcement_mode": "hard_block",
                "invariant_blocking_effect": "promotion denied when invariant violation detected",
            },
            "test_coverage": {
                "covering_test_files": ["tests/test_sequence_transition_policy.py"],
                "critical_test_names": [
                    "test_promotion_blocks_when_enforcement_result_ref_missing",
                    "test_promotion_blocks_when_eval_coverage_summary_ref_missing",
                    "test_promotion_blocks_when_threshold_context_is_comparative_analysis",
                ],
                "coverage_status": "covered",
            },
        },
        {
            "surface_id": "trust_spine_invariant_validation",
            "surface_name": "Trust Spine Invariant Validation",
            "surface_category": "governance_validation",
            "owning_module": "spectrum_systems.modules.runtime.trust_spine_invariants",
            "entrypoint_function": "validate_trust_spine_invariants",
            "decision_scope": "cross-seam consistency validation on authority paths",
            "enforcement_scope": "blocking reasons consumed by promotion/certification gates",
            "artifact_types_consumed": ["replay_result", "evaluation_control_decision", "enforcement_result", "eval_coverage_summary"],
            "artifact_types_emitted": ["trust_spine_invariant_result"],
            "required_refs": ["target_surface", "policy_ref", "replay_result_ref"],
            "optional_refs": ["gate_proof_ref", "done_certification_record"],
            "fail_closed": True,
            "promotion_blocking": True,
            "certification_blocking": True,
            "invariant_coverage": {
                "invariants_applied": [
                    "threshold_context_consistency",
                    "policy_authority_consistency",
                    "replay_enforcement_promotion_alignment",
                    "coverage_promotion_alignment",
                    "gate_proof_truthfulness",
                    "certification_closure_coherence",
                ],
                "invariant_source_module": "spectrum_systems.modules.runtime.trust_spine_invariants",
                "invariant_enforcement_mode": "hard_block",
                "invariant_blocking_effect": "blocking reasons propagated to promotion/certification seams",
            },
            "test_coverage": {
                "covering_test_files": ["tests/test_done_certification.py", "tests/test_sequence_transition_policy.py"],
                "critical_test_names": [],
                "coverage_status": "covered",
            },
        },
        {
            "surface_id": "done_certification_gate",
            "surface_name": "Done Certification Gate",
            "surface_category": "promotion_certification",
            "owning_module": "spectrum_systems.modules.governance.done_certification",
            "entrypoint_function": "run_done_certification",
            "decision_scope": "deterministic certification pass/fail and system response",
            "enforcement_scope": "certification authority for promotion readiness",
            "artifact_types_consumed": ["replay_result", "regression_run_result", "control_loop_certification_pack", "error_budget_status", "evaluation_control_decision"],
            "artifact_types_emitted": ["done_certification_record"],
            "required_refs": ["replay_result_ref", "regression_result_ref", "certification_pack_ref", "error_budget_ref", "policy_ref"],
            "optional_refs": ["enforcement_result_ref", "eval_coverage_summary_ref", "failure_injection_ref"],
            "fail_closed": True,
            "promotion_blocking": True,
            "certification_blocking": True,
            "invariant_coverage": {
                "invariants_applied": [
                    "required_authority_refs_present",
                    "enforcement_evidence_present",
                    "coverage_evidence_present",
                    "certification_supporting_refs_present",
                ],
                "invariant_source_module": "spectrum_systems.modules.runtime.trust_spine_invariants",
                "invariant_enforcement_mode": "hard_block",
                "invariant_blocking_effect": "FAILED certification on invariant/completeness failure",
            },
            "test_coverage": {
                "covering_test_files": ["tests/test_done_certification.py"],
                "critical_test_names": [
                    "test_done_certification_active_path_fails_closed_when_enforcement_ref_missing",
                    "test_done_certification_active_path_fails_closed_when_coverage_ref_missing",
                    "test_trust_spine_threshold_context_mismatch_blocks",
                ],
                "coverage_status": "covered",
            },
        },
        {
            "surface_id": "contract_preflight_gate",
            "surface_name": "Contract Preflight Governance Gate",
            "surface_category": "governance_validation",
            "owning_module": "scripts.run_contract_preflight",
            "entrypoint_function": "main",
            "decision_scope": "changed-contract impact classification and strategy gate decision",
            "enforcement_scope": "pre-merge/preflight governance decision artifact",
            "artifact_types_consumed": ["changed_paths", "schema_registry", "example_registry"],
            "artifact_types_emitted": ["contract_preflight_result"],
            "required_refs": ["contracts/schemas", "contracts/examples", "contracts/standards-manifest.json"],
            "optional_refs": ["base_ref", "head_ref", "changed_paths"],
            "fail_closed": True,
            "promotion_blocking": False,
            "certification_blocking": False,
            "invariant_coverage": {
                "invariants_applied": [],
                "invariant_source_module": "",
                "invariant_enforcement_mode": "none",
                "invariant_blocking_effect": "none",
            },
            "test_coverage": {
                "covering_test_files": ["tests/test_contract_preflight.py"],
                "critical_test_names": [],
                "coverage_status": "partially_covered",
            },
        },
    ]


def _validate_surface_metadata(surfaces: List[Dict[str, Any]]) -> None:
    if not surfaces:
        raise ControlSurfaceManifestError("control surface catalog must not be empty")

    seen: set[str] = set()
    for surface in surfaces:
        sid = surface.get("surface_id")
        if not isinstance(sid, str) or not sid:
            raise ControlSurfaceManifestError("surface_id must be a non-empty string")
        if sid in seen:
            raise ControlSurfaceManifestError(f"duplicate surface_id detected: {sid}")
        seen.add(sid)

        module_name = surface.get("owning_module")
        if not isinstance(module_name, str) or not module_name:
            raise ControlSurfaceManifestError(f"surface {sid} missing owning_module")

        module_path = _repo_root() / (module_name.replace(".", "/") + ".py")
        if module_name.startswith("scripts."):
            module_path = _repo_root() / (module_name.replace(".", "/") + ".py")
        if not module_path.is_file():
            raise ControlSurfaceManifestError(f"surface {sid} owning_module file not found: {module_path}")

        for test_file in surface["test_coverage"]["covering_test_files"]:
            if not _required_path_exists(test_file):
                raise ControlSurfaceManifestError(f"surface {sid} test coverage file not found: {test_file}")


def _gap_report(surfaces: List[Dict[str, Any]]) -> Dict[str, Any]:
    uncovered = [s["surface_id"] for s in surfaces if s["test_coverage"]["coverage_status"] == "uncovered"]
    missing_invariants = [
        s["surface_id"]
        for s in surfaces
        if not s["invariant_coverage"]["invariants_applied"] and s["surface_category"] != "runtime_decision"
    ]
    missing_required_refs = [s["surface_id"] for s in surfaces if not s["required_refs"]]
    missing_targeted_tests = [s["surface_id"] for s in surfaces if not s["test_coverage"]["covering_test_files"]]

    contradictory: List[str] = []
    for s in surfaces:
        if not s["fail_closed"] and (s["promotion_blocking"] or s["certification_blocking"]):
            contradictory.append(f"{s['surface_id']}:blocking_surface_not_fail_closed")
        if s["test_coverage"]["coverage_status"] == "covered" and not s["test_coverage"]["critical_test_names"]:
            contradictory.append(f"{s['surface_id']}:covered_without_critical_test_mapping")

    return {
        "uncovered_surfaces": _sorted_strings(uncovered),
        "surfaces_missing_invariants": _sorted_strings(missing_invariants),
        "surfaces_missing_required_refs": _sorted_strings(missing_required_refs),
        "surfaces_missing_targeted_tests": _sorted_strings(missing_targeted_tests),
        "contradictory_surface_metadata": _sorted_strings(contradictory),
    }


def build_control_surface_manifest() -> Dict[str, Any]:
    surfaces = sorted(_surface_catalog(), key=lambda item: item["surface_id"])
    _validate_surface_metadata(surfaces)

    gap_signals = _gap_report(surfaces)
    covered = sum(1 for s in surfaces if s["test_coverage"]["coverage_status"] == "covered")
    partial = sum(1 for s in surfaces if s["test_coverage"]["coverage_status"] == "partially_covered")
    uncovered = len(gap_signals["uncovered_surfaces"])

    identity_payload = {
        "schema_version": "1.0.0",
        "surface_ids": [s["surface_id"] for s in surfaces],
        "gap_signals": gap_signals,
    }
    deterministic_build_identity = f"csm-{_canonical_hash(identity_payload)[:16]}"

    manifest = {
        "artifact_type": "control_surface_manifest",
        "schema_version": "1.0.0",
        "manifest_status": "gaps_detected" if any(gap_signals.values()) else "complete",
        "deterministic_build_identity": deterministic_build_identity,
        "surfaces": surfaces,
        "gap_signals": gap_signals,
        "summary": {
            "total_surfaces": len(surfaces),
            "fully_covered_surfaces": covered,
            "partially_covered_surfaces": partial,
            "uncovered_surfaces_count": uncovered,
            "blocking_gaps_present": bool(
                gap_signals["uncovered_surfaces"]
                or gap_signals["surfaces_missing_required_refs"]
                or gap_signals["contradictory_surface_metadata"]
            ),
        },
    }

    schema = load_schema("control_surface_manifest")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(manifest), key=lambda err: list(err.absolute_path))
    if errors:
        reasons = "; ".join(error.message for error in errors)
        raise ControlSurfaceManifestError(f"generated control_surface_manifest failed schema validation: {reasons}")

    return manifest
