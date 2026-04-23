"""Tests for in-memory judgment handoff in cycle_runner — RT-Loop-12."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from spectrum_systems.orchestration import cycle_runner
from tests.helpers_repo_write_lineage import build_valid_repo_write_lineage


_REPO_ROOT = Path(__file__).resolve().parents[1]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "autonomous_cycle"


def _write(path: Path, payload: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return str(path)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _fixture(name: str) -> dict:
    return _load(_FIXTURES / name)


def _manifest(tmp_path: Path) -> tuple[dict, Path]:
    """Build a minimal valid cycle manifest for the roadmap_approved state."""
    roadmap_path = _REPO_ROOT / "docs" / "roadmap" / "system_roadmap.md"

    review_path = tmp_path / "roadmap_review.json"
    review_payload = _fixture("roadmap_review_approved.json")
    review_payload["schema_version"] = "1.1.0"
    review_payload["governance_provenance"] = {
        "strategy_authority": {
            "path": "docs/architecture/system_strategy.md",
            "version": "2026-03-30",
        },
        "source_authorities": [
            {
                "source_id": "SRE-MAPPING",
                "path": "docs/source_structured/mapping_google_sre_reliability_principles_to_spectrum_systems.json",
            }
        ],
        "invariant_checks": [
            {"invariant_id": "strategy_alignment", "status": "pass", "detail": "aligned"},
            {"invariant_id": "source_grounding", "status": "pass", "detail": "bounded refs"},
        ],
        "drift_findings": [],
    }
    _write(review_path, review_payload)

    pqx_request_path = tmp_path / "pqx_request.json"
    _write(pqx_request_path, {
        "step_id": "AI-01",
        "roadmap_path": str(roadmap_path),
        "state_path": str(tmp_path / "pqx_state.json"),
        "runs_root": str(tmp_path / "pqx_runs"),
        "pqx_output_text": "deterministic pqx output",
        "repo_mutation_requested": False,
    })

    eligibility_path = tmp_path / "roadmap_eligibility.json"
    _write(eligibility_path, {
        "artifact_type": "roadmap_eligibility_artifact",
        "schema_version": "1.2.0",
        "artifact_version": "1.2.0",
        "roadmap_ref": "docs/roadmaps/system_roadmap.md",
        "evaluated_at": "2026-03-30T00:00:00Z",
        "identity_basis": {
            "roadmap_artifact_id": "roadmap-cycle-test",
            "roadmap_digest": "a542be4e4e3d2a77e6a508d46267f37754378291a075e59977fe80c0baab1128",
        },
        "program_alignment_status": "not_evaluated",
        "program_violation": False,
        "program_enforcement_action": "no_program_artifact",
        "eligible_step_ids": ["AI-01"],
        "recommended_next_step_ids": ["AI-01"],
        "blocked_steps": [],
        "strategy_status_artifacts": [
            {
                "artifact_type": "pqx_strategy_status_artifact",
                "schema_version": "1.0.0",
                "roadmap_row_id": "AI-01",
                "strategy_gate_decision": "allow",
                "violated_invariants": [],
                "drift_signals": [],
                "hardening_vs_expansion": "hardening",
                "replay_trace_declared": True,
                "eval_control_declared": False,
                "rationale": "strategy gate allows execution",
            }
        ],
        "summary": {
            "total_steps": 1,
            "completed_steps": 0,
            "eligible_steps": 1,
            "blocked_steps": 0,
            "strategy_gate": {"allow": 1, "warn": 0, "freeze": 0, "block": 0},
        },
        "artifact_id": "c1bfd40c7ea68193b177e33a01da488ff42d8d59cd6ab745ee019ec83afe83a1",
    })

    allow_policy_path = tmp_path / "evaluation_control_decision_allow.json"
    allow_policy = json.loads(
        (_REPO_ROOT / "contracts" / "examples" / "evaluation_control_decision.json")
        .read_text(encoding="utf-8")
    )
    allow_policy["decision"] = "allow"
    allow_policy["system_response"] = "allow"
    allow_policy["system_status"] = "healthy"
    allow_policy["rationale_code"] = "allow_all_signals_healthy"
    _write(allow_policy_path, allow_policy)

    manifest = {
        "cycle_id": "cycle-test-jdg-handoff",
        "current_state": "roadmap_approved",
        "sequence_mode": "legacy",
        "roadmap_artifact_path": str(roadmap_path),
        "strategy_authority": {
            "path": "docs/architecture/system_strategy.md",
            "version": "2026-03-30",
        },
        "source_authorities": [
            {
                "source_id": "SRE-MAPPING",
                "path": "docs/source_structured/mapping_google_sre_reliability_principles_to_spectrum_systems.json",
                "title": "Mapping Google SRE Reliability Principles to Spectrum Systems",
            }
        ],
        "roadmap_review_artifact_paths": [str(review_path)],
        "execution_report_paths": [],
        "implementation_review_paths": [],
        "fix_roadmap_path": None,
        "fix_roadmap_markdown_path": None,
        "fix_group_refs": [],
        "fix_execution_report_paths": [],
        "certification_record_path": None,
        "blocking_issues": [],
        "next_action": "await_roadmap_approval",
        "roadmap_approval_state": "approved",
        "hard_gates": {
            "roadmap_approved": True,
            "execution_contracts_pinned": True,
            "review_templates_present": True,
        },
        "pqx_execution_request_path": str(pqx_request_path),
        "pqx_request_ref": None,
        "execution_started_at": None,
        "execution_completed_at": None,
        "certification_status": "pending",
        "certification_summary": None,
        "done_certification_input_refs": {
            "replay_result_ref": "a",
            "regression_result_ref": "b",
            "certification_pack_ref": "c",
            "error_budget_ref": "d",
            "policy_ref": str(allow_policy_path),
            "closure_decision_artifact_ref": str(
                _REPO_ROOT / "contracts" / "examples" / "closure_decision_artifact.json"
            ),
            "review_control_signal_ref": str(
                _REPO_ROOT / "contracts" / "examples" / "review_control_signal.json"
            ),
            "ril_output_artifact_ref": str(
                _REPO_ROOT / "contracts" / "examples" / "review_integration_packet_artifact.json"
            ),
            "trust_spine_evidence_cohesion_result_ref": str(
                _REPO_ROOT / "contracts" / "examples" / "trust_spine_evidence_cohesion_result.json"
            ),
        },
        "required_judgments": ["artifact_release_readiness"],
        "required_judgment_eval_types": ["evidence_coverage", "policy_alignment", "replay_consistency"],
        "judgment_scope": "autonomous_cycle",
        "judgment_environment": "prod",
        "judgment_policy_paths": [
            str(_REPO_ROOT / "contracts" / "examples" / "judgment_policy.json")
        ],
        "judgment_policy_lifecycle_paths": [
            str(_REPO_ROOT / "contracts" / "examples" / "judgment_policy_lifecycle_record.json")
        ],
        "judgment_policy_rollout_paths": [
            str(_REPO_ROOT / "contracts" / "examples" / "judgment_policy_rollout_record.json")
        ],
        "judgment_input_context": {
            "quality_score": 0.95,
            "evidence_complete": True,
            "risk_level": "low",
            "scope_tag": "autonomous_cycle",
        },
        "judgment_evidence_refs": [
            str(_REPO_ROOT / "contracts" / "examples" / "execution_report_artifact.json")
        ],
        "judgment_precedent_record_paths": [
            str(_REPO_ROOT / "contracts" / "examples" / "judgment_record.json")
        ],
        "judgment_replay_reference_path": None,
        "judgment_record_path": None,
        "judgment_application_record_path": None,
        "judgment_eval_result_path": None,
        "next_step_decision_artifact_path": None,
        "roadmap_eligibility_artifact_path": str(eligibility_path),
        "eligible_step_ids_snapshot": ["AI-01"],
        "recommended_next_step_ids": ["AI-01"],
        "selected_step_id": "AI-01",
        "selected_step_status": "authorized",
        "decision_summary": "Preseeded eligibility decision summary.",
        "decision_blocked": False,
        "decision_block_reason": None,
        "eligibility_summary_snapshot": {
            "total_steps": 1,
            "completed_steps": 0,
            "eligible_steps": 1,
            "blocked_steps": 0,
        },
        "drift_remediation_artifact_path": None,
        "fix_plan_artifact_path": None,
        "sequence_trace_id": "trace-jdg-handoff-test",
        "sequence_lineage": ["contracts/examples/roadmap_eligibility_artifact.json"],
        "sequence_transition_history": [],
        "control_allow_promotion": False,
        "updated_at": "2026-03-30T00:00:00Z",
    }
    manifest_path = tmp_path / "cycle_manifest.json"
    _write(manifest_path, manifest)
    return manifest, manifest_path


def test_judgment_passed_in_memory(tmp_path: Path) -> None:
    """RT-Loop-12: Judgment is available in-memory in the manifest after run_cycle.

    The disk file must also exist for provenance, and the in-memory copy must
    be identical to the on-disk record — no second file read needed.
    """
    _, manifest_path = _manifest(tmp_path)

    result = cycle_runner.run_cycle(manifest_path)

    assert result["status"] == "ok"
    # In-memory judgment_record must be present
    assert "judgment_record" in result
    assert result["judgment_record"]["artifact_type"] == "judgment_record"
    # Disk path must also be set for provenance
    assert result["judgment_record_path"] is not None
    assert Path(result["judgment_record_path"]).is_file()
    # In-memory and on-disk records must be identical
    on_disk = json.loads(Path(result["judgment_record_path"]).read_text(encoding="utf-8"))
    assert result["judgment_record"] == on_disk


def test_judgment_application_and_eval_also_in_memory(tmp_path: Path) -> None:
    """Judgment application record and eval result are also passed in-memory."""
    _, manifest_path = _manifest(tmp_path)

    result = cycle_runner.run_cycle(manifest_path)

    assert result["status"] == "ok"
    assert "judgment_application_record" in result
    assert "judgment_eval_result" in result
    assert result["judgment_application_record"]["artifact_type"] == "judgment_application_record"
