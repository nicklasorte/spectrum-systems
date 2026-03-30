from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.orchestration.drift_remediation import (
    DriftRemediationError,
    build_drift_remediation_artifact,
    load_drift_remediation_policy,
    normalize_blocking_category,
)


_REPO_ROOT = Path(__file__).resolve().parents[1]


def _manifest() -> dict:
    return {
        "cycle_id": "cycle-test",
        "current_state": "execution_complete_unreviewed",
        "updated_at": "2026-03-30T00:00:00Z",
        "strategy_authority": {"path": "docs/architecture/system_strategy.md", "version": "2026-03-30"},
        "source_authorities": [
            {
                "source_id": "SRE-MAPPING",
                "path": "docs/source_structured/mapping_google_sre_reliability_principles_to_spectrum_systems.json",
            }
        ],
    }


def _decision() -> dict:
    return {
        "decision_id": "f" * 64,
        "cycle_id": "cycle-test",
        "current_state": "execution_complete_unreviewed",
        "blocking": True,
        "blocking_reasons": ["drift detected requires remediation"],
        "required_inputs_missing": [],
        "drift_detected": True,
        "drift_reasons": ["drift_detection_result_path:exceeds_threshold"],
    }


def test_valid_policy_loads() -> None:
    policy, policy_hash = load_drift_remediation_policy()
    assert policy["policy_id"] == "DRIFT_REMEDIATION_POLICY"
    assert len(policy_hash) == 64


def test_invalid_policy_fails_closed(tmp_path: Path) -> None:
    bad = tmp_path / "bad_policy.json"
    bad.write_text(json.dumps({"policy_id": "DRIFT_REMEDIATION_POLICY"}), encoding="utf-8")
    with pytest.raises(DriftRemediationError):
        load_drift_remediation_policy(bad)


def test_ambiguous_routing_fails_closed(tmp_path: Path) -> None:
    payload = json.loads((_REPO_ROOT / "contracts" / "examples" / "drift_remediation_policy.json").read_text())
    payload["category_mappings"].append(payload["category_mappings"][0])
    path = tmp_path / "dup_policy.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(DriftRemediationError):
        load_drift_remediation_policy(path)


def test_deterministic_remediation_artifact_generation() -> None:
    policy, policy_hash = load_drift_remediation_policy()
    first = build_drift_remediation_artifact(manifest=_manifest(), decision=_decision(), policy=policy, policy_hash=policy_hash)
    second = build_drift_remediation_artifact(manifest=_manifest(), decision=_decision(), policy=policy, policy_hash=policy_hash)
    assert first["remediation_id"] == second["remediation_id"]


def test_category_normalization() -> None:
    category = normalize_blocking_category(
        decision={
            **_decision(),
            "drift_detected": False,
            "required_inputs_missing": ["strategy_authority.path"],
            "blocking_reasons": ["missing required governance signals"],
        },
        manifest=_manifest(),
    )
    assert category == "missing_strategy_authority"
