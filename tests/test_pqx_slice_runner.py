from __future__ import annotations

import importlib
import json

import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from spectrum_systems.modules.runtime.pqx_slice_runner import run_pqx_slice




class FixedClock:
    def __init__(self) -> None:
        self._tick = 0

    def __call__(self):
        base = datetime(2026, 3, 29, 22, 0, 0, tzinfo=timezone.utc)
        value = base + timedelta(seconds=self._tick)
        self._tick += 1
        return value


def test_run_pqx_slice_valid_run_emits_required_artifacts(tmp_path: Path) -> None:
    state_path = tmp_path / "pqx_state.json"
    state_path.write_text(json.dumps({"schema_version": "1.0.0", "rows": []}) + "\n", encoding="utf-8")

    result = run_pqx_slice(
        step_id="AI-01",
        roadmap_path=Path("docs/roadmap/system_roadmap.md"),
        state_path=state_path,
        runs_root=tmp_path / "runs",
        pqx_output_text="deterministic output",
        clock=FixedClock(),
    )

    assert result["status"] == "complete"
    record = json.loads(Path(result["slice_execution_record"]).read_text(encoding="utf-8"))
    assert record["artifact_type"] == "pqx_slice_execution_record"
    assert record["certification_status"] == "certified"
    assert record["artifacts_emitted"]

    bundle = json.loads(Path(result["pqx_slice_audit_bundle"]).read_text(encoding="utf-8"))
    assert bundle["trace_ref"]
    assert bundle["replay_result_ref"]
    assert bundle["control_decision_ref"]
    assert bundle["certification_result_ref"]


def test_run_pqx_slice_invalid_step_blocks_entrypoint(tmp_path: Path) -> None:
    result = run_pqx_slice(
        step_id="NOT-A-ROW",
        roadmap_path=Path("docs/roadmap/system_roadmap.md"),
        state_path=tmp_path / "state.json",
        runs_root=tmp_path / "runs",
        pqx_output_text="x",
        clock=FixedClock(),
    )
    assert result["status"] == "blocked"
    assert result["block_type"] == "INVALID_EXECUTION_ENTRYPOINT"


def test_run_pqx_slice_missing_roadmap_blocks_entrypoint(tmp_path: Path) -> None:
    result = run_pqx_slice(
        step_id="AI-01",
        roadmap_path=tmp_path / "missing.md",
        state_path=tmp_path / "state.json",
        runs_root=tmp_path / "runs",
        pqx_output_text="x",
        clock=FixedClock(),
    )
    assert result["status"] == "blocked"
    assert result["block_type"] == "INVALID_EXECUTION_ENTRYPOINT"


def test_run_pqx_slice_bypass_attempt_without_artifact_emission_blocks(tmp_path: Path) -> None:
    state_path = tmp_path / "pqx_state.json"
    state_path.write_text(json.dumps({"schema_version": "1.0.0", "rows": []}) + "\n", encoding="utf-8")
    result = run_pqx_slice(
        step_id="AI-01",
        roadmap_path=Path("docs/roadmap/system_roadmap.md"),
        state_path=state_path,
        runs_root=tmp_path / "runs",
        pqx_output_text="x",
        emit_artifacts=False,
        clock=FixedClock(),
    )
    assert result["status"] == "blocked"
    assert result["block_type"] == "ARTIFACT_EMISSION_BLOCKED"


def _impact_artifact(*, compatibility_class: str, blocking: bool, safe_to_execute: bool) -> dict:
    return {
        "artifact_type": "contract_impact_artifact",
        "schema_version": "1.0.0",
        "impact_id": "f11d5d12f47f7547d6119d91d4d5633c59dca95f3f899f1fdd0a4af11e0189ce",
        "generated_at": "2026-03-30T00:00:00Z",
        "analyzer_version": "1.0.0",
        "standards_manifest_path": "contracts/standards-manifest.json",
        "changed_contract_paths": ["contracts/schemas/pqx_execution_result.schema.json"],
        "changed_example_paths": ["contracts/examples/pqx_execution_result.json"],
        "impacted_consumer_paths": [],
        "impacted_test_paths": [],
        "impacted_runtime_paths": [],
        "impacted_script_paths": [],
        "compatibility_class": compatibility_class,
        "blocking": blocking,
        "blocking_reasons": ["test blocking reason"] if blocking else [],
        "required_remediations": ["test remediation"] if blocking else [],
        "safe_to_execute": safe_to_execute,
        "evidence_refs": ["contracts/standards-manifest.json"],
        "summary": "test",
    }


def _execution_impact_artifact(*, blocking: bool, indeterminate: bool, safe_to_execute: bool) -> dict:
    return {
        "artifact_type": "execution_change_impact_artifact",
        "schema_version": "1.0.0",
        "impact_id": "2375367d029bece6c41dd655ec38c68ed1d51f37ed4d0be2f92402fe6ad3b793",
        "generated_at": "2026-03-30T00:00:00Z",
        "baseline_ref": "HEAD",
        "changed_paths": ["README.md"],
        "analyzed_paths": ["README.md"],
        "path_assessments": [
            {
                "path": "README.md",
                "exists_in_baseline": True,
                "exists_in_worktree": True,
                "change_type": "modified",
                "sensitivity_class": "low",
                "governed_surface_types": ["unknown"],
                "impact_reason_codes": ["general_non_governed_path"],
                "review_required": False,
                "eval_required": False,
                "blocking_reason": "test" if blocking else None,
            }
        ],
        "touched_sensitive_surfaces": [],
        "highest_sensitivity": "low",
        "risk_classification": "blocking" if blocking else "safe",
        "blocking": blocking,
        "safe_to_execute": safe_to_execute,
        "indeterminate": indeterminate,
        "required_reviews": [],
        "required_eval_artifacts": [],
        "required_followup_actions": [],
        "rationale": ["test"],
        "provenance": {
            "analyzer_version": "1.0.0",
            "standards_manifest_path": "contracts/standards-manifest.json",
            "rule_set": "execution-change-impact-g14",
            "deterministic": True,
        },
    }


def _preflight_artifact(*, status: str, decision: str, masking_detected: bool = False, degraded: bool = False) -> dict:
    return {
        "artifact_type": "contract_preflight_result_artifact",
        "schema_version": "1.0.0",
        "preflight_status": status,
        "changed_contracts": ["contracts/schemas/roadmap_eligibility_artifact.schema.json"],
        "impacted_producers": [
            "spectrum_systems/orchestration/cycle_runner.py",
            "spectrum_systems/orchestration/next_step_decision.py",
            "spectrum_systems/orchestration/roadmap_eligibility.py",
        ],
        "impacted_fixtures": ["tests/fixtures/autonomous_cycle/cycle_status_blocked_manifest.json"],
        "impacted_consumers": [
            "tests/test_contract_preflight.py",
            "tests/test_contracts.py",
            "tests/test_cycle_observability.py",
            "tests/test_cycle_runner.py",
            "tests/test_next_step_decision.py",
            "tests/test_next_step_decision_policy.py",
            "tests/test_pqx_slice_runner.py",
            "tests/test_roadmap_eligibility.py",
            "tests/test_sequence_transition_policy.py",
        ],
        "masking_detected": masking_detected,
        "recommended_repair_area": [] if decision in {"ALLOW", "WARN"} else ["targeted downstream consumer tests"],
        "report_paths": {
            "json_report_path": "outputs/contract_preflight/contract_preflight_report.json",
            "markdown_report_path": "outputs/contract_preflight/contract_preflight_report.md",
        },
        "generated_at": "2026-04-01T00:00:00Z",
        "control_surface_gap_status": "not_run",
        "control_surface_gap_result_ref": None,
        "pqx_gap_work_items_ref": None,
        "control_surface_gap_blocking": False,
        "control_signal": {
            "strategy_gate_decision": decision,
            "rationale": "test preflight mapping rationale",
            "changed_path_detection_mode": "degraded_full_governed_scan" if degraded else "base_head_diff",
            "degraded_detection": degraded,
        },
        "trace": {
            "producer": "scripts/run_contract_preflight.py",
            "policy_version": "1.0.0",
            "refs_attempted": ["origin/main..HEAD"],
            "fallback_used": degraded,
            "evaluation_mode": "full",
            "skip_reason": None,
            "changed_paths_resolved": ["contracts/schemas/roadmap_eligibility_artifact.schema.json"],
            "evaluated_surfaces": ["contract_surface"],
            "provenance_ref": "contracts/standards-manifest.json",
        },
    }


def test_run_pqx_slice_blocks_on_breaking_contract_impact(tmp_path: Path) -> None:
    state_path = tmp_path / "pqx_state.json"
    state_path.write_text(json.dumps({"schema_version": "1.0.0", "rows": []}) + "\n", encoding="utf-8")
    impact_path = tmp_path / "impact.json"
    impact_path.write_text(json.dumps(_impact_artifact(compatibility_class="breaking", blocking=True, safe_to_execute=False)))

    result = run_pqx_slice(
        step_id="AI-01",
        roadmap_path=Path("docs/roadmap/system_roadmap.md"),
        state_path=state_path,
        runs_root=tmp_path / "runs",
        pqx_output_text="x",
        contract_impact_artifact_path=impact_path,
        clock=FixedClock(),
    )
    assert result["status"] == "blocked"
    assert result["block_type"] == "CONTRACT_IMPACT_BLOCKED"


def test_run_pqx_slice_blocks_on_indeterminate_contract_impact(tmp_path: Path) -> None:
    state_path = tmp_path / "pqx_state.json"
    state_path.write_text(json.dumps({"schema_version": "1.0.0", "rows": []}) + "\n", encoding="utf-8")
    impact_path = tmp_path / "impact-indeterminate.json"
    impact_path.write_text(json.dumps(_impact_artifact(compatibility_class="indeterminate", blocking=True, safe_to_execute=False)))

    result = run_pqx_slice(
        step_id="AI-01",
        roadmap_path=Path("docs/roadmap/system_roadmap.md"),
        state_path=state_path,
        runs_root=tmp_path / "runs",
        pqx_output_text="x",
        contract_impact_artifact_path=impact_path,
        clock=FixedClock(),
    )
    assert result["status"] == "blocked"
    assert result["block_type"] == "CONTRACT_IMPACT_BLOCKED"


def test_run_pqx_slice_allows_compatible_contract_impact(tmp_path: Path) -> None:
    state_path = tmp_path / "pqx_state.json"
    state_path.write_text(json.dumps({"schema_version": "1.0.0", "rows": []}) + "\n", encoding="utf-8")
    impact_path = tmp_path / "impact-compatible.json"
    impact_path.write_text(json.dumps(_impact_artifact(compatibility_class="compatible", blocking=False, safe_to_execute=True)))

    result = run_pqx_slice(
        step_id="AI-01",
        roadmap_path=Path("docs/roadmap/system_roadmap.md"),
        state_path=state_path,
        runs_root=tmp_path / "runs",
        pqx_output_text="x",
        contract_impact_artifact_path=impact_path,
        clock=FixedClock(),
    )
    assert result["status"] == "complete"


def test_run_pqx_slice_blocks_on_blocking_execution_change_impact(tmp_path: Path) -> None:
    state_path = tmp_path / "pqx_state.json"
    state_path.write_text(json.dumps({"schema_version": "1.0.0", "rows": []}) + "\n", encoding="utf-8")
    impact_path = tmp_path / "execution-impact-blocking.json"
    impact_path.write_text(
        json.dumps(_execution_impact_artifact(blocking=True, indeterminate=False, safe_to_execute=False)),
        encoding="utf-8",
    )

    result = run_pqx_slice(
        step_id="AI-01",
        roadmap_path=Path("docs/roadmap/system_roadmap.md"),
        state_path=state_path,
        runs_root=tmp_path / "runs",
        pqx_output_text="x",
        execution_change_impact_artifact_path=impact_path,
        clock=FixedClock(),
    )
    assert result["status"] == "blocked"
    assert result["block_type"] == "EXECUTION_CHANGE_IMPACT_BLOCKED"


def test_run_pqx_slice_allows_explicit_safe_execution_change_impact(tmp_path: Path) -> None:
    state_path = tmp_path / "pqx_state.json"
    state_path.write_text(json.dumps({"schema_version": "1.0.0", "rows": []}) + "\n", encoding="utf-8")
    impact_path = tmp_path / "execution-impact-safe.json"
    impact_path.write_text(
        json.dumps(_execution_impact_artifact(blocking=False, indeterminate=False, safe_to_execute=True)),
        encoding="utf-8",
    )

    result = run_pqx_slice(
        step_id="AI-01",
        roadmap_path=Path("docs/roadmap/system_roadmap.md"),
        state_path=state_path,
        runs_root=tmp_path / "runs",
        pqx_output_text="x",
        execution_change_impact_artifact_path=impact_path,
        clock=FixedClock(),
    )
    assert result["status"] == "complete"


def test_run_pqx_slice_blocks_on_manifest_completeness_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state_path = tmp_path / "pqx_state.json"
    state_path.write_text(json.dumps({"schema_version": "1.0.0", "rows": []}) + "\n", encoding="utf-8")

    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.pqx_slice_runner.validate_manifest_completeness",
        lambda _manifest: {
            "valid": False,
            "errors": ["contracts[0] missing required field: artifact_class"],
            "missing_fields": ["contracts[0].artifact_class"],
            "invalid_entries": [],
        },
    )

    result = run_pqx_slice(
        step_id="AI-01",
        roadmap_path=Path("docs/roadmap/system_roadmap.md"),
        state_path=state_path,
        runs_root=tmp_path / "runs",
        pqx_output_text="x",
        clock=FixedClock(),
        enforce_manifest_completeness=True,
    )

    assert result["status"] == "blocked"
    assert result["block_type"] == "MANIFEST_COMPLETENESS_BLOCKED"


def test_run_pqx_slice_default_path_does_not_enforce_manifest_completeness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state_path = tmp_path / "pqx_state.json"
    state_path.write_text(json.dumps({"schema_version": "1.0.0", "rows": []}) + "\n", encoding="utf-8")

    monkeypatch.setattr(
        "spectrum_systems.modules.runtime.pqx_slice_runner.validate_manifest_completeness",
        lambda _manifest: {
            "valid": False,
            "errors": ["contracts[0] missing required field: artifact_class"],
            "missing_fields": ["contracts[0].artifact_class"],
            "invalid_entries": [],
        },
    )

    result = run_pqx_slice(
        step_id="AI-01",
        roadmap_path=Path("docs/roadmap/system_roadmap.md"),
        state_path=state_path,
        runs_root=tmp_path / "runs",
        pqx_output_text="x",
        clock=FixedClock(),
    )

    assert result["status"] == "complete"


def test_run_pqx_slice_allows_progression_on_passing_preflight(tmp_path: Path) -> None:
    state_path = tmp_path / "pqx_state.json"
    state_path.write_text(json.dumps({"schema_version": "1.0.0", "rows": []}) + "\n", encoding="utf-8")
    preflight_path = tmp_path / "preflight-pass.json"
    preflight_path.write_text(json.dumps(_preflight_artifact(status="passed", decision="ALLOW")), encoding="utf-8")

    result = run_pqx_slice(
        step_id="AI-01",
        roadmap_path=Path("docs/roadmap/system_roadmap.md"),
        state_path=state_path,
        runs_root=tmp_path / "runs",
        pqx_output_text="x",
        contract_preflight_result_artifact_path=preflight_path,
        clock=FixedClock(),
    )

    assert result["status"] == "complete"
    assert result["contract_preflight_decision"] == "allow"


def test_run_pqx_slice_blocks_progression_on_failed_preflight(tmp_path: Path) -> None:
    state_path = tmp_path / "pqx_state.json"
    state_path.write_text(json.dumps({"schema_version": "1.0.0", "rows": []}) + "\n", encoding="utf-8")
    preflight_path = tmp_path / "preflight-fail.json"
    preflight_path.write_text(json.dumps(_preflight_artifact(status="failed", decision="BLOCK")), encoding="utf-8")

    result = run_pqx_slice(
        step_id="AI-01",
        roadmap_path=Path("docs/roadmap/system_roadmap.md"),
        state_path=state_path,
        runs_root=tmp_path / "runs",
        pqx_output_text="x",
        contract_preflight_result_artifact_path=preflight_path,
        clock=FixedClock(),
    )

    assert result["status"] == "blocked"
    assert result["block_type"] == "CONTRACT_PREFLIGHT_BLOCKED"


def test_run_pqx_slice_blocks_on_preflight_masking_detected(tmp_path: Path) -> None:
    state_path = tmp_path / "pqx_state.json"
    state_path.write_text(json.dumps({"schema_version": "1.0.0", "rows": []}) + "\n", encoding="utf-8")
    preflight_path = tmp_path / "preflight-masking.json"
    preflight_path.write_text(json.dumps(_preflight_artifact(status="failed", decision="BLOCK", masking_detected=True)), encoding="utf-8")

    result = run_pqx_slice(
        step_id="AI-01",
        roadmap_path=Path("docs/roadmap/system_roadmap.md"),
        state_path=state_path,
        runs_root=tmp_path / "runs",
        pqx_output_text="x",
        contract_preflight_result_artifact_path=preflight_path,
        clock=FixedClock(),
    )

    assert result["status"] == "blocked"
    assert "preflight BLOCK" in result["reason"]


def test_run_pqx_slice_warns_or_allows_on_degraded_preflight_scan(tmp_path: Path) -> None:
    state_path = tmp_path / "pqx_state.json"
    state_path.write_text(json.dumps({"schema_version": "1.0.0", "rows": []}) + "\n", encoding="utf-8")
    preflight_path = tmp_path / "preflight-warn.json"
    preflight_path.write_text(json.dumps(_preflight_artifact(status="passed", decision="WARN", degraded=True)), encoding="utf-8")

    result = run_pqx_slice(
        step_id="AI-01",
        roadmap_path=Path("docs/roadmap/system_roadmap.md"),
        state_path=state_path,
        runs_root=tmp_path / "runs",
        pqx_output_text="x",
        contract_preflight_result_artifact_path=preflight_path,
        clock=FixedClock(),
    )

    assert result["status"] == "complete"
    assert result["contract_preflight_decision"] == "warn"


def test_run_pqx_slice_blocks_when_contract_changes_lack_preflight_artifact(tmp_path: Path) -> None:
    state_path = tmp_path / "pqx_state.json"
    state_path.write_text(json.dumps({"schema_version": "1.0.0", "rows": []}) + "\n", encoding="utf-8")

    result = run_pqx_slice(
        step_id="AI-01",
        roadmap_path=Path("docs/roadmap/system_roadmap.md"),
        state_path=state_path,
        runs_root=tmp_path / "runs",
        pqx_output_text="x",
        changed_contract_paths=["contracts/schemas/roadmap_row.schema.json"],
        clock=FixedClock(),
    )

    assert result["status"] == "blocked"
    assert result["block_type"] == "CONTRACT_PREFLIGHT_BLOCKED"
    assert "required for governed contract/example changes" in result["reason"]


def test_run_pqx_slice_blocks_on_inconsistent_preflight_status_and_decision(tmp_path: Path) -> None:
    state_path = tmp_path / "pqx_state.json"
    state_path.write_text(json.dumps({"schema_version": "1.0.0", "rows": []}) + "\n", encoding="utf-8")
    preflight_path = tmp_path / "preflight-inconsistent-status-decision.json"
    preflight_path.write_text(json.dumps(_preflight_artifact(status="failed", decision="ALLOW")), encoding="utf-8")

    result = run_pqx_slice(
        step_id="AI-01",
        roadmap_path=Path("docs/roadmap/system_roadmap.md"),
        state_path=state_path,
        runs_root=tmp_path / "runs",
        pqx_output_text="x",
        contract_preflight_result_artifact_path=preflight_path,
        clock=FixedClock(),
    )

    assert result["status"] == "blocked"
    assert result["block_type"] == "CONTRACT_PREFLIGHT_BLOCKED"
    assert "inconsistent preflight control mapping" in result["reason"]


def test_run_pqx_slice_blocks_on_preflight_warn_without_degraded_detection(tmp_path: Path) -> None:
    state_path = tmp_path / "pqx_state.json"
    state_path.write_text(json.dumps({"schema_version": "1.0.0", "rows": []}) + "\n", encoding="utf-8")
    payload = _preflight_artifact(status="passed", decision="WARN", degraded=False)
    preflight_path = tmp_path / "preflight-warn-without-degraded.json"
    preflight_path.write_text(json.dumps(payload), encoding="utf-8")

    result = run_pqx_slice(
        step_id="AI-01",
        roadmap_path=Path("docs/roadmap/system_roadmap.md"),
        state_path=state_path,
        runs_root=tmp_path / "runs",
        pqx_output_text="x",
        contract_preflight_result_artifact_path=preflight_path,
        clock=FixedClock(),
    )

    assert result["status"] == "blocked"
    assert result["block_type"] == "CONTRACT_PREFLIGHT_BLOCKED"
    assert "WARN decision requires degraded_detection=true" in result["reason"]


def test_runtime_module_import_has_no_done_certification_cycle() -> None:
    runtime_module = importlib.import_module("spectrum_systems.modules.runtime")
    assert runtime_module is not None


def _gap_packet(*, overall_decision: str = "ALLOW") -> dict:
    packet = {
        "artifact_type": "control_surface_gap_packet",
        "artifact_id": "csgp-aaaaaaaaaaaaaaaaaaaaaaaa",
        "schema_version": "1.0.0",
        "generated_at": "2026-04-02T00:00:00Z",
        "trace_id": "trace:test:control-surface-gap",
        "policy_id": "policy:control-surface-gap:v1",
        "governing_ref": "contracts/standards-manifest.json",
        "overall_decision": overall_decision,
        "summary": "No control-surface gaps detected." if overall_decision == "ALLOW" else "Blocking gaps detected.",
        "evaluated_surfaces": [
            "control_surface_manifest",
            "control_surface_enforcement",
            "control_surface_obedience",
        ],
        "gap_count": 0,
        "blocking_gap_count": 0,
        "gaps": [],
        "evidence_refs": [],
        "next_governance_actions": [],
    }
    if overall_decision == "BLOCK":
        packet["gaps"] = [
            {
                "gap_id": "csg-aaaaaaaaaaaaaaaaaaaaaaaa",
                "surface_name": "control_surface_manifest",
                "gap_category": "missing_manifest_surface",
                "severity": "critical",
                "blocking": True,
                "observed_condition": "surface missing",
                "expected_condition": "surface declared",
                "evidence_ref": "contracts/examples/control_surface_manifest.json",
                "source_artifact_type": "control_surface_manifest",
                "source_artifact_ref": "contracts/examples/control_surface_manifest.json",
                "suggested_action": "fix_manifest_declaration",
                "deterministic_identity": "csg-aaaaaaaaaaaaaaaaaaaaaaaa",
            }
        ]
        packet["gap_count"] = 1
        packet["blocking_gap_count"] = 1
        packet["evidence_refs"] = ["contracts/examples/control_surface_manifest.json"]
        packet["next_governance_actions"] = ["fix_manifest_declaration"]
    return packet


def test_run_pqx_slice_blocks_when_control_surface_packet_required_but_missing(tmp_path: Path) -> None:
    state_path = tmp_path / "pqx_state.json"
    state_path.write_text(json.dumps({"schema_version": "1.0.0", "rows": []}) + "\n", encoding="utf-8")
    preflight_path = tmp_path / "preflight-control-surface.json"
    payload = _preflight_artifact(status="passed", decision="ALLOW")
    payload["control_surface_gap_status"] = "gaps_detected"
    preflight_path.write_text(json.dumps(payload), encoding="utf-8")

    result = run_pqx_slice(
        step_id="AI-01",
        roadmap_path=Path("docs/roadmap/system_roadmap.md"),
        state_path=state_path,
        runs_root=tmp_path / "runs",
        pqx_output_text="x",
        contract_preflight_result_artifact_path=preflight_path,
        clock=FixedClock(),
    )

    assert result["status"] == "blocked"
    assert result["block_type"] == "CONTROL_SURFACE_GAP_PACKET_REQUIRED"


def test_run_pqx_slice_fail_closed_on_malformed_control_surface_packet(tmp_path: Path) -> None:
    state_path = tmp_path / "pqx_state.json"
    state_path.write_text(json.dumps({"schema_version": "1.0.0", "rows": []}) + "\n", encoding="utf-8")
    packet_path = tmp_path / "bad-control-surface-gap-packet.json"
    packet_path.write_text("{ not-json", encoding="utf-8")

    result = run_pqx_slice(
        step_id="AI-01",
        roadmap_path=Path("docs/roadmap/system_roadmap.md"),
        state_path=state_path,
        runs_root=tmp_path / "runs",
        pqx_output_text="x",
        control_surface_gap_packet_ref=str(packet_path),
        clock=FixedClock(),
    )

    assert result["status"] == "blocked"
    assert result["block_type"] == "CONTROL_SURFACE_GAP_PACKET_INVALID"


def test_run_pqx_slice_blocks_when_control_surface_gap_packet_decision_is_block(tmp_path: Path) -> None:
    state_path = tmp_path / "pqx_state.json"
    state_path.write_text(json.dumps({"schema_version": "1.0.0", "rows": []}) + "\n", encoding="utf-8")
    packet_path = tmp_path / "control-surface-gap-packet-block.json"
    packet = _gap_packet(overall_decision="BLOCK")
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    result = run_pqx_slice(
        step_id="AI-01",
        roadmap_path=Path("docs/roadmap/system_roadmap.md"),
        state_path=state_path,
        runs_root=tmp_path / "runs",
        pqx_output_text="x",
        control_surface_gap_packet_ref=str(packet_path),
        clock=FixedClock(),
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "control_surface_gap_packet_block"
    assert result["blocking_gaps"] == packet["gaps"]


def test_run_pqx_slice_accepts_valid_allow_control_surface_gap_packet(tmp_path: Path) -> None:
    state_path = tmp_path / "pqx_state.json"
    state_path.write_text(json.dumps({"schema_version": "1.0.0", "rows": []}) + "\n", encoding="utf-8")
    packet_path = tmp_path / "control-surface-gap-packet-allow.json"
    packet_path.write_text(json.dumps(_gap_packet(overall_decision="ALLOW")), encoding="utf-8")

    result = run_pqx_slice(
        step_id="AI-01",
        roadmap_path=Path("docs/roadmap/system_roadmap.md"),
        state_path=state_path,
        runs_root=tmp_path / "runs",
        pqx_output_text="x",
        control_surface_gap_packet_ref=str(packet_path),
        clock=FixedClock(),
    )

    assert result["status"] == "complete"
