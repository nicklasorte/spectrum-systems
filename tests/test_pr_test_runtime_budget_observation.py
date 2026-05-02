"""EVL-RT-01 — tests for the PR test runtime budget observation artifact.

These tests assert the observation-only runtime budget contract and
its builder. The builder must:

- validate against the contract schema,
- require at least one shard_result_refs entry whenever a non-null
  shard_summary_ref is recorded (present shard evidence requires
  artifact refs),
- require at least one reason_code for budget_status unknown or
  over_budget,
- surface fallback / full-suite usage with at least one
  fallback_reason_code (never silent),
- reuse the canonical pr_test_shards_summary timing fields,
- never run pytest, mutate selection, or duplicate selector logic,
- preserve authority-safe vocabulary.

Authority scope: observation_only.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from jsonschema.exceptions import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import validate_artifact
from scripts import build_pr_test_runtime_budget_observation as builder

_EXAMPLE_PATH = (
    REPO_ROOT
    / "contracts"
    / "examples"
    / "pr_test_runtime_budget_observation.example.json"
)
_SCHEMA_PATH = (
    REPO_ROOT
    / "contracts"
    / "schemas"
    / "pr_test_runtime_budget_observation.schema.json"
)
_BUILDER_PATH = (
    REPO_ROOT / "scripts" / "build_pr_test_runtime_budget_observation.py"
)
_SELECTOR_MODULE_PATH = (
    REPO_ROOT
    / "spectrum_systems"
    / "modules"
    / "runtime"
    / "pr_test_selection.py"
)

_FORBIDDEN_AUTHORITY_TOKENS = (
    "approve",
    "approval",
    "certify",
    "certification",
    "promote",
    "promotion",
    "enforce",
    "enforcement",
    "decide",
    "decision",
    "authorize",
    "authorization",
    "verdict",
)

_SELECTOR_PRIVATE_SYMBOLS = (
    "assign_to_shard",
    "resolve_required_tests",
    "resolve_governed_surfaces",
    "build_selection_coverage_record",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_summary(
    *,
    total: float = 12.0,
    by_name: dict[str, float] | None = None,
    slowest: str | None = "governance",
    slowest_duration: float | None = 8.0,
    refs: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "artifact_type": "pr_test_shards_summary",
        "schema_version": "1.0.0",
        "base_ref": "origin/main",
        "head_ref": "HEAD",
        "shard_status": {"contract": "pass", "governance": "pass"},
        "required_shards": ["contract", "governance"],
        "shard_artifact_refs": (
            list(refs)
            if refs is not None
            else [
                "outputs/pr_test_shards/contract.json",
                "outputs/pr_test_shards/governance.json",
            ]
        ),
        "overall_status": "pass",
        "blocking_reasons": [],
        "total_duration_seconds": total,
        "max_shard_duration_seconds": slowest_duration,
        "min_shard_duration_seconds": (
            min((by_name or {"contract": 4.0, "governance": 8.0}).values())
            if (by_name or True)
            else None
        ),
        "shard_duration_by_name": (
            by_name if by_name is not None else {"contract": 4.0, "governance": 8.0}
        ),
        "slowest_shard": slowest,
        "imbalance_ratio": 2.0,
        "balancing_findings": [],
        "created_at": "2026-05-02T00:00:00Z",
        "authority_scope": "observation_only",
    }


def _make_coverage(
    *,
    selected: list[str] | None = None,
    fallback_used: bool = False,
    fallback_targets: list[str] | None = None,
    selection_reason_codes: list[str] | None = None,
    coverage_status: str = "complete",
    changed_paths: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "artifact_type": "selection_coverage_record",
        "schema_version": "1.0.0",
        "record_id": "sel-cov-test-0001",
        "created_at": "2026-05-02T00:00:00Z",
        "base_ref": "origin/main",
        "head_ref": "HEAD",
        "changed_paths": changed_paths or ["scripts/example.py"],
        "matched_paths": changed_paths or ["scripts/example.py"],
        "unmatched_changed_paths": [],
        "attempted_surface_rules": [],
        "selected_test_targets": selected
        if selected is not None
        else ["tests/test_a.py", "tests/test_b.py"],
        "fallback_used": fallback_used,
        "fallback_targets": fallback_targets or [],
        "pytest_selection_missing_count": 0,
        "missing_required_surface_mapping_count": 0,
        "selection_reason_codes": selection_reason_codes or [],
        "coverage_status": coverage_status,
        "recommended_mapping_candidates": [],
        "authority_scope": "observation_only",
    }


# ---------------------------------------------------------------------------
# 1. Schema / example consistency
# ---------------------------------------------------------------------------


def test_example_validates_against_schema() -> None:
    data = json.loads(_EXAMPLE_PATH.read_text(encoding="utf-8"))
    validate_artifact(data, "pr_test_runtime_budget_observation")


def test_example_authority_scope_is_observation_only() -> None:
    data = json.loads(_EXAMPLE_PATH.read_text(encoding="utf-8"))
    assert data["authority_scope"] == "observation_only"


def test_example_required_fields_present() -> None:
    data = json.loads(_EXAMPLE_PATH.read_text(encoding="utf-8"))
    required = {
        "artifact_type",
        "schema_version",
        "id",
        "created_at",
        "authority_scope",
        "base_ref",
        "head_ref",
        "changed_files",
        "selected_test_targets",
        "shard_result_refs",
        "shard_summary_ref",
        "full_suite_detected",
        "fallback_used",
        "fallback_reason_codes",
        "total_duration_seconds",
        "slowest_shard",
        "slowest_shard_duration_seconds",
        "shard_duration_by_name",
        "runtime_budget_seconds",
        "budget_status",
        "reason_codes",
        "improvement_recommendations",
        "evidence_hash",
    }
    missing = required - set(data.keys())
    assert not missing, f"Missing required fields: {missing}"


def test_schema_has_authority_scope_const() -> None:
    raw = _SCHEMA_PATH.read_text(encoding="utf-8")
    assert '"const": "observation_only"' in raw


# ---------------------------------------------------------------------------
# 2. Schema rules (T1, T2, T3, T9)
# ---------------------------------------------------------------------------


def _base_record() -> dict[str, Any]:
    return json.loads(_EXAMPLE_PATH.read_text(encoding="utf-8"))


def test_present_shard_summary_requires_shard_result_refs() -> None:
    record = _base_record()
    record["shard_summary_ref"] = "outputs/pr_test_shards/pr_test_shards_summary.json"
    record["shard_result_refs"] = []
    with pytest.raises(ValidationError):
        validate_artifact(record, "pr_test_runtime_budget_observation")


def test_unknown_budget_status_requires_reason_codes() -> None:
    record = _base_record()
    record["budget_status"] = "unknown"
    record["reason_codes"] = []
    record["total_duration_seconds"] = None
    record["runtime_budget_seconds"] = None
    with pytest.raises(ValidationError):
        validate_artifact(record, "pr_test_runtime_budget_observation")


def test_over_budget_status_requires_reason_codes() -> None:
    record = _base_record()
    record["budget_status"] = "over_budget"
    record["reason_codes"] = []
    record["total_duration_seconds"] = 9000.0
    record["runtime_budget_seconds"] = 300.0
    with pytest.raises(ValidationError):
        validate_artifact(record, "pr_test_runtime_budget_observation")


def test_full_suite_detected_requires_fallback_reason_codes() -> None:
    record = _base_record()
    record["full_suite_detected"] = True
    record["fallback_reason_codes"] = []
    with pytest.raises(ValidationError):
        validate_artifact(record, "pr_test_runtime_budget_observation")


def test_fallback_used_requires_fallback_reason_codes() -> None:
    record = _base_record()
    record["fallback_used"] = True
    record["fallback_reason_codes"] = []
    with pytest.raises(ValidationError):
        validate_artifact(record, "pr_test_runtime_budget_observation")


def test_authority_scope_must_be_observation_only() -> None:
    record = _base_record()
    record["authority_scope"] = "approval"
    with pytest.raises(ValidationError):
        validate_artifact(record, "pr_test_runtime_budget_observation")


# ---------------------------------------------------------------------------
# 3. Builder behavior — happy path (T5)
# ---------------------------------------------------------------------------


def test_builder_records_slowest_shard_and_durations_from_summary() -> None:
    summary = _make_summary(
        total=15.0,
        by_name={"contract": 5.0, "governance": 10.0, "changed_scope": 0.0},
        slowest="governance",
        slowest_duration=10.0,
    )
    coverage = _make_coverage()
    artifact = builder.build_runtime_budget_observation(
        base_ref="origin/main",
        head_ref="HEAD",
        shard_summary=summary,
        selection_coverage=coverage,
        runtime_budget_seconds=300.0,
        shard_summary_ref="outputs/pr_test_shards/pr_test_shards_summary.json",
    )
    validate_artifact(artifact, "pr_test_runtime_budget_observation")
    assert artifact["slowest_shard"] == "governance"
    assert artifact["slowest_shard_duration_seconds"] == 10.0
    assert artifact["total_duration_seconds"] == 15.0
    assert artifact["shard_duration_by_name"]["governance"] == 10.0
    # shard_summary_ref must appear in shard_result_refs to satisfy the
    # "present shard evidence requires artifact refs" rule.
    assert (
        "outputs/pr_test_shards/pr_test_shards_summary.json"
        in artifact["shard_result_refs"]
    )


def test_builder_within_budget_is_clean() -> None:
    summary = _make_summary(total=10.0)
    coverage = _make_coverage()
    artifact = builder.build_runtime_budget_observation(
        base_ref="origin/main",
        head_ref="HEAD",
        shard_summary=summary,
        selection_coverage=coverage,
        runtime_budget_seconds=300.0,
        shard_summary_ref="outputs/pr_test_shards/pr_test_shards_summary.json",
    )
    validate_artifact(artifact, "pr_test_runtime_budget_observation")
    assert artifact["budget_status"] == "within_budget"
    assert artifact["reason_codes"] == []


# ---------------------------------------------------------------------------
# 4. Builder behavior — over-budget (T6)
# ---------------------------------------------------------------------------


def test_builder_records_over_budget_with_reason_code() -> None:
    summary = _make_summary(total=900.0)
    coverage = _make_coverage()
    artifact = builder.build_runtime_budget_observation(
        base_ref="origin/main",
        head_ref="HEAD",
        shard_summary=summary,
        selection_coverage=coverage,
        runtime_budget_seconds=300.0,
        shard_summary_ref="outputs/pr_test_shards/pr_test_shards_summary.json",
    )
    validate_artifact(artifact, "pr_test_runtime_budget_observation")
    assert artifact["budget_status"] == "over_budget"
    assert "total_duration_seconds_over_runtime_budget" in artifact["reason_codes"]
    codes = [r["code"] for r in artifact["improvement_recommendations"]]
    assert "runtime_budget_exceeded" in codes


# ---------------------------------------------------------------------------
# 5. Builder behavior — unknown / missing inputs (T2)
# ---------------------------------------------------------------------------


def test_builder_unknown_when_summary_missing_carries_reason_codes() -> None:
    artifact = builder.build_runtime_budget_observation(
        base_ref="origin/main",
        head_ref="HEAD",
        shard_summary=None,
        selection_coverage=_make_coverage(),
        runtime_budget_seconds=300.0,
        shard_summary_ref=None,
    )
    validate_artifact(artifact, "pr_test_runtime_budget_observation")
    assert artifact["budget_status"] == "unknown"
    assert artifact["reason_codes"], "unknown budget_status must carry reason_codes"
    assert "shard_summary_artifact_missing" in artifact["reason_codes"]
    # Without shard summary, shard_summary_ref must be null (absence is
    # explicit; never silently treated as zero).
    assert artifact["shard_summary_ref"] is None


def test_builder_unknown_when_runtime_budget_missing() -> None:
    summary = _make_summary(total=12.0)
    coverage = _make_coverage()
    artifact = builder.build_runtime_budget_observation(
        base_ref="origin/main",
        head_ref="HEAD",
        shard_summary=summary,
        selection_coverage=coverage,
        runtime_budget_seconds=None,
        shard_summary_ref="outputs/pr_test_shards/pr_test_shards_summary.json",
    )
    validate_artifact(artifact, "pr_test_runtime_budget_observation")
    assert artifact["budget_status"] == "unknown"
    assert "runtime_budget_seconds_missing" in artifact["reason_codes"]


# ---------------------------------------------------------------------------
# 6. Builder behavior — fallback / full-suite detection (T4)
# ---------------------------------------------------------------------------


def test_builder_records_full_suite_when_selected_target_is_tests_dir() -> None:
    summary = _make_summary(total=120.0)
    coverage = _make_coverage(
        selected=["tests"],
        fallback_used=True,
        fallback_targets=["select_all_tests"],
        selection_reason_codes=["fallback_used"],
    )
    artifact = builder.build_runtime_budget_observation(
        base_ref="origin/main",
        head_ref="HEAD",
        shard_summary=summary,
        selection_coverage=coverage,
        runtime_budget_seconds=300.0,
        shard_summary_ref="outputs/pr_test_shards/pr_test_shards_summary.json",
    )
    validate_artifact(artifact, "pr_test_runtime_budget_observation")
    assert artifact["full_suite_detected"] is True
    assert artifact["fallback_used"] is True
    assert artifact["fallback_reason_codes"], (
        "full_suite_detected true must surface at least one fallback_reason_code"
    )
    codes = [r["code"] for r in artifact["improvement_recommendations"]]
    assert "full_suite_fallback_observed" in codes


def test_builder_records_fallback_when_selector_reports_fallback_only() -> None:
    summary = _make_summary(total=50.0)
    coverage = _make_coverage(
        selected=["tests/test_a.py"],
        fallback_used=True,
        fallback_targets=["resolution_mode:git_diff_unavailable"],
        selection_reason_codes=["fallback_used"],
    )
    artifact = builder.build_runtime_budget_observation(
        base_ref="origin/main",
        head_ref="HEAD",
        shard_summary=summary,
        selection_coverage=coverage,
        runtime_budget_seconds=300.0,
        shard_summary_ref="outputs/pr_test_shards/pr_test_shards_summary.json",
    )
    validate_artifact(artifact, "pr_test_runtime_budget_observation")
    assert artifact["fallback_used"] is True
    assert artifact["fallback_reason_codes"], (
        "fallback_used true must always surface at least one fallback_reason_code"
    )


def test_builder_no_full_suite_when_only_focused_targets_selected() -> None:
    summary = _make_summary(total=12.0)
    coverage = _make_coverage(
        selected=["tests/test_a.py", "tests/test_b.py"],
        fallback_used=False,
    )
    artifact = builder.build_runtime_budget_observation(
        base_ref="origin/main",
        head_ref="HEAD",
        shard_summary=summary,
        selection_coverage=coverage,
        runtime_budget_seconds=300.0,
        shard_summary_ref="outputs/pr_test_shards/pr_test_shards_summary.json",
    )
    validate_artifact(artifact, "pr_test_runtime_budget_observation")
    assert artifact["full_suite_detected"] is False
    assert artifact["fallback_used"] is False
    assert artifact["fallback_reason_codes"] == []


# ---------------------------------------------------------------------------
# 7. Builder never runs pytest, mutates selection, or duplicates selector
# logic (T7, T8)
# ---------------------------------------------------------------------------


def test_builder_does_not_invoke_subprocess_or_pytest() -> None:
    """The builder must read existing artifacts only — no test execution."""
    raw = _BUILDER_PATH.read_text(encoding="utf-8")
    # The builder must not import subprocess, invoke pytest, or perform
    # destructive filesystem mutations. We check call/import patterns
    # rather than substrings so prose mentions of "pytest" in docstrings
    # do not trigger false positives.
    forbidden_patterns = (
        "import subprocess",
        "from subprocess",
        "subprocess.run",
        "subprocess.Popen",
        "shutil.rmtree",
        "os.system(",
        '"-m", "pytest"',
        "'-m', 'pytest'",
        "pytest.main(",
    )
    for pattern in forbidden_patterns:
        assert pattern not in raw, (
            f"Builder must not reference {pattern!r} — runtime budget "
            "observation is read-only and never runs tests."
        )


def test_builder_does_not_mutate_selector_module() -> None:
    """The builder must not import private selector helpers, must not
    redefine selector entrypoints, and must not write to the selector
    module file."""
    raw = _BUILDER_PATH.read_text(encoding="utf-8")
    for symbol in _SELECTOR_PRIVATE_SYMBOLS:
        assert f"def {symbol}(" not in raw, (
            f"Builder must not redefine selector symbol {symbol!r} — no "
            "duplicate selector logic permitted."
        )
    assert "pr_test_selection" not in raw, (
        "Builder must not import the canonical selector module — it consumes "
        "selection_coverage_record artifacts only."
    )


def test_builder_reuses_canonical_summary_timing() -> None:
    """Builder must read durations from the shard summary, not recompute."""
    summary = _make_summary(
        total=99.0,
        by_name={"contract": 33.0, "governance": 66.0},
        slowest="governance",
        slowest_duration=66.0,
    )
    artifact = builder.build_runtime_budget_observation(
        base_ref="origin/main",
        head_ref="HEAD",
        shard_summary=summary,
        selection_coverage=_make_coverage(),
        runtime_budget_seconds=300.0,
        shard_summary_ref="outputs/pr_test_shards/pr_test_shards_summary.json",
    )
    assert artifact["total_duration_seconds"] == 99.0
    assert artifact["slowest_shard"] == "governance"
    assert artifact["slowest_shard_duration_seconds"] == 66.0
    assert artifact["shard_duration_by_name"] == {
        "contract": 33.0,
        "governance": 66.0,
    }


# ---------------------------------------------------------------------------
# 8. Authority-safe vocabulary preserved (T9)
# ---------------------------------------------------------------------------


def test_artifact_files_use_authority_safe_vocabulary() -> None:
    for path in (_SCHEMA_PATH, _EXAMPLE_PATH, _BUILDER_PATH):
        text = path.read_text(encoding="utf-8").lower()
        for token in _FORBIDDEN_AUTHORITY_TOKENS:
            assert token not in text, (
                f"{path.name} contains reserved authority token {token!r}; "
                "runtime budget artifact is observation_only and must not use "
                "authority vocabulary."
            )


def test_recommendations_are_observation_only() -> None:
    summary = _make_summary(total=900.0)
    coverage = _make_coverage(
        selected=["tests"],
        fallback_used=True,
        fallback_targets=["select_all_tests"],
        selection_reason_codes=["fallback_full_suite"],
    )
    artifact = builder.build_runtime_budget_observation(
        base_ref="origin/main",
        head_ref="HEAD",
        shard_summary=summary,
        selection_coverage=coverage,
        runtime_budget_seconds=300.0,
        shard_summary_ref="outputs/pr_test_shards/pr_test_shards_summary.json",
    )
    for rec in artifact["improvement_recommendations"]:
        assert rec["observation_only"] is True


# ---------------------------------------------------------------------------
# 9. Manifest registration
# ---------------------------------------------------------------------------


def test_artifact_type_is_registered_in_standards_manifest() -> None:
    manifest_path = REPO_ROOT / "contracts" / "standards-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    types = {
        c.get("artifact_type")
        for c in manifest.get("contracts", [])
        if isinstance(c, dict)
    }
    assert "pr_test_runtime_budget_observation" in types


def test_builder_writes_valid_artifact_to_disk(tmp_path: Path) -> None:
    """Sanity check: the builder writes a schema-valid artifact when
    invoked through a function that mirrors the CLI flow."""
    summary = _make_summary(total=12.0)
    coverage = _make_coverage()
    artifact = builder.build_runtime_budget_observation(
        base_ref="origin/main",
        head_ref="HEAD",
        shard_summary=summary,
        selection_coverage=coverage,
        runtime_budget_seconds=300.0,
        shard_summary_ref="outputs/pr_test_shards/pr_test_shards_summary.json",
    )
    out = tmp_path / "pr_test_runtime_budget_observation.json"
    out.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    reread = json.loads(out.read_text(encoding="utf-8"))
    validate_artifact(reread, "pr_test_runtime_budget_observation")


# ---------------------------------------------------------------------------
# 10. Builder is import-safe (does not run on import)
# ---------------------------------------------------------------------------


def test_builder_module_imports_without_side_effects() -> None:
    importlib.reload(builder)
    assert hasattr(builder, "build_runtime_budget_observation")
    assert callable(builder.build_runtime_budget_observation)
