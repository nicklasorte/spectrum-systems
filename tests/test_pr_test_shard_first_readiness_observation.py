"""EVL-RT-03 — tests for the PR test shard-first readiness observation.

These tests assert the observation-only shard-first readiness contract
and its builder. The builder must:

- validate against the contract schema,
- require at least one required_shard_refs entry whenever
  shard_first_status is shard_first (focused selection always carries
  shard evidence refs),
- require a fallback_justification_ref and at least one
  fallback_reason_codes entry whenever shard_first_status is
  fallback_justified, fallback_used is true, or full_suite_detected is
  true,
- require at least one reason_codes entry whenever shard_first_status
  is missing, partial, or unknown,
- reuse the existing shard summary, selection coverage, and runtime
  budget observation artifacts (no duplicate selector / runner logic),
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
from scripts import build_pr_test_shard_first_readiness_observation as builder

_EXAMPLE_PATH = (
    REPO_ROOT
    / "contracts"
    / "examples"
    / "pr_test_shard_first_readiness_observation.example.json"
)
_SCHEMA_PATH = (
    REPO_ROOT
    / "contracts"
    / "schemas"
    / "pr_test_shard_first_readiness_observation.schema.json"
)
_BUILDER_PATH = (
    REPO_ROOT / "scripts" / "build_pr_test_shard_first_readiness_observation.py"
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
    required_shards: list[str] | None = None,
    shard_status: dict[str, str] | None = None,
    shard_artifact_refs: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "artifact_type": "pr_test_shards_summary",
        "schema_version": "1.0.0",
        "base_ref": "origin/main",
        "head_ref": "HEAD",
        "shard_status": shard_status
        if shard_status is not None
        else {"contract": "pass", "governance": "pass", "changed_scope": "pass"},
        "required_shards": required_shards
        if required_shards is not None
        else ["contract", "governance", "changed_scope"],
        "shard_artifact_refs": shard_artifact_refs
        if shard_artifact_refs is not None
        else [
            "outputs/pr_test_shards/changed_scope.json",
            "outputs/pr_test_shards/contract.json",
            "outputs/pr_test_shards/governance.json",
        ],
        "overall_status": "pass",
        "blocking_reasons": [],
        "total_duration_seconds": 12.0,
        "max_shard_duration_seconds": 8.0,
        "min_shard_duration_seconds": 2.0,
        "shard_duration_by_name": {
            "contract": 2.0,
            "governance": 8.0,
            "changed_scope": 2.0,
        },
        "slowest_shard": "governance",
        "imbalance_ratio": 4.0,
        "balancing_findings": [],
        "created_at": "2026-05-03T00:00:00Z",
        "authority_scope": "observation_only",
    }


def _make_coverage(
    *,
    selected: list[str] | None = None,
    fallback_used: bool = False,
    changed_paths: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "artifact_type": "selection_coverage_record",
        "schema_version": "1.0.0",
        "record_id": "sel-cov-test-0001",
        "created_at": "2026-05-03T00:00:00Z",
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
        "fallback_targets": [],
        "pytest_selection_missing_count": 0,
        "missing_required_surface_mapping_count": 0,
        "selection_reason_codes": [],
        "coverage_status": "complete",
        "recommended_mapping_candidates": [],
        "authority_scope": "observation_only",
    }


def _make_runtime_budget(
    *,
    fallback_used: bool = False,
    full_suite_detected: bool = False,
    fallback_reason_codes: list[str] | None = None,
    fallback_scope: str = "none",
    justification_reason_codes: list[str] | None = None,
    selection_coverage_ref: str | None = (
        "outputs/selection_coverage/selection_coverage_record.json"
    ),
    shard_summary_ref: str | None = (
        "outputs/pr_test_shards/pr_test_shards_summary.json"
    ),
    recommended_mapping_candidates: list[dict[str, Any]] | None = None,
    recommended_shard_candidates: list[dict[str, Any]] | None = None,
    omit_justification: bool = False,
) -> dict[str, Any]:
    just_codes = (
        justification_reason_codes
        if justification_reason_codes is not None
        else (fallback_reason_codes or [])
    )
    artifact = {
        "artifact_type": "pr_test_runtime_budget_observation",
        "schema_version": "1.0.0",
        "id": "pr-rt-budget-test-001",
        "created_at": "2026-05-03T00:00:00Z",
        "authority_scope": "observation_only",
        "base_ref": "origin/main",
        "head_ref": "HEAD",
        "changed_files": [],
        "selected_test_targets": [],
        "shard_result_refs": [
            "outputs/pr_test_shards/pr_test_shards_summary.json"
        ],
        "shard_summary_ref": shard_summary_ref,
        "full_suite_detected": full_suite_detected,
        "fallback_used": fallback_used,
        "fallback_reason_codes": list(fallback_reason_codes or []),
        "total_duration_seconds": 12.0,
        "slowest_shard": "governance",
        "slowest_shard_duration_seconds": 8.0,
        "shard_duration_by_name": {"governance": 8.0},
        "runtime_budget_seconds": 300.0,
        "budget_status": "within_budget",
        "reason_codes": [],
        "improvement_recommendations": [],
        "evidence_hash": "sha256:test",
    }
    if not omit_justification:
        artifact["fallback_justification"] = {
            "fallback_scope": fallback_scope,
            "fallback_used": fallback_used,
            "full_suite_detected": full_suite_detected,
            "fallback_reason_codes": list(just_codes),
            "selection_coverage_ref": selection_coverage_ref,
            "shard_summary_ref": shard_summary_ref,
            "unmatched_changed_paths": [],
            "missing_surface_mappings": [],
            "selected_test_targets": [],
            "recommended_mapping_candidates": list(
                recommended_mapping_candidates or []
            ),
            "recommended_shard_candidates": list(
                recommended_shard_candidates or []
            ),
            "evidence_hash": "sha256:justification",
        }
    return artifact


# ---------------------------------------------------------------------------
# 1. Schema / example consistency
# ---------------------------------------------------------------------------


def test_example_validates_against_schema() -> None:
    data = json.loads(_EXAMPLE_PATH.read_text(encoding="utf-8"))
    validate_artifact(data, "pr_test_shard_first_readiness_observation")


def test_example_authority_scope_is_observation_only() -> None:
    data = json.loads(_EXAMPLE_PATH.read_text(encoding="utf-8"))
    assert data["authority_scope"] == "observation_only"


def test_schema_has_authority_scope_const() -> None:
    raw = _SCHEMA_PATH.read_text(encoding="utf-8")
    assert '"const": "observation_only"' in raw


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
        "selection_coverage_ref",
        "shard_summary_ref",
        "runtime_budget_observation_ref",
        "fallback_justification_ref",
        "shard_first_status",
        "required_shard_refs",
        "missing_shard_refs",
        "failed_shard_refs",
        "fallback_used",
        "full_suite_detected",
        "fallback_reason_codes",
        "reason_codes",
        "recommended_mapping_candidates",
        "recommended_shard_candidates",
        "evidence_hash",
    }
    missing = required - set(data.keys())
    assert not missing, f"Missing required fields: {missing}"


# ---------------------------------------------------------------------------
# 2. Schema rules — shard_first / fallback_justified / missing / unknown
# ---------------------------------------------------------------------------


def _base_record() -> dict[str, Any]:
    return json.loads(_EXAMPLE_PATH.read_text(encoding="utf-8"))


def test_shard_first_status_requires_required_shard_refs() -> None:
    record = _base_record()
    record["shard_first_status"] = "shard_first"
    record["required_shard_refs"] = []
    with pytest.raises(ValidationError):
        validate_artifact(record, "pr_test_shard_first_readiness_observation")


def test_shard_first_status_forbids_fallback_used() -> None:
    record = _base_record()
    record["shard_first_status"] = "shard_first"
    record["fallback_used"] = True
    record["fallback_reason_codes"] = ["selector_reported_fallback_used"]
    record["fallback_justification_ref"] = (
        "outputs/pr_test_runtime_budget/pr_test_runtime_budget_observation.json"
    )
    with pytest.raises(ValidationError):
        validate_artifact(record, "pr_test_shard_first_readiness_observation")


def test_shard_first_status_forbids_full_suite_detected() -> None:
    record = _base_record()
    record["shard_first_status"] = "shard_first"
    record["full_suite_detected"] = True
    record["fallback_reason_codes"] = ["selected_target_full_suite:tests"]
    record["fallback_justification_ref"] = (
        "outputs/pr_test_runtime_budget/pr_test_runtime_budget_observation.json"
    )
    with pytest.raises(ValidationError):
        validate_artifact(record, "pr_test_shard_first_readiness_observation")


def test_fallback_justified_requires_fallback_justification_ref() -> None:
    record = _base_record()
    record["shard_first_status"] = "fallback_justified"
    record["fallback_used"] = True
    record["fallback_reason_codes"] = ["selector_reported_fallback_used"]
    record["fallback_justification_ref"] = None
    with pytest.raises(ValidationError):
        validate_artifact(record, "pr_test_shard_first_readiness_observation")


def test_fallback_justified_requires_fallback_reason_codes() -> None:
    record = _base_record()
    record["shard_first_status"] = "fallback_justified"
    record["fallback_used"] = True
    record["fallback_reason_codes"] = []
    record["fallback_justification_ref"] = (
        "outputs/pr_test_runtime_budget/pr_test_runtime_budget_observation.json"
    )
    with pytest.raises(ValidationError):
        validate_artifact(record, "pr_test_shard_first_readiness_observation")


def test_missing_status_requires_reason_codes() -> None:
    record = _base_record()
    record["shard_first_status"] = "missing"
    record["reason_codes"] = []
    with pytest.raises(ValidationError):
        validate_artifact(record, "pr_test_shard_first_readiness_observation")


def test_partial_status_requires_reason_codes() -> None:
    record = _base_record()
    record["shard_first_status"] = "partial"
    record["reason_codes"] = []
    with pytest.raises(ValidationError):
        validate_artifact(record, "pr_test_shard_first_readiness_observation")


def test_unknown_status_requires_reason_codes() -> None:
    record = _base_record()
    record["shard_first_status"] = "unknown"
    record["reason_codes"] = []
    with pytest.raises(ValidationError):
        validate_artifact(record, "pr_test_shard_first_readiness_observation")


def test_fallback_used_true_requires_fallback_justification_ref() -> None:
    record = _base_record()
    record["shard_first_status"] = "partial"
    record["reason_codes"] = ["partial_for_test"]
    record["fallback_used"] = True
    record["fallback_reason_codes"] = ["selector_reported_fallback_used"]
    record["fallback_justification_ref"] = None
    with pytest.raises(ValidationError):
        validate_artifact(record, "pr_test_shard_first_readiness_observation")


def test_full_suite_detected_true_requires_fallback_justification_ref() -> None:
    record = _base_record()
    record["shard_first_status"] = "partial"
    record["reason_codes"] = ["partial_for_test"]
    record["full_suite_detected"] = True
    record["fallback_reason_codes"] = ["selected_target_full_suite:tests"]
    record["fallback_justification_ref"] = None
    with pytest.raises(ValidationError):
        validate_artifact(record, "pr_test_shard_first_readiness_observation")


def test_authority_scope_must_be_observation_only() -> None:
    record = _base_record()
    record["authority_scope"] = "approval"
    with pytest.raises(ValidationError):
        validate_artifact(record, "pr_test_shard_first_readiness_observation")


def test_shard_first_status_enum_rejects_unknown_value() -> None:
    record = _base_record()
    record["shard_first_status"] = "made_up_status"
    with pytest.raises(ValidationError):
        validate_artifact(record, "pr_test_shard_first_readiness_observation")


# ---------------------------------------------------------------------------
# 3. Builder behavior — shard_first happy path
# ---------------------------------------------------------------------------


def test_builder_classifies_shard_first_when_required_refs_present() -> None:
    summary = _make_summary()
    coverage = _make_coverage()
    runtime = _make_runtime_budget()
    artifact = builder.build_shard_first_readiness_observation(
        base_ref="origin/main",
        head_ref="HEAD",
        shard_summary=summary,
        selection_coverage=coverage,
        runtime_budget=runtime,
        shard_summary_ref="outputs/pr_test_shards/pr_test_shards_summary.json",
        selection_coverage_ref="outputs/selection_coverage/selection_coverage_record.json",
        runtime_budget_observation_ref="outputs/pr_test_runtime_budget/pr_test_runtime_budget_observation.json",
    )
    validate_artifact(artifact, "pr_test_shard_first_readiness_observation")
    assert artifact["shard_first_status"] == "shard_first"
    assert artifact["fallback_used"] is False
    assert artifact["full_suite_detected"] is False
    assert artifact["required_shard_refs"], (
        "shard_first must always carry at least one required_shard_ref"
    )
    assert artifact["missing_shard_refs"] == []
    assert artifact["failed_shard_refs"] == []


def test_builder_records_shard_summary_ref_only_when_present() -> None:
    coverage = _make_coverage()
    runtime = _make_runtime_budget()
    artifact = builder.build_shard_first_readiness_observation(
        base_ref="origin/main",
        head_ref="HEAD",
        shard_summary=None,
        selection_coverage=coverage,
        runtime_budget=runtime,
        shard_summary_ref="outputs/pr_test_shards/pr_test_shards_summary.json",
        selection_coverage_ref="outputs/selection_coverage/selection_coverage_record.json",
        runtime_budget_observation_ref="outputs/pr_test_runtime_budget/pr_test_runtime_budget_observation.json",
    )
    # Without a shard summary, the ref must be null (absence is explicit).
    assert artifact["shard_summary_ref"] is None


# ---------------------------------------------------------------------------
# 4. Builder behavior — fallback_justified (broad/full-suite use is justified)
# ---------------------------------------------------------------------------


def test_builder_classifies_fallback_justified_for_full_suite_with_reason_codes() -> None:
    summary = _make_summary()
    coverage = _make_coverage(
        selected=["tests"],
        fallback_used=True,
    )
    runtime = _make_runtime_budget(
        full_suite_detected=True,
        fallback_used=True,
        fallback_reason_codes=["selected_target_full_suite:tests"],
        fallback_scope="full_suite",
    )
    artifact = builder.build_shard_first_readiness_observation(
        base_ref="origin/main",
        head_ref="HEAD",
        shard_summary=summary,
        selection_coverage=coverage,
        runtime_budget=runtime,
        shard_summary_ref="outputs/pr_test_shards/pr_test_shards_summary.json",
        selection_coverage_ref="outputs/selection_coverage/selection_coverage_record.json",
        runtime_budget_observation_ref="outputs/pr_test_runtime_budget/pr_test_runtime_budget_observation.json",
    )
    validate_artifact(artifact, "pr_test_shard_first_readiness_observation")
    assert artifact["shard_first_status"] == "fallback_justified"
    assert artifact["fallback_used"] is True
    assert artifact["full_suite_detected"] is True
    assert artifact["fallback_justification_ref"] == (
        "outputs/pr_test_runtime_budget/pr_test_runtime_budget_observation.json"
    )
    assert artifact["fallback_reason_codes"], (
        "fallback_justified must surface at least one fallback_reason_code"
    )


def test_builder_classifies_fallback_justified_for_broad_pytest() -> None:
    summary = _make_summary()
    coverage = _make_coverage(
        selected=["tests/test_a.py"],
        fallback_used=True,
    )
    runtime = _make_runtime_budget(
        fallback_used=True,
        fallback_reason_codes=["selector_reported_fallback_used"],
        fallback_scope="broad_pytest",
    )
    artifact = builder.build_shard_first_readiness_observation(
        base_ref="origin/main",
        head_ref="HEAD",
        shard_summary=summary,
        selection_coverage=coverage,
        runtime_budget=runtime,
        shard_summary_ref="outputs/pr_test_shards/pr_test_shards_summary.json",
        selection_coverage_ref="outputs/selection_coverage/selection_coverage_record.json",
        runtime_budget_observation_ref="outputs/pr_test_runtime_budget/pr_test_runtime_budget_observation.json",
    )
    validate_artifact(artifact, "pr_test_shard_first_readiness_observation")
    assert artifact["shard_first_status"] == "fallback_justified"
    assert artifact["fallback_used"] is True
    assert artifact["fallback_reason_codes"]


# ---------------------------------------------------------------------------
# 5. Builder behavior — partial / missing / unknown
# ---------------------------------------------------------------------------


def test_builder_classifies_partial_when_required_shard_status_missing() -> None:
    summary = _make_summary(
        required_shards=["contract", "governance", "changed_scope"],
        shard_status={"contract": "pass", "governance": "missing"},
        shard_artifact_refs=[
            "outputs/pr_test_shards/contract.json",
        ],
    )
    coverage = _make_coverage()
    runtime = _make_runtime_budget()
    artifact = builder.build_shard_first_readiness_observation(
        base_ref="origin/main",
        head_ref="HEAD",
        shard_summary=summary,
        selection_coverage=coverage,
        runtime_budget=runtime,
        shard_summary_ref="outputs/pr_test_shards/pr_test_shards_summary.json",
        selection_coverage_ref="outputs/selection_coverage/selection_coverage_record.json",
        runtime_budget_observation_ref="outputs/pr_test_runtime_budget/pr_test_runtime_budget_observation.json",
    )
    validate_artifact(artifact, "pr_test_shard_first_readiness_observation")
    assert artifact["shard_first_status"] == "partial"
    assert artifact["missing_shard_refs"], (
        "partial status must surface at least one missing shard"
    )
    assert artifact["reason_codes"], "partial status must surface reason codes"


def test_builder_classifies_partial_when_required_shard_failed() -> None:
    summary = _make_summary(
        required_shards=["contract", "governance", "changed_scope"],
        shard_status={
            "contract": "pass",
            "governance": "fail",
            "changed_scope": "pass",
        },
        shard_artifact_refs=[
            "outputs/pr_test_shards/contract.json",
            "outputs/pr_test_shards/governance.json",
            "outputs/pr_test_shards/changed_scope.json",
        ],
    )
    artifact = builder.build_shard_first_readiness_observation(
        base_ref="origin/main",
        head_ref="HEAD",
        shard_summary=summary,
        selection_coverage=_make_coverage(),
        runtime_budget=_make_runtime_budget(),
        shard_summary_ref="outputs/pr_test_shards/pr_test_shards_summary.json",
        selection_coverage_ref="outputs/selection_coverage/selection_coverage_record.json",
        runtime_budget_observation_ref="outputs/pr_test_runtime_budget/pr_test_runtime_budget_observation.json",
    )
    validate_artifact(artifact, "pr_test_shard_first_readiness_observation")
    assert artifact["shard_first_status"] == "partial"
    assert artifact["failed_shard_refs"]


def test_builder_classifies_unknown_when_runtime_budget_missing() -> None:
    summary = _make_summary()
    coverage = _make_coverage()
    artifact = builder.build_shard_first_readiness_observation(
        base_ref="origin/main",
        head_ref="HEAD",
        shard_summary=summary,
        selection_coverage=coverage,
        runtime_budget=None,
        shard_summary_ref="outputs/pr_test_shards/pr_test_shards_summary.json",
        selection_coverage_ref="outputs/selection_coverage/selection_coverage_record.json",
        runtime_budget_observation_ref=None,
    )
    validate_artifact(artifact, "pr_test_shard_first_readiness_observation")
    assert artifact["shard_first_status"] == "unknown"
    assert artifact["reason_codes"], (
        "unknown status must surface reason codes"
    )


def test_builder_classifies_missing_when_summary_and_runtime_budget_absent() -> None:
    artifact = builder.build_shard_first_readiness_observation(
        base_ref="origin/main",
        head_ref="HEAD",
        shard_summary=None,
        selection_coverage=None,
        runtime_budget=None,
        shard_summary_ref=None,
        selection_coverage_ref=None,
        runtime_budget_observation_ref=None,
    )
    validate_artifact(artifact, "pr_test_shard_first_readiness_observation")
    assert artifact["shard_first_status"] == "missing"
    assert artifact["reason_codes"]


def test_builder_classifies_partial_when_fallback_used_but_justification_missing() -> None:
    """Fallback signals without a justification section must NOT be treated
    as fallback_justified — partial is the correct readiness observation."""
    summary = _make_summary()
    coverage = _make_coverage(fallback_used=True)
    runtime = _make_runtime_budget(
        fallback_used=True,
        fallback_reason_codes=["selector_reported_fallback_used"],
        omit_justification=True,
    )
    artifact = builder.build_shard_first_readiness_observation(
        base_ref="origin/main",
        head_ref="HEAD",
        shard_summary=summary,
        selection_coverage=coverage,
        runtime_budget=runtime,
        shard_summary_ref="outputs/pr_test_shards/pr_test_shards_summary.json",
        selection_coverage_ref="outputs/selection_coverage/selection_coverage_record.json",
        runtime_budget_observation_ref="outputs/pr_test_runtime_budget/pr_test_runtime_budget_observation.json",
    )
    validate_artifact(artifact, "pr_test_shard_first_readiness_observation")
    assert artifact["shard_first_status"] == "partial"
    assert "fallback_justification_section_missing" in artifact["reason_codes"] or (
        "fallback_justification_ref_missing" in artifact["reason_codes"]
    )


def test_builder_partial_when_fallback_used_with_no_reason_codes() -> None:
    summary = _make_summary()
    coverage = _make_coverage(fallback_used=True)
    runtime = _make_runtime_budget(
        fallback_used=True,
        fallback_reason_codes=[],
        justification_reason_codes=[],
        fallback_scope="shard_fallback",
    )
    artifact = builder.build_shard_first_readiness_observation(
        base_ref="origin/main",
        head_ref="HEAD",
        shard_summary=summary,
        selection_coverage=coverage,
        runtime_budget=runtime,
        shard_summary_ref="outputs/pr_test_shards/pr_test_shards_summary.json",
        selection_coverage_ref="outputs/selection_coverage/selection_coverage_record.json",
        runtime_budget_observation_ref="outputs/pr_test_runtime_budget/pr_test_runtime_budget_observation.json",
    )
    validate_artifact(artifact, "pr_test_shard_first_readiness_observation")
    assert artifact["shard_first_status"] == "partial"
    assert "fallback_reason_codes_missing" in artifact["reason_codes"]


# ---------------------------------------------------------------------------
# 6. Builder is observation-only — no pytest, no selector mutation
# ---------------------------------------------------------------------------


def test_builder_does_not_invoke_subprocess_or_pytest() -> None:
    """The builder must read existing artifacts only — no test execution."""
    raw = _BUILDER_PATH.read_text(encoding="utf-8")
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
            f"Builder must not reference {pattern!r} — shard-first "
            "readiness observation is read-only and never runs tests."
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
        "Builder must not import the canonical selector module — it "
        "consumes selection_coverage_record / runtime budget artifacts only."
    )


def test_builder_does_not_mutate_shard_runner() -> None:
    raw = _BUILDER_PATH.read_text(encoding="utf-8")
    assert "run_pr_test_shards" not in raw, (
        "Builder must not import or invoke the canonical shard runner — "
        "it consumes the already-emitted pr_test_shards_summary artifact "
        "only."
    )


def test_builder_does_not_mutate_runtime_budget_builder() -> None:
    raw = _BUILDER_PATH.read_text(encoding="utf-8")
    assert "build_pr_test_runtime_budget_observation" not in raw, (
        "Builder must not import the runtime budget builder — it consumes "
        "the already-emitted pr_test_runtime_budget_observation artifact "
        "only."
    )


# ---------------------------------------------------------------------------
# 7. Authority-safe vocabulary preserved
# ---------------------------------------------------------------------------


def test_artifact_files_use_authority_safe_vocabulary() -> None:
    for path in (_SCHEMA_PATH, _EXAMPLE_PATH, _BUILDER_PATH):
        text = path.read_text(encoding="utf-8").lower()
        for token in _FORBIDDEN_AUTHORITY_TOKENS:
            assert token not in text, (
                f"{path.name} contains reserved authority token {token!r}; "
                "shard-first readiness artifact is observation_only and must "
                "not use authority vocabulary."
            )


def test_recommended_candidates_are_observation_only() -> None:
    summary = _make_summary(
        required_shards=["contract", "governance", "changed_scope"],
        shard_status={
            "contract": "pass",
            "governance": "missing",
            "changed_scope": "pass",
        },
        shard_artifact_refs=[
            "outputs/pr_test_shards/contract.json",
            "outputs/pr_test_shards/changed_scope.json",
        ],
    )
    artifact = builder.build_shard_first_readiness_observation(
        base_ref="origin/main",
        head_ref="HEAD",
        shard_summary=summary,
        selection_coverage=_make_coverage(),
        runtime_budget=_make_runtime_budget(),
        shard_summary_ref="outputs/pr_test_shards/pr_test_shards_summary.json",
        selection_coverage_ref="outputs/selection_coverage/selection_coverage_record.json",
        runtime_budget_observation_ref="outputs/pr_test_runtime_budget/pr_test_runtime_budget_observation.json",
    )
    for cand in artifact["recommended_shard_candidates"]:
        assert cand["observation_only"] is True
    for cand in artifact["recommended_mapping_candidates"]:
        assert cand["observation_only"] is True


# ---------------------------------------------------------------------------
# 8. Manifest registration
# ---------------------------------------------------------------------------


def test_artifact_type_is_registered_in_standards_manifest() -> None:
    manifest_path = REPO_ROOT / "contracts" / "standards-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    types = {
        c.get("artifact_type")
        for c in manifest.get("contracts", [])
        if isinstance(c, dict)
    }
    assert "pr_test_shard_first_readiness_observation" in types


def test_builder_writes_valid_artifact_to_disk(tmp_path: Path) -> None:
    """Sanity check: the builder output is a schema-valid artifact."""
    summary = _make_summary()
    coverage = _make_coverage()
    runtime = _make_runtime_budget()
    artifact = builder.build_shard_first_readiness_observation(
        base_ref="origin/main",
        head_ref="HEAD",
        shard_summary=summary,
        selection_coverage=coverage,
        runtime_budget=runtime,
        shard_summary_ref="outputs/pr_test_shards/pr_test_shards_summary.json",
        selection_coverage_ref="outputs/selection_coverage/selection_coverage_record.json",
        runtime_budget_observation_ref="outputs/pr_test_runtime_budget/pr_test_runtime_budget_observation.json",
    )
    out = tmp_path / "pr_test_shard_first_readiness_observation.json"
    out.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    reread = json.loads(out.read_text(encoding="utf-8"))
    validate_artifact(reread, "pr_test_shard_first_readiness_observation")


def test_builder_module_imports_without_side_effects() -> None:
    importlib.reload(builder)
    assert hasattr(builder, "build_shard_first_readiness_observation")
    assert callable(builder.build_shard_first_readiness_observation)


# ---------------------------------------------------------------------------
# 9. PR prose cannot substitute for fallback evidence
# ---------------------------------------------------------------------------


def test_pr_prose_does_not_satisfy_fallback_evidence() -> None:
    """A schema-valid record must reference a fallback_justification_ref;
    a free-text PR description / comment cannot be encoded as evidence."""
    record = _base_record()
    record["shard_first_status"] = "fallback_justified"
    record["fallback_used"] = True
    record["fallback_reason_codes"] = ["selector_reported_fallback_used"]
    # Simulate a PR-prose substitution: clearing the artifact ref while
    # claiming fallback_justified must trip the schema rule.
    record["fallback_justification_ref"] = None
    with pytest.raises(ValidationError):
        validate_artifact(record, "pr_test_shard_first_readiness_observation")


# ---------------------------------------------------------------------------
# 10. Recommended candidates carry observation_only and are dervied from
# the existing fallback_justification section (no duplicate selector logic)
# ---------------------------------------------------------------------------


def test_builder_reuses_fallback_justification_recommended_candidates() -> None:
    summary = _make_summary()
    coverage = _make_coverage(
        selected=["tests"],
        fallback_used=True,
    )
    runtime = _make_runtime_budget(
        full_suite_detected=True,
        fallback_used=True,
        fallback_reason_codes=["selected_target_full_suite:tests"],
        fallback_scope="full_suite",
        recommended_mapping_candidates=[
            {
                "path": "scripts/orphan.py",
                "candidate_test_targets": ["tests/test_orphan.py"],
                "observation_only": True,
                "rationale": "operator hint",
            }
        ],
        recommended_shard_candidates=[
            {
                "shard": "all",
                "candidate_action": "narrow_selection",
                "observation_only": True,
                "rationale": "full-suite fallback observed",
            }
        ],
    )
    artifact = builder.build_shard_first_readiness_observation(
        base_ref="origin/main",
        head_ref="HEAD",
        shard_summary=summary,
        selection_coverage=coverage,
        runtime_budget=runtime,
        shard_summary_ref="outputs/pr_test_shards/pr_test_shards_summary.json",
        selection_coverage_ref="outputs/selection_coverage/selection_coverage_record.json",
        runtime_budget_observation_ref="outputs/pr_test_runtime_budget/pr_test_runtime_budget_observation.json",
    )
    validate_artifact(artifact, "pr_test_shard_first_readiness_observation")
    assert artifact["recommended_mapping_candidates"]
    assert artifact["recommended_mapping_candidates"][0]["path"] == "scripts/orphan.py"
    actions = {
        c.get("candidate_action") for c in artifact["recommended_shard_candidates"]
    }
    assert "narrow_selection" in actions
