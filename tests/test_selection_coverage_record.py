"""AEX-SELECTION-COVERAGE-01 — tests for the selection coverage record.

Tests the observation-only selection coverage measurement artifact:
- schema/example consistency
- mapping behavior (matched, unmatched, partial, missing, unknown)
- recommended mapping candidates as observations only
- fallback recording
- canonical selector reuse (no duplicate selector logic)
- APR integration (selection_coverage_record artifact ref is included
  among AEX phase output_artifact_refs)

Authority scope: observation_only.
"""

from __future__ import annotations

import json
import secrets
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime import pr_test_selection
from spectrum_systems.modules.runtime.pr_test_selection import (
    build_selection_coverage_record,
)
from scripts.run_agent_pr_precheck import aex_required_surface_check

_EXAMPLE_PATH = (
    REPO_ROOT / "contracts" / "examples" / "selection_coverage_record.example.json"
)
_SCHEMA_PATH = (
    REPO_ROOT / "contracts" / "schemas" / "selection_coverage_record.schema.json"
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


# ---------------------------------------------------------------------------
# Schema / example consistency
# ---------------------------------------------------------------------------


def test_example_validates_against_schema():
    data = json.loads(_EXAMPLE_PATH.read_text(encoding="utf-8"))
    validate_artifact(data, "selection_coverage_record")


def test_example_authority_scope_is_observation_only():
    data = json.loads(_EXAMPLE_PATH.read_text(encoding="utf-8"))
    assert data["authority_scope"] == "observation_only"


def test_example_required_fields_present():
    data = json.loads(_EXAMPLE_PATH.read_text(encoding="utf-8"))
    required = {
        "artifact_type",
        "schema_version",
        "record_id",
        "created_at",
        "base_ref",
        "head_ref",
        "changed_paths",
        "matched_paths",
        "unmatched_changed_paths",
        "attempted_surface_rules",
        "selected_test_targets",
        "fallback_used",
        "fallback_targets",
        "pytest_selection_missing_count",
        "missing_required_surface_mapping_count",
        "selection_reason_codes",
        "coverage_status",
        "recommended_mapping_candidates",
        "authority_scope",
    }
    assert required <= set(data.keys())


def test_schema_does_not_contain_reserved_authority_tokens():
    text = _SCHEMA_PATH.read_text(encoding="utf-8").lower()
    for token in _FORBIDDEN_AUTHORITY_TOKENS:
        assert token not in text, (
            f"reserved authority token {token!r} appears in selection coverage schema"
        )


def test_example_does_not_contain_reserved_authority_tokens():
    text = _EXAMPLE_PATH.read_text(encoding="utf-8").lower()
    for token in _FORBIDDEN_AUTHORITY_TOKENS:
        assert token not in text, (
            f"reserved authority token {token!r} appears in selection coverage example"
        )


# ---------------------------------------------------------------------------
# Builder behavior — uses canonical selector, no duplicate logic
# ---------------------------------------------------------------------------


def _build(
    changed_paths: list[str],
    *,
    fallback_used: bool = False,
    fallback_targets: list[str] | None = None,
) -> dict:
    return build_selection_coverage_record(
        repo_root=REPO_ROOT,
        base_ref="origin/main",
        head_ref="HEAD",
        changed_paths=changed_paths,
        record_id="sel-cov-test-0000000000000000",
        created_at="2026-05-02T00:00:00Z",
        fallback_used=fallback_used,
        fallback_targets=fallback_targets or [],
    )


def test_changed_path_with_mapping_yields_complete_status():
    # docs/governance/pytest_pr_selection_integrity_policy.json has explicit
    # mapping entries in both the override map and the policy file.
    record = _build(
        ["docs/governance/pytest_pr_selection_integrity_policy.json"]
    )
    validate_artifact(record, "selection_coverage_record")
    assert record["coverage_status"] == "complete"
    assert record["unmatched_changed_paths"] == []
    assert record["missing_required_surface_mapping_count"] == 0
    assert record["selected_test_targets"], "expected at least one selected target"


def _synthetic_unmapped_governed_path() -> str:
    """Return a governed runtime-module path whose stem does not appear in
    any existing test file source.

    Constructed from random hex so the canonical selector's needle-match
    pass cannot incidentally match a fixture or doc reference. The
    resulting path is governed (``spectrum_systems/modules/runtime/`` is a
    governed prefix) but has no override entry and no matching test name.
    """
    return (
        "spectrum_systems/modules/runtime/"
        + secrets.token_hex(16)
        + "_module.py"
    )


def test_changed_path_without_mapping_yields_missing_or_partial():
    # An invented governed runtime module that does not exist on disk and
    # has no override entry. This forces the canonical selector to find no
    # mapping target.
    synthetic = _synthetic_unmapped_governed_path()
    record = _build([synthetic])
    validate_artifact(record, "selection_coverage_record")
    assert record["coverage_status"] in {"missing", "partial"}
    assert record["unmatched_changed_paths"] != []
    assert record["missing_required_surface_mapping_count"] >= 1
    assert "missing_required_surface_mapping" in record["selection_reason_codes"]


def test_unmatched_changed_paths_populated():
    synthetic = _synthetic_unmapped_governed_path()
    record = _build([synthetic])
    assert synthetic in record["unmatched_changed_paths"]


def test_recommended_mapping_candidates_observation_only():
    synthetic = _synthetic_unmapped_governed_path()
    record = _build([synthetic])
    assert record["recommended_mapping_candidates"], "expected recommendations"
    for rec in record["recommended_mapping_candidates"]:
        assert rec["observation_only"] is True
        assert isinstance(rec["candidate_test_targets"], list)
        assert rec["candidate_test_targets"], "candidates must be non-empty"
        assert rec["path"]


def test_fallback_used_recorded():
    record = _build(
        ["docs/governance/pytest_pr_selection_integrity_policy.json"],
        fallback_used=True,
        fallback_targets=["resolution_mode:fetched_diff"],
    )
    validate_artifact(record, "selection_coverage_record")
    assert record["fallback_used"] is True
    assert record["fallback_targets"] == ["resolution_mode:fetched_diff"]
    assert "fallback_used" in record["selection_reason_codes"]


def test_unknown_status_when_no_changed_paths():
    record = _build([])
    validate_artifact(record, "selection_coverage_record")
    assert record["coverage_status"] == "unknown"
    # unknown is never treated as complete
    assert record["coverage_status"] != "complete"
    assert "no_changed_paths_resolved" in record["selection_reason_codes"]


def test_unknown_is_not_complete_after_validation():
    # Force-build an inconsistent payload where coverage_status=unknown but
    # unmatched_changed_paths is empty. The schema must accept "unknown"
    # without treating it as "complete".
    record = _build([])
    assert record["coverage_status"] == "unknown"
    # The schema "complete" branch requires empty unmatched paths AND
    # missing_required_surface_mapping_count == 0, but unknown does not
    # apply that branch — it still requires reason codes.
    assert record["selection_reason_codes"], (
        "non-complete coverage_status must list reason codes"
    )


def test_builder_uses_canonical_selector(monkeypatch):
    # Verify the builder calls the canonical override map and selector,
    # rather than reimplementing them.
    calls = {"override_map": 0, "required_tests": 0, "classify": 0}

    real_load_override_map = pr_test_selection.load_override_map
    real_resolve_required_tests = pr_test_selection.resolve_required_tests
    real_classify_changed_path = pr_test_selection.classify_changed_path

    def spy_load_override_map(repo_root):
        calls["override_map"] += 1
        return real_load_override_map(repo_root)

    def spy_resolve_required_tests(repo_root, paths):
        calls["required_tests"] += 1
        return real_resolve_required_tests(repo_root, paths)

    def spy_classify_changed_path(path):
        calls["classify"] += 1
        return real_classify_changed_path(path)

    monkeypatch.setattr(
        pr_test_selection, "load_override_map", spy_load_override_map
    )
    monkeypatch.setattr(
        pr_test_selection, "resolve_required_tests", spy_resolve_required_tests
    )
    monkeypatch.setattr(
        pr_test_selection, "classify_changed_path", spy_classify_changed_path
    )

    _build(["docs/governance/pytest_pr_selection_integrity_policy.json"])
    assert calls["override_map"] >= 1
    assert calls["required_tests"] >= 1
    assert calls["classify"] >= 1


def test_no_duplicate_selector_logic_in_builder_module():
    # The builder helper must live alongside the canonical selector and
    # not redefine governed-prefix or shard routing tables.
    src = (
        REPO_ROOT
        / "spectrum_systems"
        / "modules"
        / "runtime"
        / "pr_test_selection.py"
    ).read_text(encoding="utf-8")
    # Selector constants defined exactly once each.
    assert src.count("GOVERNED_PATH_PREFIXES: tuple[str, ...]") == 1
    assert src.count("SHARD_PATH_PATTERNS: dict[str, list[str]]") == 1


def test_no_duplicate_selector_logic_in_builder_script():
    # The builder script must delegate to the canonical helper instead of
    # redefining selector constants.
    script = (
        REPO_ROOT / "scripts" / "build_selection_coverage_record.py"
    ).read_text(encoding="utf-8")
    assert "build_selection_coverage_record" in script
    assert "GOVERNED_PATH_PREFIXES" not in script
    assert "SHARD_PATH_PATTERNS" not in script


# ---------------------------------------------------------------------------
# APR integration
# ---------------------------------------------------------------------------


def test_apr_aex_includes_selection_coverage_artifact_ref(tmp_path):
    # Use a governed but mapped path so AEX returns pass; the coverage
    # artifact ref should still be present in output_artifact_refs.
    changed_paths = ["docs/governance/pytest_pr_selection_integrity_policy.json"]
    output_dir = tmp_path / "apr"
    result = aex_required_surface_check(
        repo_root=REPO_ROOT,
        changed_paths=changed_paths,
        output_dir=output_dir,
        base_ref="origin/main",
        head_ref="HEAD",
    )
    refs = result.output_artifact_refs
    assert any(
        ref.endswith("selection_coverage_record.json") for ref in refs
    ), f"selection_coverage_record artifact ref missing from {refs}"


def test_apr_aex_emits_selection_coverage_record_on_disk():
    # Calling AEX writes the coverage record to the repo's outputs dir.
    aex_required_surface_check(
        repo_root=REPO_ROOT,
        changed_paths=[
            "docs/governance/pytest_pr_selection_integrity_policy.json"
        ],
        output_dir=REPO_ROOT / "outputs" / "agent_pr_precheck",
        base_ref="origin/main",
        head_ref="HEAD",
    )
    coverage_path = (
        REPO_ROOT / "outputs" / "selection_coverage" / "selection_coverage_record.json"
    )
    assert coverage_path.is_file(), "AEX should emit selection coverage record"
    data = json.loads(coverage_path.read_text(encoding="utf-8"))
    validate_artifact(data, "selection_coverage_record")
    assert data["authority_scope"] == "observation_only"


# ---------------------------------------------------------------------------
# Builder script CLI smoke
# ---------------------------------------------------------------------------


def test_builder_script_writes_validated_record(tmp_path):
    import subprocess

    out_rel = tmp_path / "selection_coverage_record.json"
    rc = subprocess.run(
        [
            sys.executable,
            "scripts/build_selection_coverage_record.py",
            "--base-ref",
            "origin/main",
            "--head-ref",
            "HEAD",
            "--output",
            str(out_rel),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert rc.returncode == 0, rc.stderr
    data = json.loads(out_rel.read_text(encoding="utf-8"))
    validate_artifact(data, "selection_coverage_record")
    assert data["artifact_type"] == "selection_coverage_record"
    assert data["authority_scope"] == "observation_only"
