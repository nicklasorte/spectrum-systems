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
    compute_balancing_findings,
    compute_shard_timing_summary,
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
# Shard timing observations + balancing findings (PAR-BALANCE-01)
# ---------------------------------------------------------------------------


def _shard_artifact(
    *,
    shard_name: str,
    status: str = "pass",
    duration_seconds: float = 1.0,
    selected_tests: list[str] | None = None,
    output_artifact_refs: list[str] | None = None,
    reason_codes: list[str] | None = None,
    exit_code: int | None = 0,
    command: str | None = "python -m pytest -q",
) -> dict[str, Any]:
    artifact = {
        "artifact_type": "pr_test_shard_result",
        "schema_version": "1.0.0",
        "shard_name": shard_name,
        "status": status,
        "selected_tests": list(selected_tests or []),
        "command": command,
        "exit_code": exit_code,
        "duration_seconds": float(duration_seconds),
        "output_artifact_refs": list(
            output_artifact_refs
            or [f"outputs/pr_test_shards/{shard_name}.json"]
        ),
        "reason_codes": list(reason_codes or []),
        "created_at": "2026-05-01T00:00:00Z",
        "authority_scope": "observation_only",
    }
    if status != "pass" and not artifact["reason_codes"]:
        artifact["reason_codes"] = [f"placeholder_{status}"]
    return artifact


def test_shard_result_records_duration_seconds(tmp_path: Path, monkeypatch):
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
    assert isinstance(artifact["duration_seconds"], float)
    assert artifact["duration_seconds"] >= 0.0


def test_shard_skipped_artifact_records_duration_seconds(tmp_path: Path):
    artifact = run_shard(
        shard_name="contract",
        selected_tests=[],
        selector_status="empty_allowed",
        output_dir=tmp_path,
        repo_root=REPO_ROOT,
    )
    assert "duration_seconds" in artifact
    assert isinstance(artifact["duration_seconds"], float)


def test_summary_includes_timing_fields(tmp_path: Path):
    artifacts = {
        "contract": _shard_artifact(
            shard_name="contract",
            duration_seconds=10.0,
            selected_tests=["tests/a.py"],
        ),
        "governance": _shard_artifact(
            shard_name="governance",
            duration_seconds=2.0,
            selected_tests=["tests/b.py"],
        ),
    }
    summary = _build_summary(
        base_ref="origin/main",
        head_ref="HEAD",
        artifacts_by_shard=artifacts,
        required_shards=("contract", "governance"),
        output_dir=tmp_path,
    )
    for key in (
        "total_duration_seconds",
        "max_shard_duration_seconds",
        "min_shard_duration_seconds",
        "shard_duration_by_name",
        "slowest_shard",
        "imbalance_ratio",
        "balancing_findings",
    ):
        assert key in summary, f"summary missing field: {key}"
    assert summary["total_duration_seconds"] == pytest.approx(12.0)
    assert summary["shard_duration_by_name"] == {"contract": 10.0, "governance": 2.0}


def test_summary_records_slowest_shard(tmp_path: Path):
    artifacts = {
        "contract": _shard_artifact(
            shard_name="contract",
            duration_seconds=3.0,
            selected_tests=["tests/a.py"],
        ),
        "governance": _shard_artifact(
            shard_name="governance",
            duration_seconds=12.0,
            selected_tests=["tests/b.py"],
        ),
    }
    summary = _build_summary(
        base_ref="origin/main",
        head_ref="HEAD",
        artifacts_by_shard=artifacts,
        required_shards=("contract", "governance"),
        output_dir=tmp_path,
    )
    assert summary["slowest_shard"] == "governance"
    assert summary["max_shard_duration_seconds"] == pytest.approx(12.0)


def test_summary_imbalance_ratio_is_max_over_min(tmp_path: Path):
    artifacts = {
        "contract": _shard_artifact(
            shard_name="contract",
            duration_seconds=2.0,
            selected_tests=["tests/a.py"],
        ),
        "governance": _shard_artifact(
            shard_name="governance",
            duration_seconds=10.0,
            selected_tests=["tests/b.py"],
        ),
    }
    summary = _build_summary(
        base_ref="origin/main",
        head_ref="HEAD",
        artifacts_by_shard=artifacts,
        required_shards=("contract", "governance"),
        output_dir=tmp_path,
    )
    assert summary["imbalance_ratio"] == pytest.approx(5.0)


def test_summary_skipped_and_missing_shards_do_not_corrupt_ratio(tmp_path: Path):
    """Skipped/missing/unknown shards must be excluded from the imbalance ratio."""
    artifacts = {
        "contract": _shard_artifact(
            shard_name="contract",
            duration_seconds=4.0,
            selected_tests=["tests/a.py"],
        ),
        "governance": _shard_artifact(
            shard_name="governance",
            status="skipped",
            duration_seconds=0.001,
            selected_tests=[],
            command=None,
            exit_code=None,
            reason_codes=["empty_allowed_by_selector"],
        ),
        "runtime_core": _shard_artifact(
            shard_name="runtime_core",
            status="missing",
            duration_seconds=0.0,
            command=None,
            exit_code=None,
            reason_codes=["selector_blocked_shard"],
        ),
        "changed_scope": _shard_artifact(
            shard_name="changed_scope",
            duration_seconds=8.0,
            selected_tests=["tests/c.py"],
        ),
    }
    summary = _build_summary(
        base_ref="origin/main",
        head_ref="HEAD",
        artifacts_by_shard=artifacts,
        required_shards=("contract", "changed_scope"),
        output_dir=tmp_path,
    )
    assert summary["max_shard_duration_seconds"] == pytest.approx(8.0)
    assert summary["min_shard_duration_seconds"] == pytest.approx(4.0)
    assert summary["imbalance_ratio"] == pytest.approx(2.0)
    assert summary["slowest_shard"] == "changed_scope"


def test_summary_all_skipped_emits_null_ratio(tmp_path: Path):
    artifacts = {
        "contract": _shard_artifact(
            shard_name="contract",
            status="skipped",
            duration_seconds=0.0,
            selected_tests=[],
            command=None,
            exit_code=None,
            reason_codes=["empty_allowed_by_selector"],
        ),
        "governance": _shard_artifact(
            shard_name="governance",
            status="skipped",
            duration_seconds=0.0,
            selected_tests=[],
            command=None,
            exit_code=None,
            reason_codes=["empty_allowed_by_selector"],
        ),
    }
    summary = _build_summary(
        base_ref="origin/main",
        head_ref="HEAD",
        artifacts_by_shard=artifacts,
        required_shards=("contract", "governance"),
        output_dir=tmp_path,
    )
    assert summary["imbalance_ratio"] is None
    assert summary["slowest_shard"] is None
    assert summary["max_shard_duration_seconds"] is None
    assert summary["min_shard_duration_seconds"] is None
    assert summary["balancing_findings"] == []


def test_balancing_findings_emitted_when_one_shard_is_slow(tmp_path: Path):
    artifacts = {
        "contract": _shard_artifact(
            shard_name="contract",
            duration_seconds=1.0,
            selected_tests=["tests/a.py"],
        ),
        "governance": _shard_artifact(
            shard_name="governance",
            duration_seconds=1.0,
            selected_tests=["tests/b.py"],
        ),
        "changed_scope": _shard_artifact(
            shard_name="changed_scope",
            duration_seconds=20.0,
            selected_tests=["tests/c.py"],
        ),
    }
    findings = compute_balancing_findings(artifacts)
    codes = [f["code"] for f in findings]
    assert "slowest_shard_observed" in codes
    over_median = [f for f in findings if f["code"] == "shard_duration_over_2x_median"]
    assert any(f["shard"] == "changed_scope" for f in over_median)
    slowest = [f for f in findings if f["code"] == "slowest_shard_observed"]
    assert slowest and slowest[0]["shard"] == "changed_scope"


def test_balancing_findings_emit_selected_tests_count_skew():
    artifacts = {
        "contract": _shard_artifact(
            shard_name="contract",
            duration_seconds=1.0,
            selected_tests=["tests/a.py"],
        ),
        "changed_scope": _shard_artifact(
            shard_name="changed_scope",
            duration_seconds=2.0,
            selected_tests=[f"tests/c{i}.py" for i in range(10)],
        ),
    }
    findings = compute_balancing_findings(artifacts)
    skew = [f for f in findings if f["code"] == "selected_tests_count_skew"]
    assert skew, "selected_tests_count_skew finding expected for 10x skew"
    assert skew[0]["shard"] == "changed_scope"
    assert skew[0]["details"]["max_selected_tests"] == 10
    assert skew[0]["details"]["min_selected_tests"] == 1


def test_balancing_findings_empty_when_balanced():
    artifacts = {
        "contract": _shard_artifact(
            shard_name="contract",
            duration_seconds=1.0,
            selected_tests=["tests/a.py"],
        ),
        "governance": _shard_artifact(
            shard_name="governance",
            duration_seconds=1.0,
            selected_tests=["tests/b.py"],
        ),
    }
    findings = compute_balancing_findings(artifacts)
    # The slowest_shard_observed marker is informational and always emitted
    # when there is at least one active shard. Substantive imbalance
    # findings should be empty in this balanced case.
    codes = [f["code"] for f in findings]
    assert codes == ["slowest_shard_observed"]


def test_compute_shard_timing_summary_matches_summary_fields():
    artifacts = {
        "contract": _shard_artifact(
            shard_name="contract",
            duration_seconds=4.5,
            selected_tests=["tests/a.py"],
        ),
        "governance": _shard_artifact(
            shard_name="governance",
            duration_seconds=1.5,
            selected_tests=["tests/b.py"],
        ),
    }
    timing = compute_shard_timing_summary(artifacts)
    assert timing["total_duration_seconds"] == pytest.approx(6.0)
    assert timing["max_shard_duration_seconds"] == pytest.approx(4.5)
    assert timing["min_shard_duration_seconds"] == pytest.approx(1.5)
    assert timing["slowest_shard"] == "contract"
    assert timing["imbalance_ratio"] == pytest.approx(3.0)
    assert timing["shard_duration_by_name"] == {
        "contract": 4.5,
        "governance": 1.5,
    }


def test_summary_does_not_drop_selected_tests(tmp_path: Path):
    """Balancing findings must observe imbalance only — not move tests."""
    contract_tests = ["tests/test_contract_one.py", "tests/test_contract_two.py"]
    governance_tests = ["tests/test_governance_one.py"]
    artifacts = {
        "contract": _shard_artifact(
            shard_name="contract",
            duration_seconds=10.0,
            selected_tests=contract_tests,
        ),
        "governance": _shard_artifact(
            shard_name="governance",
            duration_seconds=1.0,
            selected_tests=governance_tests,
        ),
    }
    summary = _build_summary(
        base_ref="origin/main",
        head_ref="HEAD",
        artifacts_by_shard=artifacts,
        required_shards=("contract", "governance"),
        output_dir=tmp_path,
    )
    # Findings must not strip tests from the per-shard artifacts.
    assert artifacts["contract"]["selected_tests"] == contract_tests
    assert artifacts["governance"]["selected_tests"] == governance_tests
    # And shard_status fields must remain unchanged by the balancing pass.
    assert summary["shard_status"] == {"contract": "pass", "governance": "pass"}


def test_balancing_findings_preserve_shard_status(tmp_path: Path):
    artifacts = {
        "contract": _shard_artifact(
            shard_name="contract",
            duration_seconds=10.0,
            selected_tests=["tests/a.py"],
        ),
        "governance": _shard_artifact(
            shard_name="governance",
            status="fail",
            duration_seconds=2.0,
            selected_tests=["tests/b.py"],
            exit_code=1,
            reason_codes=["pytest_returncode_1"],
        ),
        "changed_scope": _shard_artifact(
            shard_name="changed_scope",
            status="skipped",
            duration_seconds=0.0,
            selected_tests=[],
            command=None,
            exit_code=None,
            reason_codes=["empty_allowed_by_selector"],
        ),
    }
    summary = _build_summary(
        base_ref="origin/main",
        head_ref="HEAD",
        artifacts_by_shard=artifacts,
        required_shards=("contract", "governance", "changed_scope"),
        output_dir=tmp_path,
    )
    # shard_status reflects the per-shard artifact status. The balancing
    # pass adds findings only and never rewrites it.
    assert summary["shard_status"] == {
        "contract": "pass",
        "governance": "fail",
        "changed_scope": "skipped",
    }
    # Existing fail-closed semantics are preserved.
    assert summary["overall_status"] == "block"
    assert any(
        "governance:required_shard_failed" == r for r in summary["blocking_reasons"]
    )


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
    """Summary that reports a failed required shard must block APR.

    Uses rc=0 to exercise APR's summary-content path. The non-zero rc
    fail-closed path is covered separately by
    ``test_apr_evl_phase_blocks_on_stale_pass_summary`` and friends.
    """
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
        return 0, ""

    monkeypatch.setattr(apr_module, "_run_subprocess", _fake_run)
    result = evl_pr_test_shards(
        repo_root=REPO_ROOT,
        base_ref="origin/main",
        head_ref="HEAD",
        output_dir=tmp_path,
    )
    assert result.status == "block"
    assert "contract:required_shard_failed" in result.reason_codes


def test_apr_evl_phase_blocks_on_stale_pass_summary(
    tmp_path: Path, monkeypatch
):
    """Non-zero shard runner exit must block APR even if a stale
    summary on disk says ``overall_status=pass``.

    This is the safety bug the PAR-BATCH-01B fix targets. The shard
    runner's subprocess return code is the primary readiness signal;
    APR must not trust a stale or partially written summary as
    artifact-backed evidence when the current invocation failed.
    """
    from scripts.run_agent_pr_precheck import evl_pr_test_shards
    import scripts.run_agent_pr_precheck as apr_module

    shard_dir = REPO_ROOT / "outputs" / "pr_test_shards"
    summary_path = shard_dir / "pr_test_shards_summary.json"
    shard_dir.mkdir(parents=True, exist_ok=True)
    # Stale summary on disk says everything is fine.
    summary_path.write_text(
        json.dumps(
            {
                "artifact_type": "pr_test_shards_summary",
                "schema_version": "1.0.0",
                "base_ref": "origin/main",
                "head_ref": "HEAD",
                "shard_status": {
                    "contract": "pass",
                    "governance": "pass",
                    "changed_scope": "pass",
                },
                "required_shards": [
                    "contract",
                    "governance",
                    "changed_scope",
                ],
                "shard_artifact_refs": [
                    "outputs/pr_test_shards/contract.json",
                    "outputs/pr_test_shards/governance.json",
                    "outputs/pr_test_shards/changed_scope.json",
                ],
                "overall_status": "pass",
                "blocking_reasons": [],
                "created_at": "2026-05-01T00:00:00Z",
                "authority_scope": "observation_only",
            }
        ),
        encoding="utf-8",
    )

    # But the current shard runner subprocess crashed.
    def _fake_run(cmd, cwd):  # noqa: ARG001
        return 1, "Traceback: shard runner crashed"

    monkeypatch.setattr(apr_module, "_run_subprocess", _fake_run)
    result = evl_pr_test_shards(
        repo_root=REPO_ROOT,
        base_ref="origin/main",
        head_ref="HEAD",
        output_dir=tmp_path,
    )
    assert result.status == "block", (
        "stale pass summary must not pass APR when runner exits non-zero"
    )
    assert result.exit_code == 1
    assert "pr_test_shard_runner_failed" in result.reason_codes
    assert "pr_test_shard_summary_stale_or_untrusted" in result.reason_codes
