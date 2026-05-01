"""Tests for PR test shard artifacts, the sequential shard runner, and
APR consumption.

Authority scope: observation_only. These tests assert the artifact-backed
shard contract introduced by PAR-BATCH-01 and confirm APR consumes shard
artifacts without recomputing selection.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.pr_test_selection import assign_to_shard
from scripts import run_pr_test_shards
from scripts.run_pr_test_shards import (
    CANONICAL_SHARDS,
    DEFAULT_REQUIRED_SHARDS,
    _build_summary,
    _select_tests_for_canonical_shard,
    _selector_status_for_shard,
    run_shard,
)

_EXAMPLE_PATH = REPO_ROOT / "contracts" / "examples" / "pr_test_shard_result.example.json"
_SCHEMA_PATH = REPO_ROOT / "contracts" / "schemas" / "pr_test_shard_result.schema.json"

_FORBIDDEN_TOP_LEVEL_KEYS = {"approve", "certify", "promote", "enforce"}


# ---------------------------------------------------------------------------
# Schema / example
# ---------------------------------------------------------------------------


def test_shard_result_example_validates_against_schema():
    data = json.loads(_EXAMPLE_PATH.read_text(encoding="utf-8"))
    validate_artifact(data, "pr_test_shard_result")


def test_shard_result_example_has_observation_only_authority_scope():
    data = json.loads(_EXAMPLE_PATH.read_text(encoding="utf-8"))
    assert data.get("authority_scope") == "observation_only"


def test_shard_result_example_has_canonical_shard_name():
    data = json.loads(_EXAMPLE_PATH.read_text(encoding="utf-8"))
    assert data["shard_name"] in CANONICAL_SHARDS


def test_shard_result_example_required_fields_present():
    data = json.loads(_EXAMPLE_PATH.read_text(encoding="utf-8"))
    required = {
        "artifact_type",
        "schema_version",
        "shard_name",
        "status",
        "selected_tests",
        "command",
        "exit_code",
        "duration_seconds",
        "output_artifact_refs",
        "reason_codes",
        "created_at",
        "authority_scope",
    }
    missing = required - set(data.keys())
    assert not missing, f"Missing required fields: {missing}"


def test_shard_result_schema_has_authority_scope_const():
    raw_text = _SCHEMA_PATH.read_text(encoding="utf-8")
    assert '"const": "observation_only"' in raw_text


def test_shard_result_cannot_have_authority_keys():
    data = json.loads(_EXAMPLE_PATH.read_text(encoding="utf-8"))
    forbidden = set(data.keys()) & _FORBIDDEN_TOP_LEVEL_KEYS
    assert not forbidden, f"Authority-violating keys: {forbidden}"


# ---------------------------------------------------------------------------
# Schema rules: pass requires output_artifact_refs; fail/missing/unknown/skipped
# require reason_codes.
# ---------------------------------------------------------------------------


def _base_artifact(**overrides: Any) -> dict[str, Any]:
    base = {
        "artifact_type": "pr_test_shard_result",
        "schema_version": "1.0.0",
        "shard_name": "contract",
        "status": "pass",
        "selected_tests": ["tests/test_x.py"],
        "command": "python -m pytest -q tests/test_x.py",
        "exit_code": 0,
        "duration_seconds": 1.0,
        "output_artifact_refs": ["outputs/pr_test_shards/contract.json"],
        "reason_codes": [],
        "created_at": "2026-05-01T00:00:00Z",
        "authority_scope": "observation_only",
    }
    base.update(overrides)
    return base


def test_pass_without_output_artifact_refs_fails_validation():
    artifact = _base_artifact(output_artifact_refs=[])
    with pytest.raises(Exception):
        validate_artifact(artifact, "pr_test_shard_result")


@pytest.mark.parametrize("status", ["fail", "missing", "unknown", "skipped"])
def test_non_pass_without_reason_codes_fails_validation(status: str):
    artifact = _base_artifact(
        status=status,
        reason_codes=[],
        exit_code=None if status != "fail" else 1,
        command=None if status != "fail" else "python -m pytest",
    )
    with pytest.raises(Exception):
        validate_artifact(artifact, "pr_test_shard_result")


def test_unknown_status_is_not_pass():
    """`unknown` must require reason_codes and never satisfy the pass rule."""
    artifact = _base_artifact(
        status="unknown",
        reason_codes=["unknown_selector_status:none"],
        exit_code=None,
        command=None,
    )
    validate_artifact(artifact, "pr_test_shard_result")
    assert artifact["status"] != "pass"


def test_status_enum_does_not_include_block():
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    enum = schema["properties"]["status"]["enum"]
    assert "block" not in enum
    assert set(enum) == {"pass", "fail", "skipped", "missing", "unknown"}


# ---------------------------------------------------------------------------
# Canonical shards
# ---------------------------------------------------------------------------


def test_canonical_shards_match_spec():
    assert CANONICAL_SHARDS == (
        "contract",
        "governance",
        "runtime_core",
        "changed_scope",
        "generated_artifacts",
        "measurement",
    )


def test_default_required_shards_subset_of_canonical():
    assert set(DEFAULT_REQUIRED_SHARDS).issubset(set(CANONICAL_SHARDS))


def test_governance_shard_assigned_for_governance_test():
    assert assign_to_shard("tests/test_governance_doc.py") == "governance"


# ---------------------------------------------------------------------------
# Shard runner: per-shard artifacts + summary
# ---------------------------------------------------------------------------


def test_skipped_shard_emits_artifact_with_reason_codes(tmp_path: Path):
    artifact = run_shard(
        shard_name="contract",
        selected_tests=[],
        selector_status="empty_allowed",
        output_dir=tmp_path,
        repo_root=REPO_ROOT,
    )
    validate_artifact(artifact, "pr_test_shard_result")
    assert artifact["status"] == "skipped"
    assert artifact["reason_codes"], "skipped status must carry reason codes"
    assert (tmp_path / "contract.json").is_file()


def test_missing_shard_emits_artifact_with_reason_codes(tmp_path: Path):
    artifact = run_shard(
        shard_name="contract",
        selected_tests=[],
        selector_status="block",
        output_dir=tmp_path,
        repo_root=REPO_ROOT,
    )
    validate_artifact(artifact, "pr_test_shard_result")
    assert artifact["status"] == "missing"
    assert "selector_blocked_shard" in artifact["reason_codes"]


def test_unknown_selector_status_emits_unknown_shard_result(tmp_path: Path):
    artifact = run_shard(
        shard_name="contract",
        selected_tests=[],
        selector_status="garbage",
        output_dir=tmp_path,
        repo_root=REPO_ROOT,
    )
    validate_artifact(artifact, "pr_test_shard_result")
    assert artifact["status"] == "unknown"
    assert artifact["reason_codes"]


def test_pass_shard_artifact_validates_with_artifact_refs(tmp_path: Path, monkeypatch):
    def _fake_run(cmd, cwd):  # noqa: ARG001
        return 0, ""

    monkeypatch.setattr(run_pr_test_shards, "_run_subprocess", _fake_run)
    artifact = run_shard(
        shard_name="contract",
        selected_tests=["tests/test_pr_test_shards.py"],
        selector_status="selected",
        output_dir=tmp_path,
        repo_root=REPO_ROOT,
    )
    validate_artifact(artifact, "pr_test_shard_result")
    assert artifact["status"] == "pass"
    assert artifact["output_artifact_refs"], "pass requires output_artifact_refs"


def test_failed_shard_artifact_blocks_summary(tmp_path: Path, monkeypatch):
    def _fake_run(cmd, cwd):  # noqa: ARG001
        return 1, "boom"

    monkeypatch.setattr(run_pr_test_shards, "_run_subprocess", _fake_run)
    fail_art = run_shard(
        shard_name="contract",
        selected_tests=["tests/test_pr_test_shards.py"],
        selector_status="selected",
        output_dir=tmp_path,
        repo_root=REPO_ROOT,
    )
    pass_art_gov = run_shard(
        shard_name="governance",
        selected_tests=[],
        selector_status="empty_allowed",
        output_dir=tmp_path,
        repo_root=REPO_ROOT,
    )
    pass_art_chg = run_shard(
        shard_name="changed_scope",
        selected_tests=[],
        selector_status="empty_allowed",
        output_dir=tmp_path,
        repo_root=REPO_ROOT,
    )

    summary = _build_summary(
        base_ref="origin/main",
        head_ref="HEAD",
        artifacts_by_shard={
            "contract": fail_art,
            "governance": pass_art_gov,
            "changed_scope": pass_art_chg,
        },
        required_shards=("contract", "governance", "changed_scope"),
        output_dir=tmp_path,
    )
    assert summary["overall_status"] == "block"
    assert any("contract:required_shard_failed" == r for r in summary["blocking_reasons"])


def test_required_shard_missing_blocks_summary(tmp_path: Path):
    pass_art_gov = run_shard(
        shard_name="governance",
        selected_tests=[],
        selector_status="empty_allowed",
        output_dir=tmp_path,
        repo_root=REPO_ROOT,
    )
    summary = _build_summary(
        base_ref="origin/main",
        head_ref="HEAD",
        artifacts_by_shard={"governance": pass_art_gov},
        required_shards=("contract", "governance", "changed_scope"),
        output_dir=tmp_path,
    )
    assert summary["overall_status"] == "block"
    reasons = " ".join(summary["blocking_reasons"])
    assert "required_shard_missing_artifact" in reasons


def test_summary_has_observation_only_authority_scope(tmp_path: Path):
    summary = _build_summary(
        base_ref="origin/main",
        head_ref="HEAD",
        artifacts_by_shard={},
        required_shards=(),
        output_dir=tmp_path,
    )
    assert summary["authority_scope"] == "observation_only"


# ---------------------------------------------------------------------------
# Selector reuse: runner does not duplicate selection logic.
# ---------------------------------------------------------------------------


def test_runner_select_uses_canonical_assign_to_shard():
    # Tests routed to the legacy "dashboard" shard by the canonical
    # selector should appear under the new "generated_artifacts" canonical
    # shard.
    all_tests = [
        "tests/test_dashboard_thing.py",
        "tests/test_governance_thing.py",
        "tests/test_contract_thing.py",
    ]
    gen = _select_tests_for_canonical_shard(all_tests, "generated_artifacts")
    gov = _select_tests_for_canonical_shard(all_tests, "governance")
    con = _select_tests_for_canonical_shard(all_tests, "contract")
    assert gen == ["tests/test_dashboard_thing.py"]
    assert gov == ["tests/test_governance_thing.py"]
    assert con == ["tests/test_contract_thing.py"]


def test_runner_does_not_redefine_assign_to_shard():
    # The runner must not ship its own copy of the routing table. We
    # encode this as: the runner module contains no SHARD_PATH_PATTERNS
    # constant. (If you legitimately need one, consolidate with
    # spectrum_systems.modules.runtime.pr_test_selection.)
    src = Path(run_pr_test_shards.__file__).read_text(encoding="utf-8")
    assert "SHARD_PATH_PATTERNS" not in src, (
        "run_pr_test_shards.py must not redefine SHARD_PATH_PATTERNS — "
        "reuse pr_test_selection.assign_to_shard."
    )


def test_selector_status_for_shard_returns_expected_values():
    # No changed paths -> empty_allowed for any shard.
    assert (
        _selector_status_for_shard(
            canonical_shard="contract",
            governed_surfaces=[],
            selected_tests=[],
            changed_paths=[],
            all_tests=[],
        )
        == "empty_allowed"
    )
    # Selected tests present -> selected.
    assert (
        _selector_status_for_shard(
            canonical_shard="contract",
            governed_surfaces=[{"path": "scripts/x.py"}],
            selected_tests=["tests/test_contract_x.py"],
            changed_paths=["scripts/x.py"],
            all_tests=["tests/test_contract_x.py"],
        )
        == "selected"
    )


# ---------------------------------------------------------------------------
# APR consumption
# ---------------------------------------------------------------------------


def test_apr_evl_phase_consumes_shard_artifacts(tmp_path: Path, monkeypatch):
    """APR's EVL check must consume the shard summary and surface refs."""
    from scripts.run_agent_pr_precheck import evl_pr_test_shards

    shard_dir = REPO_ROOT / "outputs" / "pr_test_shards"
    summary_path = shard_dir / "pr_test_shards_summary.json"
    contract_artifact_path = shard_dir / "contract.json"
    shard_dir.mkdir(parents=True, exist_ok=True)
    contract_artifact_path.write_text(
        json.dumps(
            _base_artifact(
                shard_name="contract",
                output_artifact_refs=["outputs/pr_test_shards/contract.json"],
            )
        ),
        encoding="utf-8",
    )
    summary = {
        "artifact_type": "pr_test_shards_summary",
        "schema_version": "1.0.0",
        "base_ref": "origin/main",
        "head_ref": "HEAD",
        "shard_status": {"contract": "pass"},
        "required_shards": ["contract"],
        "shard_artifact_refs": ["outputs/pr_test_shards/contract.json"],
        "overall_status": "pass",
        "blocking_reasons": [],
        "created_at": "2026-05-01T00:00:00Z",
        "authority_scope": "observation_only",
    }
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    def _fake_run(cmd, cwd):  # noqa: ARG001
        return 0, ""

    import scripts.run_agent_pr_precheck as apr_module

    monkeypatch.setattr(apr_module, "_run_subprocess", _fake_run)
    result = evl_pr_test_shards(
        repo_root=REPO_ROOT,
        base_ref="origin/main",
        head_ref="HEAD",
        output_dir=tmp_path,
    )
    assert result.status == "pass"
    assert result.phase == "EVL"
    assert any("pr_test_shards_summary.json" in ref for ref in result.output_artifact_refs)
    assert any("contract.json" in ref for ref in result.output_artifact_refs)


def test_apr_evl_phase_blocks_when_shard_summary_missing(tmp_path: Path, monkeypatch):
    from scripts.run_agent_pr_precheck import evl_pr_test_shards
    import scripts.run_agent_pr_precheck as apr_module

    summary_path = REPO_ROOT / "outputs" / "pr_test_shards" / "pr_test_shards_summary.json"
    if summary_path.is_file():
        summary_path.unlink()

    def _fake_run(cmd, cwd):  # noqa: ARG001
        return 1, "intentional failure"

    monkeypatch.setattr(apr_module, "_run_subprocess", _fake_run)
    result = evl_pr_test_shards(
        repo_root=REPO_ROOT,
        base_ref="origin/main",
        head_ref="HEAD",
        output_dir=tmp_path,
    )
    assert result.status == "block"
    assert "pr_test_shards_summary_missing" in result.reason_codes


def test_apr_evl_phase_blocks_when_summary_reports_failed_shard(
    tmp_path: Path, monkeypatch
):
    from scripts.run_agent_pr_precheck import evl_pr_test_shards
    import scripts.run_agent_pr_precheck as apr_module

    shard_dir = REPO_ROOT / "outputs" / "pr_test_shards"
    summary_path = shard_dir / "pr_test_shards_summary.json"
    shard_dir.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(
            {
                "artifact_type": "pr_test_shards_summary",
                "schema_version": "1.0.0",
                "base_ref": "origin/main",
                "head_ref": "HEAD",
                "shard_status": {"contract": "fail"},
                "required_shards": ["contract"],
                "shard_artifact_refs": ["outputs/pr_test_shards/contract.json"],
                "overall_status": "block",
                "blocking_reasons": ["contract:required_shard_failed"],
                "created_at": "2026-05-01T00:00:00Z",
                "authority_scope": "observation_only",
            }
        ),
        encoding="utf-8",
    )

    def _fake_run(cmd, cwd):  # noqa: ARG001
        return 1, ""

    monkeypatch.setattr(apr_module, "_run_subprocess", _fake_run)
    result = evl_pr_test_shards(
        repo_root=REPO_ROOT,
        base_ref="origin/main",
        head_ref="HEAD",
        output_dir=tmp_path,
    )
    assert result.status == "block"
    assert "contract:required_shard_failed" in result.reason_codes
