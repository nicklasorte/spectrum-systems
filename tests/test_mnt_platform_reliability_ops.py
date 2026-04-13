import json
from pathlib import Path

import pytest

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.platform_reliability_ops import (
    PlatformReliabilityError,
    build_mnt_red_team_round_report,
    run_mnt002_platform_reliability,
)


def _base_evidence() -> dict:
    return {
        "replay_integrity": 0.998,
        "eval_coverage": 0.99,
        "trace_completeness": 0.996,
        "certification_health": 0.995,
        "evidence_chain_completeness": 0.997,
        "drift_debt_health": 0.98,
        "burn_window_hours": 6,
        "expected_incidents": 1,
        "certification_bundle": {"status": "certified", "created_at": "2026-04-13T01:00:00Z"},
        "certification_max_age_hours": 24,
        "active_set_refs": ["policy:v2", "judgment:v4", "contract:v3"],
        "used_artifact_refs": ["policy:v2", "judgment:v4"],
        "superseded_refs": [],
        "previous_snapshot": {"slo_pass_rate": 0.8, "alert_count": 1},
        "retry_rate": 0.1,
        "backlog_depth": 5,
        "avg_latency_ms": 180,
        "duplicate_guard_count": 0,
        "trust_preserved_after_simplification": True,
        "signed_promotion_bundle": {
            "signer": "governance-signer-1",
            "payload": {"bundle_ref": "cert-bundle-1", "trace_id": "trace-abc"},
        },
        "trusted_signers": ["governance-signer-1"],
    }


def test_mnt002_bundle_builds_and_validates() -> None:
    evidence = _base_evidence()
    payload = json.dumps(evidence["signed_promotion_bundle"]["payload"], sort_keys=True, separators=(",", ":")).encode("utf-8")
    evidence["signed_promotion_bundle"]["payload_digest"] = __import__("hashlib").sha256(payload).hexdigest()

    artifact = run_mnt002_platform_reliability(evidence, now_iso="2026-04-13T02:00:00Z")

    validate_artifact(artifact, "mnt_platform_reliability_bundle")
    assert artifact["platform_reliability_review_gate"]["status"] == "pass"
    assert artifact["freeze_on_budget_exhaustion"]["status"] == "normal"
    assert artifact["signed_promotion_bundle_validation"]["status"] == "pass"


def test_mnt002_blocks_on_stale_certification_and_stale_active_set_refs() -> None:
    evidence = _base_evidence()
    evidence["certification_bundle"] = {"status": "certified", "created_at": "2026-04-10T00:00:00Z"}
    evidence["used_artifact_refs"] = ["policy:v1"]
    evidence["superseded_refs"] = ["policy:v1"]
    evidence["signed_promotion_bundle"]["payload_digest"] = "bad"

    artifact = run_mnt002_platform_reliability(evidence, now_iso="2026-04-13T02:00:00Z")

    assert artifact["continuous_certification_gate"]["status"] == "block"
    assert artifact["active_set_gate"]["status"] == "block"
    assert "policy:v1" in artifact["active_set_gate"]["stale_refs"]
    assert artifact["signed_promotion_bundle_validation"]["status"] == "block"


def test_budget_exhaustion_triggers_freeze_gate() -> None:
    evidence = _base_evidence()
    evidence.update(
        {
            "replay_integrity": 0.85,
            "eval_coverage": 0.80,
            "trace_completeness": 0.82,
            "certification_health": 0.84,
            "evidence_chain_completeness": 0.83,
            "drift_debt_health": 0.75,
            "retry_rate": 0.7,
            "backlog_depth": 90,
            "avg_latency_ms": 3500,
            "rt3_false_green_dashboard": True,
            "rt3_stale_certification_used": True,
            "rt4_active_set_ambiguity": True,
            "duplicate_guard_count": 2,
        }
    )
    evidence["signed_promotion_bundle"]["payload_digest"] = "invalid"

    artifact = run_mnt002_platform_reliability(evidence, now_iso="2026-04-13T02:00:00Z")

    assert artifact["error_budget"]["status"] == "exhausted"
    assert artifact["freeze_on_budget_exhaustion"]["status"] == "frozen"
    assert artifact["capacity_guardrails"]["retry_storm_detected"] is True
    assert "false_green_dashboard" in artifact["red_team"]["rt3_exploits"]
    assert "active_set_ambiguity" in artifact["red_team"]["rt4_exploits"]


def test_invalid_ratio_fails_closed() -> None:
    evidence = _base_evidence()
    evidence["replay_integrity"] = 1.2
    with pytest.raises(PlatformReliabilityError):
        run_mnt002_platform_reliability(evidence)


def test_red_team_round_report_validates_and_enforces_round_id() -> None:
    report = build_mnt_red_team_round_report("RT3", ["false_green_dashboard", "stale_certification_used"])
    validate_artifact(report, "mnt_red_team_round_report")

    with pytest.raises(PlatformReliabilityError):
        build_mnt_red_team_round_report("RT9", ["x"])


def test_new_contract_examples_validate() -> None:
    root = Path(__file__).resolve().parents[1]
    bundle = json.loads((root / "contracts/examples/mnt_platform_reliability_bundle.json").read_text(encoding="utf-8"))
    round_report = json.loads((root / "contracts/examples/mnt_red_team_round_report.json").read_text(encoding="utf-8"))
    validate_artifact(bundle, "mnt_platform_reliability_bundle")
    validate_artifact(round_report, "mnt_red_team_round_report")
