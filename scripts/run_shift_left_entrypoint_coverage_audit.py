#!/usr/bin/env python3
"""Audit execution entrypoints for mandatory SLH front-door routing."""
from __future__ import annotations

import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]

ENTRYPOINT_RULES = {
    "scripts/pqx_runner.py": "scripts/run_shift_left_preflight.py",
    "scripts/run_enforced_execution.py": "scripts/run_shift_left_preflight.py",
}

ALT_BYPASS_PATTERNS = (
    "python -m pytest",
    "pytest ",
)


def _read(rel_path: str) -> str:
    path = REPO_ROOT / rel_path
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def main() -> int:
    missing_routes: list[str] = []
    bypass_paths: list[str] = []

    for rel_path, required_route in ENTRYPOINT_RULES.items():
        text = _read(rel_path)
        if not text:
            missing_routes.append(f"missing_entrypoint:{rel_path}")
            continue
        if required_route not in text:
            missing_routes.append(f"front_door_unrouted:{rel_path}")
        if any(pattern in text for pattern in ALT_BYPASS_PATTERNS) and required_route not in text:
            bypass_paths.append(rel_path)

    payload = {
        "status": "pass" if not (missing_routes or bypass_paths) else "fail",
        "missing_routes": missing_routes,
        "bypass_paths": sorted(set(bypass_paths)),
        "required_front_door": "scripts/run_shift_left_preflight.py",
        "entrypoints_checked": sorted(ENTRYPOINT_RULES),
    }

    out = REPO_ROOT / "outputs" / "shift_left_hardening" / "entrypoint_coverage_audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
