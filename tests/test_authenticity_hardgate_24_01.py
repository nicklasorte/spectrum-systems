"""Tests for scripts/run_authenticity_hardgate_24_01.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_authenticity_hardgate_24_01.py"
ARTIFACT_ROOT = REPO_ROOT / "artifacts" / "authenticity_hardgate_24_01"
TRACE_PATH = REPO_ROOT / "artifacts" / "rdx_runs" / "AUTHENTICITY-HARDGATE-24-01-artifact-trace.json"


def _run_script() -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT_PATH)], cwd=str(REPO_ROOT), capture_output=True, text=True, check=True)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_script_emits_all_umbrella_checkpoints_and_trace() -> None:
    _run_script()

    for index in range(1, 5):
        checkpoint = ARTIFACT_ROOT / f"umbrella-{index}_checkpoint.json"
        assert checkpoint.is_file()

    trace = _load_json(TRACE_PATH)
    assert trace["execution_mode"] == "SERIAL WITH HARD CHECKPOINTS"
    assert trace["umbrella_sequence"] == ["UMBRELLA-1", "UMBRELLA-2", "UMBRELLA-3", "UMBRELLA-4"]


def test_umbrella_1_authenticity_hardening_outputs() -> None:
    _run_script()

    envelope = _load_json(ARTIFACT_ROOT / "umbrella_1" / "admission_authenticity_envelope_spec.json")
    assert envelope["owner"] == "AEX"

    handoff = _load_json(ARTIFACT_ROOT / "umbrella_1" / "attested_tlc_handoff_record.json")
    assert handoff["owner"] == "TLC"
    assert handoff["orchestration_only"] is True

    pqx_validation = _load_json(ARTIFACT_ROOT / "umbrella_1" / "repo_write_authenticity_validation_result.json")
    assert pqx_validation["owner"] == "PQX"
    assert pqx_validation["issuer_bound_authenticity"] == "pass"

    sel_gate = _load_json(ARTIFACT_ROOT / "umbrella_1" / "forged_lineage_enforcement_result.json")
    assert sel_gate["owner"] == "SEL"
    assert sel_gate["fail_closed"] is True


def test_umbrella_2_ingress_unification_outputs() -> None:
    _run_script()

    ingress_manifest = _load_json(ARTIFACT_ROOT / "umbrella_2" / "repo_write_ingress_manifest.json")
    assert ingress_manifest["owner"] == "AEX"

    bypass_guard = _load_json(ARTIFACT_ROOT / "umbrella_2" / "direct_caller_bypass_enforcement_result.json")
    assert bypass_guard["owner"] == "SEL"
    assert bypass_guard["fail_closed"] is True

    classification = _load_json(ARTIFACT_ROOT / "umbrella_2" / "repo_write_capability_classification_record.json")
    assert classification["owner"] == "PQX"
    assert classification["default_classification"] == "repo_write_class"

    tpa_policy = _load_json(ARTIFACT_ROOT / "umbrella_2" / "repo_write_capability_scope_policy.json")
    assert tpa_policy["owner"] == "TPA"
    assert tpa_policy["policy_scope_only"] is True


def test_umbrella_3_replay_protected_reentry_outputs() -> None:
    _run_script()

    forwarding = _load_json(ARTIFACT_ROOT / "umbrella_3" / "fix_reentry_lineage_forwarding_record.json")
    assert forwarding["owner"] == "TLC"
    assert forwarding["lineage_forwarded"] == ["AEX", "TLC", "TPA", "PQX"]

    replay = _load_json(ARTIFACT_ROOT / "umbrella_3" / "repo_write_replay_protection_result.json")
    assert replay["owner"] == "PQX"
    assert replay["replay_protection"] == "enforced"

    fre_bundle = _load_json(ARTIFACT_ROOT / "umbrella_3" / "replay_safe_repair_candidate_bundle.json")
    assert fre_bundle["owner"] == "FRE"
    assert fre_bundle["repair_planning_only"] is True

    continuation = _load_json(ARTIFACT_ROOT / "umbrella_3" / "reentry_continuation_decision.json")
    assert continuation["owner"] == "CDE"


def test_umbrella_4_hard_gate_evidence_closure_outputs() -> None:
    _run_script()

    completeness = _load_json(ARTIFACT_ROOT / "umbrella_4" / "hard_gate_evidence_completeness_packet.json")
    assert completeness["owner"] == "RIL"
    assert completeness["interpretation_only"] is True

    scoreboard = _load_json(ARTIFACT_ROOT / "umbrella_4" / "hard_gate_evidence_gap_scoreboard.json")
    assert scoreboard["owner"] == "PRG"
    assert scoreboard["authoritative"] is False

    readiness = _load_json(ARTIFACT_ROOT / "umbrella_4" / "certification_readiness_decision.json")
    assert readiness["owner"] == "CDE"

    projection = _load_json(ARTIFACT_ROOT / "umbrella_4" / "hard_gate_proof_projection_bundle.json")
    assert projection["owner"] == "MAP"
    assert projection["projection_only"] is True
    assert projection["semantics_invented"] is False


def test_required_reporting_cross_checks_and_closeout_are_non_empty() -> None:
    _run_script()

    required_paths = [
        ARTIFACT_ROOT / "umbrella_1" / "canonical_delivery_report_artifact.json",
        ARTIFACT_ROOT / "umbrella_1" / "canonical_review_report_artifact.json",
        ARTIFACT_ROOT / "checkpoint_summary.json",
        ARTIFACT_ROOT / "registry_alignment_result.json",
        ARTIFACT_ROOT / "closeout_artifact.json",
    ]

    for path in required_paths:
        assert path.is_file()
        assert path.stat().st_size > 2

    alignment = _load_json(ARTIFACT_ROOT / "registry_alignment_result.json")
    assert len(alignment["cross_checks"]) == 15
    assert all(status == "pass" for status in alignment["cross_checks"].values())

    closeout = _load_json(ARTIFACT_ROOT / "closeout_artifact.json")
    assert all(closeout["final_success_conditions"].values())
