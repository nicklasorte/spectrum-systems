#!/usr/bin/env python3
"""Fail-closed governance compliance checker for prompt text/files."""
from __future__ import annotations

import argparse
import fnmatch
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "docs" / "governance" / "governed_prompt_surfaces.json"


@dataclass(frozen=True)
class ComplianceResult:
    passed: bool
    missing_items: list[str]
    governed: bool
    surface_id: str | None


@dataclass(frozen=True)
class GovernedPromptSurface:
    surface_id: str
    prompt_class: str
    path_globs: tuple[str, ...]
    requires_governance_check: bool
    required_references: tuple[str, ...]
    required_includes_or_templates: dict[str, Any]
    checked_by: tuple[str, ...]
    notes: str


def load_governed_prompt_surface_registry(registry_path: Path = REGISTRY_PATH) -> list[GovernedPromptSurface]:
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    surfaces: list[GovernedPromptSurface] = []
    for item in payload.get("surfaces", []):
        surfaces.append(
            GovernedPromptSurface(
                surface_id=item["surface_id"],
                prompt_class=item["prompt_class"],
                path_globs=tuple(item.get("path_globs", [])),
                requires_governance_check=bool(item.get("requires_governance_check", True)),
                required_references=tuple(item.get("required_references", [])),
                required_includes_or_templates=dict(item.get("required_includes_or_templates", {"mode": "all_of", "paths": []})),
                checked_by=tuple(item.get("checked_by", [])),
                notes=str(item.get("notes", "")),
            )
        )
    return surfaces


def classify_governed_surface_for_path(path: str, surfaces: list[GovernedPromptSurface]) -> GovernedPromptSurface | None:
    for surface in surfaces:
        for pattern in surface.path_globs:
            if fnmatch.fnmatch(path, pattern):
                return surface
    return None


def _validate_required_includes(prompt_text: str, include_rule: dict[str, Any], missing: list[str]) -> None:
    mode = str(include_rule.get("mode", "all_of"))
    paths = [str(path) for path in include_rule.get("paths", [])]
    if not paths:
        return
    if mode == "all_of":
        for include_path in paths:
            if include_path not in prompt_text:
                missing.append(f"missing required include/template reference: {include_path}")
        return
    if mode == "any_of" and not any(include_path in prompt_text for include_path in paths):
        missing.append("missing governance include/template reference: include at least one of " + ", ".join(paths))
        return
    if mode not in {"all_of", "any_of"}:
        missing.append(f"invalid include rule mode in registry: {mode}")


def evaluate_prompt_text(prompt_text: str, surface: GovernedPromptSurface | None = None) -> ComplianceResult:
    if surface is None:
        required_refs = [
            "docs/governance/strategy_control_doc.md",
            "docs/governance/source_inputs_manifest.json",
            "docs/governance/prompt_includes/source_input_loading_include.md",
        ]
        include_rule = {
            "mode": "any_of",
            "paths": [
                "docs/governance/prompt_includes/roadmap_governance_include.md",
                "docs/governance/prompt_includes/implementation_governance_include.md",
            ],
        }
        surface_id = "raw_text_default"
    else:
        required_refs = list(surface.required_references)
        include_rule = surface.required_includes_or_templates
        surface_id = surface.surface_id

    missing: list[str] = []
    for required_path in required_refs:
        if required_path not in prompt_text:
            missing.append(f"missing required reference: {required_path}")
    _validate_required_includes(prompt_text, include_rule, missing)

    return ComplianceResult(passed=not missing, missing_items=missing, governed=True, surface_id=surface_id)


def _path_for_surface_classification(file_path: Path) -> str | None:
    resolved = file_path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return None


def evaluate_prompt_file(file_path: Path, surfaces: list[GovernedPromptSurface]) -> ComplianceResult:
    prompt_text = file_path.read_text(encoding="utf-8")
    relative_path = _path_for_surface_classification(file_path)

    if relative_path is None:
        return evaluate_prompt_text(prompt_text)

    surface = classify_governed_surface_for_path(relative_path, surfaces)
    if surface is None or not surface.requires_governance_check:
        return ComplianceResult(passed=True, missing_items=[], governed=False, surface_id=None)
    return evaluate_prompt_text(prompt_text, surface=surface)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate prompt governance references (fail-closed)."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", type=Path, help="Path to prompt file to validate.")
    source.add_argument("--text", help="Raw prompt text to validate.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON output instead of plain text.",
    )
    return parser.parse_args(argv)


def _render_result(result: ComplianceResult, *, as_json: bool) -> str:
    payload = {
        "status": "PASS" if result.passed else "FAIL",
        "governed": result.governed,
        "surface_id": result.surface_id,
        "missing_items": result.missing_items,
    }
    if as_json:
        return json.dumps(payload, indent=2)

    if result.passed and not result.governed:
        return "PASS: file is outside governed prompt surfaces; governance checks not required."
    if result.passed:
        return "PASS: governance compliance checks satisfied."

    lines = ["FAIL: governance compliance checks failed."]
    lines.extend(f"- {item}" for item in result.missing_items)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.file:
        surfaces = load_governed_prompt_surface_registry()
        result = evaluate_prompt_file(args.file, surfaces)
    else:
        result = evaluate_prompt_text(args.text)

    print(_render_result(result, as_json=args.json))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
