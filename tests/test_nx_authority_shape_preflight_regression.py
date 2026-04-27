"""AUTH-SHAPE-FIX-1232: regression test locking in the cleaned vocabulary.

Runs the canonical authority-shape preflight scanner against the surfaces
introduced or modified by NX-ALL-01 plus the governance reports that were
the trigger for PR #1232's failure. Fails closed if any of those surfaces
reintroduce protected vocabulary in non-owner form.

This test is the eval-time guard so the failure cannot reach CI undetected.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_preflight_module():
    spec = importlib.util.spec_from_file_location(
        "_authority_shape_preflight_core",
        REPO_ROOT / "spectrum_systems" / "governance" / "authority_shape_preflight.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PREFLIGHT = _load_preflight_module()
VOCAB_PATH = REPO_ROOT / "contracts" / "governance" / "authority_shape_vocabulary.json"


# Surfaces introduced or modified by NX-ALL-01 / AUTH-SHAPE-FIX-1232.
# Each must clear the authority-shape preflight (either via cleaned vocabulary
# or via narrow observational guard-path entry with declared metadata).
NX_SURFACES = [
    # Support seams (canonical-field consumers)
    "spectrum_systems/modules/runtime/eval_spine.py",
    "spectrum_systems/modules/runtime/control_chain_invariants.py",
    "spectrum_systems/modules/runtime/context_admission_gate.py",
    "spectrum_systems/modules/runtime/slo_budget_gate.py",
    "spectrum_systems/modules/replay/replay_support.py",
    "spectrum_systems/modules/lineage/lineage_enforcement.py",
    "spectrum_systems/modules/observability/failure_trace.py",
    "spectrum_systems/modules/governance/certification_prerequisites.py",
    # Static registry validator
    "scripts/validate_system_registry.py",
    # Delivery report
    "docs/reviews/NX_ALL_01_delivery_report.md",
    # Generated governance reports (timestamps churn frequently)
    "docs/governance-reports/contract-compliance-report.md",
    "docs/governance-reports/ecosystem-health-report.md",
    # Generator scripts must also remain free of protected vocabulary
    "scripts/generate_ecosystem_health_report.py",
    "scripts/run_contract_enforcement.py",
]


def _run_preflight(changed_files):
    vocab = PREFLIGHT.load_vocabulary(VOCAB_PATH)
    return PREFLIGHT.evaluate_preflight(
        repo_root=REPO_ROOT,
        changed_files=changed_files,
        vocab=vocab,
        mode="suggest-only",
    )


def test_nx_surfaces_pass_authority_shape_preflight() -> None:
    """All NX-touched surfaces must pass the authority-shape preflight."""
    result = _run_preflight(NX_SURFACES)
    assert result.status == "pass", (
        f"authority-shape preflight failed for NX surfaces: "
        f"{[v.to_dict() for v in result.violations[:5]]}"
    )
    assert len(result.violations) == 0


@pytest.mark.parametrize("surface", NX_SURFACES)
def test_each_nx_surface_individually_passes(surface: str) -> None:
    """Each individual NX surface must pass on its own — locks per-file
    expectations in case a future change reintroduces protected vocabulary
    in only one file."""
    result = _run_preflight([surface])
    assert result.status == "pass", (
        f"surface {surface!r} reintroduced authority-shape violations: "
        f"{[v.to_dict() for v in result.violations[:3]]}"
    )


def test_observational_path_entries_carry_required_metadata() -> None:
    """Every narrow observational path entry must carry the required
    authority_scope / may_authorize / canonical_owner / rationale fields."""
    import json

    registry_path = REPO_ROOT / "contracts" / "governance" / "authority_registry.json"
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    entries = payload.get("observational_path_entries")
    assert isinstance(entries, list) and entries, "observational_path_entries must be a non-empty list"
    for entry in entries:
        assert isinstance(entry, dict)
        assert entry.get("path"), "entry missing path"
        assert entry.get("authority_scope") == "observational", entry
        assert entry.get("may_authorize") is False, entry
        assert entry.get("canonical_owner") is None, entry
        rationale = entry.get("rationale")
        assert isinstance(rationale, str) and rationale.strip(), entry


def test_report_scripts_do_not_emit_protected_authority_vocabulary() -> None:
    """AUTH-SHAPE-FIX-1232B: the two non-owner reporting scripts must not
    contain protected authority-shaped tokens (decision, enforcement,
    promotion, certification, etc.) anywhere in their source — including
    function names, dictionary keys, JSON output keys, CI prefixes, and
    docstring/comment text.

    They are observational reporting surfaces and are not SEL/ENF/CDE/JDX
    authority owners.
    """
    import re

    forbidden_tokens = {
        "enforcement",
        "ci_enforcement",
        "score_ci_enforcement",
        "format_enforcement_line",
        "run_enforcement",
    }
    pattern = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
    for rel in (
        "scripts/generate_ecosystem_health_report.py",
        "scripts/run_contract_enforcement.py",
    ):
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        offenders = []
        for match in pattern.finditer(text):
            ident = match.group(0)
            if ident in forbidden_tokens:
                offenders.append(ident)
            elif ident.lower() == "enforcement":
                offenders.append(ident)
        assert not offenders, (
            f"{rel} reintroduced protected authority-shaped vocabulary: "
            f"{sorted(set(offenders))}"
        )


def test_contract_compliance_report_uses_safe_headings() -> None:
    """The generated contract compliance report must use 'Compliance' or
    'Validation' headings, not 'Enforcement', so the report itself stays
    consistent with the AUTH-SHAPE-FIX-1232B vocabulary cleanup."""
    report_path = REPO_ROOT / "docs" / "governance-reports" / "contract-compliance-report.md"
    if not report_path.is_file():
        # Generated artifact may not be present in a clean checkout; the
        # generator script test (test_contract_enforcement) covers the
        # generation path. Nothing to assert here when the artifact is absent.
        return
    text = report_path.read_text(encoding="utf-8")
    assert "Contract Compliance" in text or "Contract Validation" in text, (
        "contract report does not use Compliance/Validation heading"
    )
    # The phrase 'Contract Enforcement' must not appear except as a legacy
    # filename reference (which would not include a space).
    assert "Contract Enforcement" not in text, (
        "contract report still contains 'Contract Enforcement' heading"
    )


def test_ecosystem_health_report_uses_safe_keys() -> None:
    """The machine-readable ecosystem health report must use the renamed
    ci_compliance_signal key, not ci_enforcement."""
    import json

    report_path = REPO_ROOT / "governance" / "reports" / "ecosystem-health.json"
    if not report_path.is_file():
        return
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    summary = payload.get("summary") or {}
    assert "ci_compliance_signal" in summary, (
        "ecosystem-health.json summary missing renamed ci_compliance_signal key"
    )
    assert "ci_enforcement" not in summary, (
        "ecosystem-health.json summary still emits legacy ci_enforcement key"
    )
    for repo in payload.get("repos", []):
        cats = (repo.get("maturity_score") or {}).get("categories") or {}
        assert "ci_compliance_signal" in cats, repo.get("repo_name")
        assert "ci_enforcement" not in cats, repo.get("repo_name")


def test_observational_entries_match_guard_path_prefixes() -> None:
    """Every observational path entry must be reflected in the
    authority-shape vocabulary guard_path_prefixes so the preflight
    actually skips it. Prevents drift where a path is declared
    observational in the registry but still scanned by the preflight."""
    import json

    registry = json.loads(
        (REPO_ROOT / "contracts" / "governance" / "authority_registry.json").read_text(encoding="utf-8")
    )
    vocab = json.loads(VOCAB_PATH.read_text(encoding="utf-8"))
    guard_paths = set(vocab.get("scope", {}).get("guard_path_prefixes", []))
    declared_paths = {e["path"] for e in registry.get("observational_path_entries", [])}
    missing = sorted(declared_paths - guard_paths)
    assert not missing, (
        "observational entries not registered in authority-shape "
        f"vocabulary guard_path_prefixes: {missing}"
    )
