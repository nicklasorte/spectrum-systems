#!/usr/bin/env python3
"""Fail-closed governance compliance checker for prompt text/files."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

REQUIRED_PATHS = {
    "strategy_control_doc": "docs/governance/strategy_control_doc.md",
    "source_inputs_manifest": "docs/governance/source_inputs_manifest.json",
    "source_loading_include": "docs/governance/prompt_includes/source_input_loading_include.md",
}

GOVERNANCE_INCLUDES = (
    "docs/governance/prompt_includes/roadmap_governance_include.md",
    "docs/governance/prompt_includes/implementation_governance_include.md",
)


@dataclass(frozen=True)
class ComplianceResult:
    passed: bool
    missing_items: list[str]


def evaluate_prompt_text(prompt_text: str) -> ComplianceResult:
    missing: list[str] = []

    for label, required_path in REQUIRED_PATHS.items():
        if required_path not in prompt_text:
            missing.append(f"missing required reference: {required_path} ({label})")

    if not any(include in prompt_text for include in GOVERNANCE_INCLUDES):
        missing.append(
            "missing governance include reference: include at least one of "
            + ", ".join(GOVERNANCE_INCLUDES)
        )

    return ComplianceResult(passed=not missing, missing_items=missing)


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
        "missing_items": result.missing_items,
    }
    if as_json:
        return json.dumps(payload, indent=2)

    if result.passed:
        return "PASS: governance compliance checks satisfied."

    lines = ["FAIL: governance compliance checks failed."]
    lines.extend(f"- {item}" for item in result.missing_items)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.file:
        prompt_text = args.file.read_text(encoding="utf-8")
    else:
        prompt_text = args.text

    result = evaluate_prompt_text(prompt_text)
    print(_render_result(result, as_json=args.json))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
