from __future__ import annotations

from pathlib import Path

from spectrum_systems.modules.governance.system_registry_guard import (
    evaluate_system_registry_guard,
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
