from __future__ import annotations

import fnmatch
from pathlib import Path

from scripts import run_contract_preflight as preflight
from scripts.check_governance_compliance import (
    REGISTRY_PATH,
    classify_governed_surface_for_path,
    load_governed_prompt_surface_registry,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

GOVERNED_PROMPT_CANDIDATE_GLOBS = (
    "docs/governance/prompt_includes/*.md",
    "docs/governance/prompt_templates/*.md",
    "docs/architecture/strategy_guided_roadmap_prompt.md",
    "prompts/**/*.md",
    "prompts/*.md",
    "templates/review/*prompt*.md",
)


def _candidate_paths() -> list[str]:
    files = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in REPO_ROOT.rglob("*.md")
        if any(fnmatch.fnmatch(path.relative_to(REPO_ROOT).as_posix(), pattern) for pattern in GOVERNED_PROMPT_CANDIDATE_GLOBS)
    ]
    return sorted(set(files))


def test_registry_exists_and_is_non_empty() -> None:
    assert REGISTRY_PATH.exists()
    surfaces = load_governed_prompt_surface_registry()
    assert surfaces
    assert len({surface.surface_id for surface in surfaces}) == len(surfaces)


def test_every_governed_prompt_candidate_is_registry_covered() -> None:
    surfaces = load_governed_prompt_surface_registry()
    uncovered = [path for path in _candidate_paths() if classify_governed_surface_for_path(path, surfaces) is None]
    assert uncovered == []


def test_checker_and_preflight_surface_taxonomy_are_aligned() -> None:
    surfaces = load_governed_prompt_surface_registry()
    mismatches: list[str] = []
    for path in _candidate_paths():
        checker_surface = classify_governed_surface_for_path(path, surfaces)
        preflight_required, preflight_surface, _ = preflight._is_forced_evaluation_surface(path)
        if checker_surface is None:
            mismatches.append(f"checker-unclassified:{path}")
            continue
        if not preflight_required or preflight_surface != "governed_prompt_surface":
            mismatches.append(f"preflight-mismatch:{path}:{preflight_surface}")
    assert mismatches == []


def test_registry_required_paths_are_structurally_coherent() -> None:
    surfaces = load_governed_prompt_surface_registry()
    missing_paths: list[str] = []
    for surface in surfaces:
        for required_path in surface.required_references:
            if not (REPO_ROOT / required_path).exists():
                missing_paths.append(f"{surface.surface_id}:reference:{required_path}")
        include_rule_paths = [str(path) for path in surface.required_includes_or_templates.get("paths", [])]
        for include_path in include_rule_paths:
            if not (REPO_ROOT / include_path).exists():
                missing_paths.append(f"{surface.surface_id}:include:{include_path}")
    assert missing_paths == []
