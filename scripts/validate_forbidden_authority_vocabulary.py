#!/usr/bin/env python3
"""Fail-closed guard for forbidden authority vocabulary outside canonical owners."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCAN_PATHS = [
    "spectrum_systems/modules/transcript_hardening.py",
    "spectrum_systems/modules/runtime/downstream_product_substrate.py",
]
DEFAULT_OWNER_PATH_PREFIXES = [
    "spectrum_systems/modules/runtime/evaluation_control.py",
    "spectrum_systems/modules/runtime/enforcement_engine.py",
    "spectrum_systems/modules/runtime/cde_decision_flow.py",
    "spectrum_systems/modules/review_promotion_gate.py",
]
FORBIDDEN_KEYS = {
    "decision",
    "enforcement_action",
    "certification_status",
    "promote",
    "promoted",
    "allow",
    "block",
    "freeze",
    "readiness_to_close",
    "closure_decision",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate forbidden authority vocabulary boundaries")
    parser.add_argument("--scan-path", action="append", default=[], help="Path(s) to scan for forbidden keys")
    parser.add_argument(
        "--owner-path-prefix",
        action="append",
        default=[],
        help="Canonical owner path prefixes allowed to emit authority vocabulary",
    )
    return parser.parse_args()


def _find_forbidden_keys(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    findings: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    normalized = key.value.strip().lower()
                    if normalized in FORBIDDEN_KEYS:
                        findings.append((key.lineno, normalized))
    return findings


def main() -> int:
    args = _parse_args()
    scan_paths = [Path(p) for p in (args.scan_path or DEFAULT_SCAN_PATHS)]
    owner_prefixes = tuple(args.owner_path_prefix or DEFAULT_OWNER_PATH_PREFIXES)

    violations: list[tuple[str, int, str]] = []
    for relative_path in scan_paths:
        full_path = REPO_ROOT / relative_path
        if not full_path.exists():
            continue
        rel = str(relative_path)
        if rel.startswith(owner_prefixes):
            continue
        for lineno, key in _find_forbidden_keys(full_path):
            violations.append((rel, lineno, key))

    if violations:
        for rel, line, key in violations:
            print(f"{rel}:{line}: forbidden authority key '{key}' emitted outside canonical owners")
        return 1

    print("authority vocabulary guard passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
