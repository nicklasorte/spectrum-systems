"""Test: System registry guard runs clean against 3LS simplification files (Phase hardening).

This test catches DIRECT_OWNERSHIP_OVERLAP, PROTECTED_AUTHORITY_VIOLATION, and
SHADOW_OWNERSHIP_OVERLAP in changed files *before* they reach CI.

It replicates what `scripts/run_system_registry_guard.py` does in CI, so the
same guard fires locally during `python -m pytest`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, List

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]

# Files introduced by the 3LS simplification that the registry guard must accept.
SIMPLIFICATION_FILES = [
    "docs/rca_guide.md",
    "docs/migration_guide.md",
    "docs/runbooks/system_debug_guide.md",
    "docs/system_justifications/TPA.md",
    "docs/system_justifications/TLC.md",
    "docs/system_justifications/PRG.md",
    "docs/system_justifications/WPG.md",
    "docs/system_justifications/CHK.md",
    "docs/system_justifications/GOV.md",
    "config/policy/consolidated_systems_policy.json",
    "spectrum_systems/compat/__init__.py",
    "spectrum_systems/compat/deprecation_layer.py",
    "spectrum_systems/debugging/structured_failures.py",
    "spectrum_systems/eval_system/__init__.py",
    "spectrum_systems/eval_system/eval_system.py",
    "spectrum_systems/exec_system/__init__.py",
    "spectrum_systems/exec_system/exec_system.py",
    "spectrum_systems/govern/__init__.py",
    "spectrum_systems/govern/govern.py",
    "spectrum_systems/governance/gate_categories.py",
    "spectrum_systems/governance/gate_runner.py",
    "spectrum_systems/governance/system_dependency_map.py",
    "spectrum_systems/governance/system_justification.py",
    "spectrum_systems/observability/event_filter.py",
    "spectrum_systems/observability/loop_metrics.py",
    "tests/test_3ls_simplification.py",
    "tests/test_3ls_registry_guard.py",
]


def _guard_available() -> bool:
    """Return True if the registry guard and its dependencies are importable."""
    try:
        from spectrum_systems.modules.governance.system_registry_guard import (  # noqa: F401
            evaluate_system_registry_guard,
            load_guard_policy,
            parse_system_registry,
        )
        return True
    except ImportError:
        return False


def _policy_and_registry_exist() -> bool:
    policy = REPO_ROOT / "contracts" / "governance" / "system_registry_guard_policy.json"
    registry = REPO_ROOT / "docs" / "architecture" / "system_registry.md"
    return policy.is_file() and registry.is_file()


def _run_guard_on_files(file_list: List[str]) -> Dict[str, Any]:
    """Run the registry guard against an explicit list of files."""
    from spectrum_systems.modules.governance.system_registry_guard import (
        evaluate_system_registry_guard,
        load_guard_policy,
        parse_system_registry,
    )

    policy_path = REPO_ROOT / "contracts" / "governance" / "system_registry_guard_policy.json"
    registry_path = REPO_ROOT / "docs" / "architecture" / "system_registry.md"

    policy = load_guard_policy(policy_path)
    registry = parse_system_registry(registry_path)

    # Only include files that actually exist in the repo
    existing = [f for f in file_list if (REPO_ROOT / f).is_file()]

    return evaluate_system_registry_guard(
        repo_root=REPO_ROOT,
        changed_files=existing,
        policy=policy,
        registry_model=registry,
    )


@pytest.mark.skipif(
    not _guard_available() or not _policy_and_registry_exist(),
    reason="Registry guard or policy/registry files not available",
)
class TestRegistryGuard3LSFiles:
    """Registry guard must pass on all 3LS simplification files."""

    def test_no_ownership_violations_in_simplification_files(self):
        """All 3LS simplification files must pass the registry guard."""
        result = _run_guard_on_files(SIMPLIFICATION_FILES)

        diagnostics = result.get("diagnostics") or []
        if diagnostics:
            # Format violations for a readable failure message
            lines = ["Registry guard violations found in 3LS simplification files:", ""]
            for d in diagnostics:
                lines.append(
                    f"  {d.get('reason_code')} | "
                    f"{d.get('file')}:{d.get('line')} | "
                    f"symbol={d.get('symbol')} | "
                    f"canonical_owner={d.get('canonical_owner')} | "
                    f"fix: {d.get('resolution_category')}"
                )
            lines.append("")
            lines.append(
                "Hint: Remove ownership-claim words (authority, controls, governs, "
                "emits, override, owns) near system acronyms that are not the "
                "canonical owner. See docs/architecture/system_registry.md."
            )
            pytest.fail("\n".join(lines))

        assert result["status"] == "pass", (
            f"Registry guard returned status={result['status']!r} with no diagnostics"
        )

    def test_no_violations_in_rca_guide(self):
        """rca_guide.md must not claim ownership for non-owned systems."""
        result = _run_guard_on_files(["docs/rca_guide.md"])
        diags = [d for d in (result.get("diagnostics") or []) if d.get("file") == "docs/rca_guide.md"]
        assert diags == [], _format_diags(diags)

    def test_no_violations_in_runbook(self):
        """system_debug_guide.md must not claim ownership for non-owned systems."""
        result = _run_guard_on_files(["docs/runbooks/system_debug_guide.md"])
        diags = [
            d for d in (result.get("diagnostics") or [])
            if d.get("file") == "docs/runbooks/system_debug_guide.md"
        ]
        assert diags == [], _format_diags(diags)

    def test_no_violations_in_system_justification_docs(self):
        """System justification docs must not claim ownership for non-owned systems."""
        files = [
            "docs/system_justifications/TPA.md",
            "docs/system_justifications/TLC.md",
            "docs/system_justifications/PRG.md",
            "docs/system_justifications/WPG.md",
            "docs/system_justifications/CHK.md",
            "docs/system_justifications/GOV.md",
        ]
        result = _run_guard_on_files(files)
        diags = result.get("diagnostics") or []
        assert diags == [], _format_diags(diags)

    def test_no_violations_in_python_modules(self):
        """Python modules added by 3LS simplification must not violate registry ownership."""
        files = [
            "spectrum_systems/govern/__init__.py",
            "spectrum_systems/governance/gate_categories.py",
            "spectrum_systems/governance/system_justification.py",
        ]
        result = _run_guard_on_files(files)
        diags = result.get("diagnostics") or []
        assert diags == [], _format_diags(diags)

    def test_gate_s_importable(self):
        """GATE-S must be registered in gate_runner.GATE_CHECKS."""
        from spectrum_systems.governance.gate_runner import GATE_CHECKS
        assert "GATE-S" in GATE_CHECKS, "GATE-S missing from gate_runner.GATE_CHECKS"
        name, fn = GATE_CHECKS["GATE-S"]
        assert name == "System Registry"
        assert callable(fn)


def _format_diags(diags: List[Dict[str, Any]]) -> str:
    if not diags:
        return ""
    lines = ["Ownership violations:"]
    for d in diags:
        lines.append(
            f"  {d.get('reason_code')} {d.get('file')}:{d.get('line')} "
            f"symbol={d.get('symbol')} canonical_owner={d.get('canonical_owner')}"
        )
    lines.append(
        "\nFix: remove ownership-claim words (authority, controls, governs, "
        "emits, override, owns) near system acronyms that are not the canonical owner."
    )
    return "\n".join(lines)
