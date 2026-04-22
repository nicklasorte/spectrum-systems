"""SRG ownership guard tests for Phase 2 files.

These tests run the system registry guard in-process against the Phase 2
changed files to catch SHADOW_OWNERSHIP_OVERLAP and related violations
during `pytest`, before any push or CI run.

Adding SRG validation to the test suite means ownership violations surface
in the local test loop (the fastest feedback cycle) rather than in CI.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.governance.system_registry_guard import (
    evaluate_system_registry_guard,
    load_guard_policy,
    parse_system_registry,
)

_POLICY_PATH = REPO_ROOT / "contracts" / "governance" / "system_registry_guard_policy.json"
_REGISTRY_PATH = REPO_ROOT / "docs" / "architecture" / "system_registry.md"

# Phase 2 files that must be clean
PHASE_2_FILES: List[str] = [
    "contracts/schemas/execution_event.schema.json",
    "contracts/schemas/failure_artifact.schema.json",
    "contracts/schemas/system_freeze_record.schema.json",
    "contracts/schemas/system_supersession_record.schema.json",
    "docs/phase-2/PHASE_2_ESCALATION_PROTOCOL.md",
    "docs/phase-2/PHASE_2_METRICS.json",
    "docs/phase-2/PHASE_2_ROLLBACK_STRATEGY.md",
    "spectrum_systems/evaluation/__init__.py",
    "spectrum_systems/evaluation/eval_gate.py",
    "spectrum_systems/execution/admission_gate.py",
    "spectrum_systems/execution/fail_closed_enforcer.py",
    "spectrum_systems/governance/system_justification.py",
    "spectrum_systems/governance/system_lifecycle.py",
    "spectrum_systems/observability/execution_event_log.py",
    "spectrum_systems/promotion/__init__.py",
    "spectrum_systems/promotion/promotion_gate.py",
    "tests/test_control_loop_gates.py",
    "tests/test_execution_event_log.py",
    "tests/test_fail_closed_enforcer.py",
    "tests/test_system_justification.py",
    "tests/test_system_lifecycle.py",
]


@pytest.fixture(scope="module")
def srg_policy():
    return load_guard_policy(_POLICY_PATH)


@pytest.fixture(scope="module")
def srg_registry():
    return parse_system_registry(_REGISTRY_PATH)


def _run_srg(files: List[str], policy: Dict[str, Any], registry: Any) -> Dict[str, Any]:
    existing = [f for f in files if (REPO_ROOT / f).is_file()]
    return evaluate_system_registry_guard(
        repo_root=REPO_ROOT,
        changed_files=existing,
        policy=policy,
        registry_model=registry,
    )


# ---------------------------------------------------------------------------
# Test 1: All Phase 2 files pass SRG (the guard we actually care about)
# ---------------------------------------------------------------------------


def test_phase2_files_pass_srg(srg_policy, srg_registry):
    result = _run_srg(PHASE_2_FILES, srg_policy, srg_registry)
    diagnostics = result.get("diagnostics") or []
    assert result["status"] == "pass", (
        f"SRG failed on Phase 2 files.\n"
        f"reason_codes: {result['normalized_reason_codes']}\n"
        f"diagnostics:\n"
        + "\n".join(
            f"  {d['file']}:{d['line']} [{d['reason_code']}] "
            f"symbol={d.get('symbol')} cluster={d.get('cluster')} "
            f"canonical_owner={d.get('canonical_owner')}"
            for d in diagnostics
        )
    )


# ---------------------------------------------------------------------------
# Test 2: Guard detects SHADOW_OWNERSHIP_OVERLAP in a synthetic bad file
# ---------------------------------------------------------------------------


def test_srg_detects_shadow_ownership_overlap(srg_policy, srg_registry, tmp_path):
    """The guard must detect the 'authority' + 3-letter + cluster pattern."""
    bad_doc = tmp_path / "bad_doc.md"
    # 'authority' on a line with 'WPG' and 'execution' → SHADOW with PQX
    bad_doc.write_text(
        "# Bad doc\n\nWPG is the execution authority for all governed work.\n",
        encoding="utf-8",
    )
    result = evaluate_system_registry_guard(
        repo_root=tmp_path,
        changed_files=["bad_doc.md"],
        policy=srg_policy,
        registry_model=srg_registry,
    )
    assert result["status"] == "fail", "SRG should have detected SHADOW_OWNERSHIP_OVERLAP"
    codes = result["normalized_reason_codes"]
    assert "SHADOW_OWNERSHIP_OVERLAP" in codes, f"Expected SHADOW_OWNERSHIP_OVERLAP, got: {codes}"


# ---------------------------------------------------------------------------
# Test 3: Guard passes a clean file with a 3-letter acronym but no claim words
# ---------------------------------------------------------------------------


def test_srg_passes_clean_file_with_acronym(srg_policy, srg_registry, tmp_path):
    good_doc = tmp_path / "good_doc.md"
    good_doc.write_text(
        "# Good doc\n\nAll escalations route to CDE for sign-off.\n",
        encoding="utf-8",
    )
    result = evaluate_system_registry_guard(
        repo_root=tmp_path,
        changed_files=["good_doc.md"],
        policy=srg_policy,
        registry_model=srg_registry,
    )
    assert result["status"] == "pass", (
        f"SRG unexpectedly failed on clean file: {result['normalized_reason_codes']}"
    )


# ---------------------------------------------------------------------------
# Test 4: Guard detects the exact pattern that triggered the Phase 2 CI failure
# ---------------------------------------------------------------------------


def test_srg_detects_original_phase2_violation(srg_policy, srg_registry, tmp_path):
    """Regression guard: the original failing line must be detected."""
    offending = tmp_path / "escalation.md"
    offending.write_text(
        "## Escalation Contact\n\n"
        "All escalations route to CDE (Canonical Decision Engine). "
        "CDE is the sole decision authority.\n",
        encoding="utf-8",
    )
    result = evaluate_system_registry_guard(
        repo_root=tmp_path,
        changed_files=["escalation.md"],
        policy=srg_policy,
        registry_model=srg_registry,
    )
    assert result["status"] == "fail", (
        "Regression: the original Phase 2 CI violation was not detected by in-process SRG"
    )
    assert "SHADOW_OWNERSHIP_OVERLAP" in result["normalized_reason_codes"]
