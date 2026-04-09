from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.orchestration.fix_plan import FixPlanError, build_fix_plan_artifact


def _manifest() -> dict:
    return {"cycle_id": "cycle-test", "current_state": "blocked", "updated_at": "2026-03-30T00:00:00Z"}


def _decision() -> dict:
    return {"decision_id": "d" * 64, "current_state": "blocked", "trace_id": "trace-test"}


def _remediation(path: str | None) -> dict:
    payload = {
        "remediation_id": "a" * 64,
        "cycle_id": "cycle-test",
        "decision_id": "d" * 64,
        "remediation_class": "roadmap_repair",
    }
    if path is not None:
        payload["fre_fix_plan_artifact_ref"] = path
    return payload


def test_requires_fre_fix_plan_reference() -> None:
    with pytest.raises(FixPlanError, match="fre_fix_plan_artifact_ref"):
        build_fix_plan_artifact(manifest=_manifest(), decision=_decision(), remediation=_remediation(None))


def test_requires_existing_fre_fix_plan_file(tmp_path: Path) -> None:
    with pytest.raises(FixPlanError, match="file"):
        build_fix_plan_artifact(
            manifest=_manifest(),
            decision=_decision(),
            remediation=_remediation(str(tmp_path / "missing_fix_plan.json")),
        )


def test_fre_artifact_must_declare_fre_policy(tmp_path: Path) -> None:
    artifact = json.loads((Path(__file__).resolve().parents[1] / "contracts" / "examples" / "fix_plan_artifact.json").read_text())
    artifact["policy_id"] = "DRIFT_REMEDIATION_POLICY"
    path = tmp_path / "fix_plan.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")
    with pytest.raises(FixPlanError, match="FRE_"):
        build_fix_plan_artifact(
            manifest=_manifest(),
            decision=_decision(),
            remediation=_remediation(str(path)),
        )


def test_accepts_schema_valid_fre_fix_plan_artifact(tmp_path: Path) -> None:
    artifact = json.loads((Path(__file__).resolve().parents[1] / "contracts" / "examples" / "fix_plan_artifact.json").read_text())
    artifact["policy_id"] = "FRE_REMEDIATION_POLICY"
    artifact["decision_id"] = "d" * 64
    path = tmp_path / "fix_plan_fre.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")
    loaded = build_fix_plan_artifact(
        manifest=_manifest(),
        decision=_decision(),
        remediation=_remediation(str(path)),
    )
    assert loaded["policy_id"] == "FRE_REMEDIATION_POLICY"
