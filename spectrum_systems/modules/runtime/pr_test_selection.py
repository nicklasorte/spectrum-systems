"""PR test selection — canonical single source of truth for shard-based test selection.

This module exposes deterministic, testable functions with no randomness, no hidden
defaults, and no filesystem side effects except for `load_override_map`, which reads a
single governed override file.

Authority scope: observation_only.  This module produces selection artifacts and parity
artifacts.  It does NOT issue enforcement_signal, readiness_evidence, or promotion_signal.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SHARD_NAMES: tuple[str, ...] = (
    "contract",
    "governance",
    "dashboard",
    "changed_scope",
    "runtime_core",
    "measurement",
)

# Governed path prefixes — paths that trigger fail-closed selection logic.
# Extracted from _GOVERNED_CHANGED_PATH_PREFIXES in scripts/run_contract_preflight.py.
GOVERNED_PATH_PREFIXES: tuple[str, ...] = (
    "contracts/",
    "scripts/",
    "spectrum_systems/",
    ".github/workflows/",
    "docs/governance/",
)

# Non-governed doc path prefixes — used by is_docs_only_non_governed to decide
# whether an empty selection is acceptable or a block.
DOCS_ONLY_PREFIXES: tuple[str, ...] = (
    "docs/",
    "README",
    ".md",
)

# ---------------------------------------------------------------------------
# Shard routing patterns
# ---------------------------------------------------------------------------

# Maps shard name -> list of path patterns (substrings / prefixes) that route a
# test file to that shard.  Order within each list is not significant; all
# patterns are substring matches against the test path.
SHARD_PATH_PATTERNS: dict[str, list[str]] = {
    "contract": [
        "test_contract",
        "test_schema",
        "test_standards",
        "test_contracts",
        "contracts/",
        "tests/test_contract",
        "tests/test_schema",
    ],
    "governance": [
        "test_governance",
        "test_system_registry",
        "test_authority_shape",
        "test_preflight",
        "test_pytest_selection",
        "test_workflow",
        "test_artifact_boundary_workflow",
        "docs/governance/",
        "docs/architecture/",
        "tests/test_governance",
        "tests/test_system_registry",
    ],
    "dashboard": [
        "test_met_04",
        "test_dashboard",
        "test_validate_dashboard",
        "apps/dashboard-3ls/",
        "artifacts/dashboard_",
        "tests/metrics/",
        "tests/test_validate_dashboard",
    ],
    "runtime_core": [
        "test_aex",
        "test_pqx",
        "test_evl",
        "test_tpa",
        "test_cde",
        "test_sel",
        "test_tlc",
    ],
    "measurement": [
        "test_sma",
        "test_met",
        "test_tls",
        "test_dashboard_metrics",
    ],
    # "changed_scope" is the catch-all; it has no patterns of its own.
    "changed_scope": [],
}

# ---------------------------------------------------------------------------
# Fallback smoke tests (from DEFAULT_REQUIRED_SMOKE_TESTS in preflight script)
# ---------------------------------------------------------------------------

_DEFAULT_REQUIRED_SMOKE_TESTS: list[str] = [
    "tests/test_roadmap_eligibility.py",
    "tests/test_next_step_decision.py",
    "tests/test_next_step_decision_policy.py",
    "tests/test_cycle_runner.py",
]

# ---------------------------------------------------------------------------
# Built-in surface override map (from _REQUIRED_SURFACE_TEST_OVERRIDES in
# scripts/run_contract_preflight.py).
# ---------------------------------------------------------------------------

_CONTROL_SURFACE_GAP_PACKET_REQUIRED_TESTS: list[str] = [
    "tests/test_control_surface_gap_to_pqx.py",
    "tests/test_pqx_slice_runner.py",
]

_REQUIRED_SURFACE_TEST_OVERRIDES: dict[str, list[str]] = {
    "scripts/run_autonomous_validation_run.py": [
        "tests/test_run_autonomous_validation_run.py",
    ],
    "scripts/run_ops03_adversarial_stress_testing.py": [
        "tests/test_run_ops03_adversarial_stress_testing.py",
    ],
    "scripts/run_trust_spine_evidence_cohesion.py": [
        "tests/test_trust_spine_evidence_cohesion.py",
    ],
    "scripts/run_enforced_execution.py": [
        "tests/test_execution_contracts.py",
        "tests/test_control_executor.py",
    ],
    "spectrum_systems/modules/runtime/control_surface_gap_loader.py": _CONTROL_SURFACE_GAP_PACKET_REQUIRED_TESTS,
    "spectrum_systems/modules/runtime/control_surface_gap_to_pqx.py": _CONTROL_SURFACE_GAP_PACKET_REQUIRED_TESTS,
    "spectrum_systems/modules/runtime/pqx_slice_runner.py": _CONTROL_SURFACE_GAP_PACKET_REQUIRED_TESTS,
    "scripts/pqx_runner.py": _CONTROL_SURFACE_GAP_PACKET_REQUIRED_TESTS,
    ".github/workflows/artifact-boundary.yml": [
        "tests/test_artifact_boundary_workflow_pytest_policy_observation.py",
        "tests/test_artifact_boundary_workflow_policy_observation.py",
    ],
}

# ---------------------------------------------------------------------------
# Forced-evaluation surfaces (from _is_forced_evaluation_surface in preflight).
# Used to build surface/reason metadata in classify_changed_path.
# ---------------------------------------------------------------------------

_CONTROL_SURFACE_GAP_PACKET_GOVERNANCE_PATHS: frozenset[str] = frozenset(
    {
        "spectrum_systems/modules/runtime/control_surface_gap_loader.py",
        "spectrum_systems/modules/runtime/control_surface_gap_to_pqx.py",
        "spectrum_systems/modules/runtime/pqx_slice_runner.py",
        "scripts/pqx_runner.py",
    }
)

# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def is_governed_path(path: str) -> bool:
    """Return True if *path* belongs to a governed surface.

    Extracted from ``_is_governed_changed_path`` in
    ``scripts/run_contract_preflight.py``.
    """
    return any(path.startswith(prefix) for prefix in GOVERNED_PATH_PREFIXES)


def classify_changed_path(path: str) -> dict[str, Any]:
    """Return a classification dict for a single changed path.

    The dict has keys:
      - ``is_governed`` (bool)
      - ``surface`` (str)
      - ``reason`` (str)

    Logic is adapted from ``_is_forced_evaluation_surface`` in
    ``scripts/run_contract_preflight.py``.
    """
    # Control-surface gap packet governance seam
    if path in _CONTROL_SURFACE_GAP_PACKET_GOVERNANCE_PATHS:
        return {
            "is_governed": True,
            "surface": "control_surface_gap_packet_governance",
            "reason": "control-surface gap packet governance seam changed",
        }

    # Root governance instruction docs
    if path in {"AGENTS.md", "CLAUDE.md"}:
        return {
            "is_governed": True,
            "surface": "governance_instruction_doc",
            "reason": "root governance instruction doc changed (subject to system registry guard)",
        }

    # Preflight selection policy / override surfaces
    if path in {
        "docs/governance/pytest_pr_selection_integrity_policy.json",
        "docs/governance/preflight_required_surface_test_overrides.json",
    }:
        return {
            "is_governed": True,
            "surface": "preflight_selection_policy",
            "reason": "preflight selection policy/override surface changed",
        }

    # Runtime module
    if path.startswith("spectrum_systems/modules/runtime/"):
        return {
            "is_governed": True,
            "surface": "runtime_module",
            "reason": "runtime module changed",
        }

    # Orchestration
    if path.startswith("spectrum_systems/orchestration/"):
        return {
            "is_governed": True,
            "surface": "orchestration",
            "reason": "orchestration path changed",
        }

    # Governance / scripts / contracts/governance
    if (
        path.startswith("spectrum_systems/governance/")
        or path.startswith("scripts/")
        or path.startswith("contracts/governance/")
    ):
        return {
            "is_governed": True,
            "surface": "governance",
            "reason": "governance/control surface changed",
        }

    # CI workflow surface
    if path.startswith(".github/workflows/") and path.endswith(".yml"):
        return {
            "is_governed": True,
            "surface": "ci_workflow_surface",
            "reason": "CI workflow surface changed",
        }

    # Contract / schema paths (governed by GOVERNED_PATH_PREFIXES via contracts/)
    if path.startswith("contracts/"):
        return {
            "is_governed": True,
            "surface": "contract_surface",
            "reason": "contract/schema path changed",
        }

    # Contract-tied tests
    if path.startswith("tests/") and path.endswith(".py"):
        tied_markers = (
            "contract",
            "preflight",
            "schema",
            "roadmap_eligibility",
            "next_step_decision",
            "cycle_runner",
            "workflow",
        )
        if any(marker in path for marker in tied_markers):
            return {
                "is_governed": True,
                "surface": "contract_tied_tests",
                "reason": "contract-tied test changed",
            }

    # MET-04-18 dashboard artifact surfaces
    if path.startswith("artifacts/dashboard_metrics/") or path.startswith("artifacts/dashboard_cases/"):
        return {
            "is_governed": True,
            "surface": "met_04_18_dashboard_artifact",
            "reason": "MET-04-18 dashboard artifact changed",
        }

    # MET-04-18 dashboard app surfaces
    if path.startswith("apps/dashboard-3ls/app/api/intelligence/") or path == "apps/dashboard-3ls/app/page.tsx":
        return {
            "is_governed": True,
            "surface": "met_04_18_dashboard_surface",
            "reason": "MET-04-18 dashboard surface changed",
        }

    # MET-* review docs
    if path.startswith("docs/reviews/MET-") and path.endswith(".md"):
        return {
            "is_governed": True,
            "surface": "met_review_surface",
            "reason": "MET-* review doc changed",
        }

    # AGENT-INSTR-* review docs
    if path.startswith("docs/reviews/AGENT-INSTR-") and path.endswith(".md"):
        return {
            "is_governed": True,
            "surface": "agent_instr_review_surface",
            "reason": "AGENT-INSTR-* review doc changed",
        }

    # Docs/governance/ prefix (from GOVERNED_PATH_PREFIXES)
    if path.startswith("docs/governance/"):
        return {
            "is_governed": True,
            "surface": "governance_docs",
            "reason": "governance doc path changed",
        }

    return {
        "is_governed": False,
        "surface": "other",
        "reason": "path does not map to governed contract surface",
    }


def resolve_governed_surfaces(changed_paths: list[str]) -> list[dict[str, Any]]:
    """Return a list of classification dicts for all governed changed paths.

    Each dict has the same shape as the return of ``classify_changed_path``
    plus an additional ``path`` key.
    """
    results: list[dict[str, Any]] = []
    for path in sorted(set(changed_paths)):
        classification = classify_changed_path(path)
        if classification["is_governed"]:
            results.append({"path": path, **classification})
    return results


def load_override_map(repo_root: Path) -> dict[str, list[str]]:
    """Return the merged required-surface test override map.

    Starts from the built-in ``_REQUIRED_SURFACE_TEST_OVERRIDES`` and merges
    any entries from the on-disk override file at
    ``docs/governance/preflight_required_surface_test_overrides.json``.

    This is the only function in this module that performs filesystem I/O.
    Adapted from ``_load_required_surface_override_map`` in
    ``scripts/run_contract_preflight.py``.
    """
    merged: dict[str, list[str]] = {
        path: list(targets) for path, targets in _REQUIRED_SURFACE_TEST_OVERRIDES.items()
    }
    override_path = repo_root / "docs" / "governance" / "preflight_required_surface_test_overrides.json"
    if not override_path.is_file():
        return merged
    try:
        payload = json.loads(override_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return merged
    if not isinstance(payload, dict):
        return merged
    for path, targets in payload.items():
        if not isinstance(path, str) or not isinstance(targets, list):
            continue
        normalized_targets = [str(item) for item in targets if isinstance(item, str) and item.strip()]
        merged[path] = sorted(set(normalized_targets))
    return merged


def resolve_required_tests(repo_root: Path, changed_paths: list[str]) -> dict[str, list[str]]:
    """Return a mapping of changed path -> list of required test file paths.

    For each changed path the function:
    1. Checks the override map for explicit test bindings.
    2. Includes the path itself if it is a test file (``tests/test_*.py``).
    3. Scans all test files under ``tests/`` for name-based needle matches.

    Adapted from ``resolve_required_surface_tests`` in
    ``scripts/run_contract_preflight.py``.
    """
    tests_root = repo_root / "tests"
    test_files: list[Path] = (
        sorted(p for p in tests_root.rglob("test_*.py") if p.is_file())
        if tests_root.is_dir()
        else []
    )
    override_map = load_override_map(repo_root)
    path_to_targets: dict[str, list[str]] = {}

    for rel_path in changed_paths:
        targets: set[str] = set()

        # Apply explicit overrides first.
        for override in override_map.get(rel_path, []):
            targets.add(override)

        candidate = Path(rel_path)

        if rel_path.startswith("tests/test_") and rel_path.endswith(".py"):
            # The changed path is itself a test file.
            targets.add(rel_path)
        else:
            needles = {candidate.stem.lower(), candidate.name.lower()}
            needles = {n for n in needles if n and n not in {"test", "tests"}}
            for test_file in test_files:
                rel_test = test_file.relative_to(repo_root).as_posix()
                try:
                    text = test_file.read_text(encoding="utf-8").lower()
                except (OSError, UnicodeDecodeError):
                    continue
                if any(needle in text for needle in needles):
                    targets.add(rel_test)

        path_to_targets[rel_path] = sorted(targets)

    return path_to_targets


def assign_to_shard(test_path: str) -> str | None:
    """Return the shard name that should own *test_path*, or ``None``.

    Shards are checked in declaration order (contract → governance → dashboard
    → runtime_core → measurement).  ``changed_scope`` is the catch-all and is
    returned only when explicitly requested via the build_selection_artifact
    flow; this function does not return it — callers must handle the fallback
    themselves.

    Returns the first matching shard name, or ``None`` if no pattern matches.
    """
    for shard_name in SHARD_NAMES:
        if shard_name == "changed_scope":
            # Skip the catch-all; callers own the fallback logic.
            continue
        patterns = SHARD_PATH_PATTERNS.get(shard_name, [])
        for pattern in patterns:
            if pattern in test_path:
                return shard_name
    return None


def is_docs_only_non_governed(changed_paths: list[str]) -> bool:
    """Return True if every changed path is a non-governed documentation path.

    Used to decide whether an empty test selection is ``empty_allowed`` (True)
    or ``block`` (False).
    """
    if not changed_paths:
        return False
    for path in changed_paths:
        # If any path is governed, this is not docs-only.
        if is_governed_path(path):
            return False
        # Must match at least one docs-only prefix/suffix.
        if not any(
            path.startswith(prefix) or path.endswith(prefix)
            for prefix in DOCS_ONLY_PREFIXES
        ):
            return False
    return True


def build_selection_artifact(
    *,
    shard_name: str,
    mode: str,
    base_ref: str,
    head_ref: str,
    changed_paths: list[str],
    governed_surfaces: list[dict[str, Any]],
    selected_test_files: list[str],
    fallback_used: bool,
    status: str,
    reason_codes: list[str],
    trace_refs: list[str],
) -> dict[str, Any]:
    """Build and return a ``pr_test_shard_selection`` artifact dict.

    Fail-closed rules applied (in order, earlier rules win):
    - governed surface changed + no selected tests
        → status "block", reason_code "governed_surface_empty_selection"
    - governed surface present but mapping is unknown
        → status "block", reason_code "unknown_governed_surface_mapping"
    - docs-only non-governed paths + no selected tests
        → status "empty_allowed"
    - otherwise: status "selected" (or caller-supplied status when tests present)

    ``authority_scope`` is always ``"observation_only"``.
    """
    # Derive coverage ratio
    total_governed = len(governed_surfaces)
    coverage_ratio: float = 0.0
    if total_governed > 0 and selected_test_files:
        coverage_ratio = min(1.0, len(selected_test_files) / total_governed)

    # Fail-closed evaluation
    effective_status = status
    effective_reason_codes: list[str] = list(reason_codes)

    has_governed = len(governed_surfaces) > 0
    has_tests = len(selected_test_files) > 0

    if has_governed and not has_tests:
        if status == "empty_allowed":
            # Caller has determined this shard has no obligation for the governed
            # surfaces (e.g., required tests belong to other shards).
            effective_status = "empty_allowed"
        else:
            # Check for unknown mapping vs. simply no tests found.
            surfaces_set = {s.get("surface", "") for s in governed_surfaces}
            if "other" in surfaces_set or "" in surfaces_set:
                effective_status = "block"
                if "unknown_governed_surface_mapping" not in effective_reason_codes:
                    effective_reason_codes.append("unknown_governed_surface_mapping")
            else:
                effective_status = "block"
                if "governed_surface_empty_selection" not in effective_reason_codes:
                    effective_reason_codes.append("governed_surface_empty_selection")
    elif not has_governed and not has_tests:
        # No governed surfaces and no selected tests.
        if not changed_paths:
            # Nothing changed at all — empty selection is acceptable.
            effective_status = "empty_allowed"
        elif is_docs_only_non_governed(changed_paths):
            effective_status = "empty_allowed"
        else:
            effective_status = "block"
            if "governed_surface_empty_selection" not in effective_reason_codes:
                effective_reason_codes.append("governed_surface_empty_selection")
    elif has_tests:
        if effective_status not in ("block", "empty_allowed", "selected"):
            effective_status = "selected"

    return {
        "artifact_type": "pr_test_shard_selection",
        "schema_version": "1.0.0",
        "mode": mode,
        "shard_name": shard_name,
        "base_ref": base_ref,
        "head_ref": head_ref,
        "changed_paths": sorted(set(changed_paths)),
        "governed_surfaces": governed_surfaces,
        "selected_test_files": sorted(set(selected_test_files)),
        "coverage_ratio": coverage_ratio,
        "fallback_used": fallback_used,
        "status": effective_status,
        "reason_codes": sorted(set(effective_reason_codes)),
        "trace_refs": trace_refs,
        "authority_scope": "observation_only",
    }


def compare_parity(
    ci_selection: dict[str, Any],
    precheck_selection: dict[str, Any],
) -> dict[str, Any]:
    """Compare a CI selection artifact against a precheck selection artifact.

    Returns a ``precheck_selection_parity`` artifact dict.

    Parity rules:
    - ci_tests != precheck_tests  → parity_status "fail", reason "ci_precheck_diverge"
    - precheck has fewer tests    → parity_status "fail", reason "precheck_undercoverage"
    - CI has fewer tests          → parity_status "fail", reason "ci_drift_detected"
    - otherwise                   → parity_status "pass"
    """
    ci_tests: list[str] = sorted(set(ci_selection.get("selected_test_files", [])))
    precheck_tests: list[str] = sorted(set(precheck_selection.get("selected_test_files", [])))

    ci_set = set(ci_tests)
    precheck_set = set(precheck_tests)

    mismatched_tests: list[str] = sorted(ci_set.symmetric_difference(precheck_set))
    mismatched_shards: list[str] = []

    ci_shard = ci_selection.get("shard_name", "")
    precheck_shard = precheck_selection.get("shard_name", "")
    if ci_shard != precheck_shard:
        mismatched_shards = sorted({ci_shard, precheck_shard} - {""})

    reason_codes: list[str] = []
    parity_status = "pass"

    if ci_set != precheck_set:
        parity_status = "fail"
        reason_codes.append("ci_precheck_diverge")
        if len(precheck_tests) < len(ci_tests):
            reason_codes.append("precheck_undercoverage")
        if len(ci_tests) < len(precheck_tests):
            reason_codes.append("ci_drift_detected")

    ci_ref = ci_selection.get("shard_name", "") + "/" + ci_selection.get("mode", "")
    precheck_ref = precheck_selection.get("shard_name", "") + "/" + precheck_selection.get("mode", "")

    return {
        "artifact_type": "precheck_selection_parity",
        "schema_version": "1.0.0",
        "ci_selection_ref": ci_ref,
        "precheck_selection_ref": precheck_ref,
        "parity_status": parity_status,
        "mismatched_shards": mismatched_shards,
        "mismatched_tests": mismatched_tests,
        "reason_codes": reason_codes,
        "authority_scope": "observation_only",
    }
