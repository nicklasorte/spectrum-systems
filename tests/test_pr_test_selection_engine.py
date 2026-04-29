"""Tests for canonical PR test selection engine."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.pr_test_selection import (
    GOVERNED_PATH_PREFIXES,
    SHARD_NAMES,
    SHARD_PATH_PATTERNS,
    assign_to_shard,
    build_selection_artifact,
    classify_changed_path,
    compare_parity,
    is_docs_only_non_governed,
    is_governed_path,
    load_override_map,
    resolve_governed_surfaces,
    resolve_required_tests,
)


# ---------------------------------------------------------------------------
# is_governed_path
# ---------------------------------------------------------------------------


def test_is_governed_path_contracts():
    assert is_governed_path("contracts/foo.json") is True


def test_is_governed_path_scripts():
    assert is_governed_path("scripts/run_x.py") is True


def test_is_governed_path_workflows():
    assert is_governed_path(".github/workflows/pr.yml") is True


def test_is_governed_path_non_governed():
    # docs/architecture/ is NOT in GOVERNED_PATH_PREFIXES; only docs/governance/ is
    assert is_governed_path("docs/architecture/foo.md") is False


# ---------------------------------------------------------------------------
# classify_changed_path
# ---------------------------------------------------------------------------


def test_classify_changed_path_governance_doc():
    result = classify_changed_path("docs/governance/foo.json")
    assert result["is_governed"] is True
    assert result["surface"] == "governance_docs"


def test_classify_changed_path_runtime_module():
    result = classify_changed_path("spectrum_systems/modules/runtime/foo.py")
    assert result["is_governed"] is True
    assert result["surface"] == "runtime_module"


def test_classify_changed_path_workflow():
    result = classify_changed_path(".github/workflows/pr-pytest.yml")
    assert result["is_governed"] is True
    assert result["surface"] == "ci_workflow_surface"


def test_classify_changed_path_non_governed():
    result = classify_changed_path("README.md")
    assert result["is_governed"] is False


# ---------------------------------------------------------------------------
# resolve_governed_surfaces
# ---------------------------------------------------------------------------


def test_resolve_governed_surfaces_filters_ungoverned():
    paths = [
        "contracts/foo.json",
        "README.md",
        "docs/architecture/system_registry.md",
        "scripts/run_something.py",
    ]
    surfaces = resolve_governed_surfaces(paths)
    surface_paths = [s["path"] for s in surfaces]
    assert "contracts/foo.json" in surface_paths
    assert "scripts/run_something.py" in surface_paths
    # non-governed paths must be excluded
    assert "README.md" not in surface_paths
    assert "docs/architecture/system_registry.md" not in surface_paths


# ---------------------------------------------------------------------------
# build_selection_artifact — fail-closed rules
# ---------------------------------------------------------------------------


def _base_artifact_kwargs(**overrides):
    defaults = dict(
        shard_name="contract",
        mode="ci",
        base_ref="abc123",
        head_ref="def456",
        changed_paths=["contracts/foo.json"],
        governed_surfaces=[
            {"path": "contracts/foo.json", "is_governed": True, "surface": "contract_surface", "reason": "x"}
        ],
        selected_test_files=[],
        fallback_used=False,
        status="selected",
        reason_codes=[],
        trace_refs=[],
    )
    defaults.update(overrides)
    return defaults


def test_governed_surface_empty_selection_blocks():
    artifact = build_selection_artifact(**_base_artifact_kwargs(selected_test_files=[]))
    assert artifact["status"] == "block"
    assert "governed_surface_empty_selection" in artifact["reason_codes"]


def test_governed_surface_empty_selection_allowed_when_caller_declares_empty_allowed():
    # When other shards carry coverage, _determine_status passes status="empty_allowed".
    # build_selection_artifact must respect that and not override to "block".
    artifact = build_selection_artifact(
        **_base_artifact_kwargs(selected_test_files=[], status="empty_allowed")
    )
    assert artifact["status"] == "empty_allowed"


def test_docs_only_non_governed_empty_allowed():
    artifact = build_selection_artifact(
        shard_name="changed_scope",
        mode="ci",
        base_ref="abc",
        head_ref="def",
        changed_paths=["docs/some-guide.md"],
        governed_surfaces=[],
        selected_test_files=[],
        fallback_used=False,
        status="selected",
        reason_codes=[],
        trace_refs=[],
    )
    assert artifact["status"] == "empty_allowed"


def test_normal_selection_produces_selected_status():
    artifact = build_selection_artifact(
        **_base_artifact_kwargs(
            selected_test_files=["tests/test_contracts.py"],
        )
    )
    assert artifact["status"] == "selected"


# ---------------------------------------------------------------------------
# assign_to_shard
# ---------------------------------------------------------------------------


def test_assign_to_shard_contract():
    assert assign_to_shard("tests/test_contracts.py") == "contract"


def test_assign_to_shard_governance():
    assert assign_to_shard("tests/test_system_registry.py") == "governance"


def test_assign_to_shard_dashboard():
    assert assign_to_shard("tests/metrics/test_met_04_something.py") == "dashboard"


def test_assign_to_shard_unknown_returns_none():
    assert assign_to_shard("tests/test_some_random_thing.py") is None


# ---------------------------------------------------------------------------
# compare_parity
# ---------------------------------------------------------------------------


def _make_selection(shard="contract", mode="ci", tests=None):
    return {
        "artifact_type": "pr_test_shard_selection",
        "schema_version": "1.0.0",
        "shard_name": shard,
        "mode": mode,
        "selected_test_files": tests or [],
    }


def test_compare_parity_pass():
    tests = ["tests/test_contracts.py", "tests/test_schema.py"]
    ci = _make_selection(tests=tests)
    precheck = _make_selection(mode="precheck", tests=tests)
    result = compare_parity(ci, precheck)
    assert result["parity_status"] == "pass"
    assert result["reason_codes"] == []


def test_compare_parity_fail_diverge():
    ci = _make_selection(tests=["tests/test_contracts.py"])
    precheck = _make_selection(mode="precheck", tests=["tests/test_schema.py"])
    result = compare_parity(ci, precheck)
    assert result["parity_status"] == "fail"
    assert "ci_precheck_diverge" in result["reason_codes"]


def test_compare_parity_precheck_undercoverage():
    ci = _make_selection(tests=["tests/test_contracts.py", "tests/test_schema.py"])
    precheck = _make_selection(mode="precheck", tests=["tests/test_contracts.py"])
    result = compare_parity(ci, precheck)
    assert result["parity_status"] == "fail"
    assert "precheck_undercoverage" in result["reason_codes"]


# ---------------------------------------------------------------------------
# authority_scope
# ---------------------------------------------------------------------------


def test_selection_artifact_has_authority_scope_observation_only():
    artifact = build_selection_artifact(
        **_base_artifact_kwargs(selected_test_files=["tests/test_contracts.py"])
    )
    assert artifact["authority_scope"] == "observation_only"


def test_parity_artifact_has_authority_scope_observation_only():
    ci = _make_selection(tests=["tests/test_contracts.py"])
    precheck = _make_selection(mode="precheck", tests=["tests/test_contracts.py"])
    result = compare_parity(ci, precheck)
    assert result["authority_scope"] == "observation_only"


# ---------------------------------------------------------------------------
# load_override_map
# ---------------------------------------------------------------------------


def test_load_override_map_merges_disk_overrides(tmp_path):
    # Create the expected directory structure
    gov_dir = tmp_path / "docs" / "governance"
    gov_dir.mkdir(parents=True)
    override_file = gov_dir / "preflight_required_surface_test_overrides.json"
    disk_entry = {
        "scripts/my_new_script.py": ["tests/test_my_new_script.py"],
    }
    override_file.write_text(json.dumps(disk_entry), encoding="utf-8")

    merged = load_override_map(tmp_path)

    # Disk entry must be present
    assert "scripts/my_new_script.py" in merged
    assert "tests/test_my_new_script.py" in merged["scripts/my_new_script.py"]

    # Built-in entries must still be present
    assert "scripts/run_enforced_execution.py" in merged


# ---------------------------------------------------------------------------
# resolve_required_tests
# ---------------------------------------------------------------------------


def test_resolve_required_tests_with_real_repo():
    result = resolve_required_tests(REPO_ROOT, ["scripts/run_contract_preflight.py"])
    tests = result.get("scripts/run_contract_preflight.py", [])
    assert isinstance(tests, list)
    assert len(tests) > 0


# ---------------------------------------------------------------------------
# determinism
# ---------------------------------------------------------------------------


def test_deterministic_same_inputs_same_outputs():
    kwargs = _base_artifact_kwargs(selected_test_files=["tests/test_contracts.py"])
    first = build_selection_artifact(**kwargs)
    second = build_selection_artifact(**kwargs)
    assert first == second
