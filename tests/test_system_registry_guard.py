from __future__ import annotations

from pathlib import Path

from spectrum_systems.modules.governance.system_registry_guard import (
    evaluate_system_registry_guard,
    load_guard_policy,
    parse_system_registry,
)


def _policy() -> dict[str, object]:
    return {
        "policy_version": "1.0.0",
        "protected_authority_seams": {"execution": "PQX", "closure": "CDE", "override": "HIT"},
        "responsibility_clusters": {
            "execution": ["execution", "execute"],
            "closure": ["closure", "promotion"],
            "policy": ["policy", "admission"],
            "override_hitl": ["override", "human"],
        },
        "synonym_groups": {"execution": ["run"], "closure": ["finalization"]},
        "phrase_mappings": {
            "execute work": "execution",
            "closure decision": "closure",
            "human override": "override_hitl",
        },
        "system_like_path_prefixes": [
            "scripts/",
            "spectrum_systems/modules/",
            ".github/workflows/",
            "docs/governance/",
            "contracts/governance/",
        ],
        "reserved_or_transitional_path_prefixes": [
            "docs/reviews/",
            "docs/review-actions/",
            "contracts/examples/",
        ],
        "require_three_letter_system_tokens": True,
    }


def _registry_text() -> str:
    return """
# System Registry (Canonical)

## System Map
- **PQX** — bounded execution engine
- **CDE** — closure authority
- **HIT** — human override authority
- **OLD** — deprecated owner (deprecated)
- **REM** — retired owner (not currently present in this repository scope)
- **LCE** — placeholder lifecycle seam *(placeholder; control-plane seam)*

## System Definitions

### PQX
- **acronym:** `PQX`
- **full_name:** Prompt Queue Execution
- **role:** executes bounded work
- **owns:**
  - execution
- **consumes:**
  - task
- **produces:**
  - execution_record
- **must_not_do:**
  - issue closure decisions

### CDE
- **acronym:** `CDE`
- **full_name:** Closure Decision Engine
- **role:** closure decisions
- **owns:**
  - closure_decision
- **consumes:**
  - evidence
- **produces:**
  - closure_decision_artifact
- **must_not_do:**
  - execute work

### HIT
- **acronym:** `HIT`
- **full_name:** Human Interaction Touchpoint
- **role:** human override authority
- **owns:**
  - override_record
- **consumes:**
  - evidence
- **produces:**
  - hit_record
- **must_not_do:**
  - execute work

### OLD
- **acronym:** `OLD`
- **full_name:** Old Runtime
- **role:** retired owner
- **owns:**
  - retired_capability
- **consumes:**
  - none
- **produces:**
  - none
- **must_not_do:**
  - everything

### REM
- **acronym:** `REM`
- **full_name:** Removed Runtime
- **role:** removed owner
- **owns:**
  - removed_capability
- **consumes:**
  - none
- **produces:**
  - none
- **must_not_do:**
  - everything
""".strip()


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_parse_registry_model_classifies_statuses(tmp_path: Path) -> None:
    registry_path = tmp_path / "docs" / "architecture" / "system_registry.md"
    _write(registry_path, _registry_text())

    model = parse_system_registry(registry_path)

    assert "PQX" in model.active_systems
    assert "OLD" in model.deprecated_systems
    assert "REM" in model.removed_systems
    assert model.systems["PQX"].owns == ("execution",)


def test_guard_passes_for_existing_owner_reference(tmp_path: Path) -> None:
    registry_path = tmp_path / "docs" / "architecture" / "system_registry.md"
    _write(registry_path, _registry_text())
    _write(tmp_path / "docs" / "notes.md", "PQX owns execution and executes work slices.")

    result = evaluate_system_registry_guard(
        repo_root=tmp_path,
        changed_files=["docs/notes.md"],
        policy=_policy(),
        registry_model=parse_system_registry(registry_path),
    )

    assert result["status"] == "pass"


def test_guard_fails_when_new_acronym_appears_outside_registry(tmp_path: Path) -> None:
    registry_path = tmp_path / "docs" / "architecture" / "system_registry.md"
    _write(registry_path, _registry_text())
    _write(tmp_path / "docs" / "proposal.md", "### ZZZ\n- ZZZ owns execution decisions")

    result = evaluate_system_registry_guard(
        repo_root=tmp_path,
        changed_files=["docs/proposal.md"],
        policy=_policy(),
        registry_model=parse_system_registry(registry_path),
    )

    assert result["status"] == "fail"
    assert "NEW_SYSTEM_MISSING_REGISTRATION" in result["normalized_reason_codes"]


def test_guard_fails_on_removed_system_resurrection_and_protected_violation(tmp_path: Path) -> None:
    registry_path = tmp_path / "docs" / "architecture" / "system_registry.md"
    _write(registry_path, _registry_text())
    _write(tmp_path / "docs" / "resurrection.md", "REM owns execution authority. PQX claims closure decision.")

    result = evaluate_system_registry_guard(
        repo_root=tmp_path,
        changed_files=["docs/resurrection.md"],
        policy=_policy(),
        registry_model=parse_system_registry(registry_path),
    )

    assert result["status"] == "fail"
    codes = set(result["normalized_reason_codes"])
    assert "REMOVED_SYSTEM_REFERENCE" in codes
    assert "PROTECTED_AUTHORITY_VIOLATION" in codes
    assert any(item.get("resolution_category") == "fold_into_owner" for item in result["diagnostics"])


def test_guard_enforces_same_change_registration_fields(tmp_path: Path) -> None:
    registry_path = tmp_path / "docs" / "architecture" / "system_registry.md"
    _write(registry_path, _registry_text() + "\n\n### NEO\n- **acronym:** `NEO`\n")
    _write(tmp_path / "docs" / "expansion.md", "### NEO\n- NEO owns policy authority")

    result = evaluate_system_registry_guard(
        repo_root=tmp_path,
        changed_files=["docs/architecture/system_registry.md", "docs/expansion.md"],
        policy=_policy(),
        registry_model=parse_system_registry(registry_path),
    )

    assert result["status"] == "fail"
    assert "INCOMPLETE_SYSTEM_REGISTRATION" in result["normalized_reason_codes"]


def test_guard_detects_shadow_overlap_via_cluster_mapping(tmp_path: Path) -> None:
    registry_path = tmp_path / "docs" / "architecture" / "system_registry.md"
    _write(registry_path, _registry_text())
    _write(tmp_path / "docs" / "shadow.md", "CDE governs execute work for runtime queue.")

    result = evaluate_system_registry_guard(
        repo_root=tmp_path,
        changed_files=["docs/shadow.md"],
        policy=_policy(),
        registry_model=parse_system_registry(registry_path),
    )

    assert result["status"] == "fail"
    assert "SHADOW_OWNERSHIP_OVERLAP" in result["normalized_reason_codes"]


def test_guard_flags_unowned_system_like_surface(tmp_path: Path) -> None:
    registry_path = tmp_path / "docs" / "architecture" / "system_registry.md"
    _write(registry_path, _registry_text())
    _write(tmp_path / "scripts" / "unknown_surface.py", "# ZZZ owns execution authority for this helper\n")

    result = evaluate_system_registry_guard(
        repo_root=tmp_path,
        changed_files=["scripts/unknown_surface.py"],
        policy=_policy(),
        registry_model=parse_system_registry(registry_path),
    )

    assert result["status"] == "fail"
    assert "UNOWNED_SYSTEM_SURFACE" in result["normalized_reason_codes"]


def test_guard_allows_reserved_transitional_paths(tmp_path: Path) -> None:
    registry_path = tmp_path / "docs" / "architecture" / "system_registry.md"
    _write(registry_path, _registry_text())
    _write(tmp_path / "docs" / "reviews" / "note.md", "Historical note without owner claim.\n")

    result = evaluate_system_registry_guard(
        repo_root=tmp_path,
        changed_files=["docs/reviews/note.md"],
        policy=_policy(),
        registry_model=parse_system_registry(registry_path),
    )

    assert result["status"] == "pass"


def test_guard_allows_non_authority_manifest_metadata(tmp_path: Path) -> None:
    registry_path = tmp_path / "docs" / "architecture" / "system_registry.md"
    _write(registry_path, _registry_text())
    _write(
        tmp_path / "contracts" / "standards-manifest.json",
        '{\n  "contracts": [\n    {"notes": "FRE bounded repair candidate with no execution authority"}\n  ]\n}\n',
    )

    policy = _policy()
    policy["non_authority_exact_paths"] = ["contracts/standards-manifest.json"]
    policy["authoritative_owner_scan_suffixes"] = [".md", ".py"]

    result = evaluate_system_registry_guard(
        repo_root=tmp_path,
        changed_files=["contracts/standards-manifest.json"],
        policy=policy,
        registry_model=parse_system_registry(registry_path),
    )

    assert result["status"] == "pass"
    assert result["normalized_reason_codes"] == []


def test_current_fix02_changed_surface_passes_with_non_authority_classification() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    policy = load_guard_policy(repo_root / "contracts" / "governance" / "system_registry_guard_policy.json")
    registry = parse_system_registry(repo_root / "docs" / "architecture" / "system_registry.md")
    changed_files = [
        "contracts/examples/historical_pytest_exposure_backtest_result.json",
        "contracts/examples/three_letter_system_enforcement_audit_result.json",
        "contracts/governance/system_registry_guard_policy.json",
        "contracts/schemas/historical_pytest_exposure_backtest_result.schema.json",
        "contracts/schemas/three_letter_system_enforcement_audit_result.schema.json",
        "contracts/standards-manifest.json",
        "docs/governance/three_letter_system_policy.json",
        "docs/review-actions/PLAN-BXT-01-2026-04-14.md",
        "docs/reviews/BXT-01_backtest_and_3ls_strengthening_review.md",
        "docs/reviews/BXT-01_historical_pytest_exposure_backtest.md",
        "scripts/run_historical_pytest_exposure_backtest.py",
        "scripts/run_three_letter_system_enforcement_audit.py",
        "spectrum_systems/modules/governance/system_registry_guard.py",
        "spectrum_systems/modules/governance/three_letter_system_enforcement.py",
        "spectrum_systems/modules/runtime/historical_pytest_exposure_backtest.py",
        "tests/test_historical_pytest_exposure_backtest.py",
        "tests/test_system_registry_guard.py",
        "tests/test_three_letter_system_enforcement.py",
    ]
    result = evaluate_system_registry_guard(
        repo_root=repo_root,
        changed_files=changed_files,
        policy=policy,
        registry_model=registry,
    )
    assert result["status"] == "pass"
    assert result["normalized_reason_codes"] == []
