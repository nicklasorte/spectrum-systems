#!/usr/bin/env python3
"""Fail-closed validation for governed runtime ownership assignment."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = REPO_ROOT / "docs" / "governance" / "governed_runtime_ownership_map.json"


def _git_changed_paths(base_ref: str, head_ref: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base_ref}..{head_ref}"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "failed to diff paths")
    return sorted({line.strip() for line in result.stdout.splitlines() if line.strip()})


def _load_map() -> dict:
    payload = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("governed runtime ownership map must be a JSON object")
    return payload


def _classify(path: str, payload: dict) -> tuple[str | None, str | None]:
    prefixes = payload.get("governed_path_prefixes", [])
    for entry in prefixes:
        if not isinstance(entry, dict):
            continue
        prefix = str(entry.get("path") or "")
        if path.startswith(prefix):
            return str(entry.get("classification") or ""), entry.get("owner") if isinstance(entry.get("owner"), str) else None
    return None, None


def _is_waived(path: str, payload: dict) -> bool:
    waivers = payload.get("waivers", [])
    for waiver in waivers:
        if isinstance(waiver, dict) and str(waiver.get("path") or "") == path:
            return True
    return False


def validate_paths(paths: list[str]) -> list[str]:
    payload = _load_map()
    known_exact = {
        str(entry.get("path") or "")
        for entry in payload.get("governed_path_prefixes", [])
        if isinstance(entry, dict) and str(entry.get("path") or "").endswith(".py")
    }
    failures: list[str] = []
    for path in paths:
        if not path.startswith(("spectrum_systems/modules/runtime/", "scripts/")):
            continue
        file_exists = (REPO_ROOT / path).exists()
        classification, owner = _classify(path, payload)
        if not file_exists and path not in known_exact:
            failures.append(f"ownership_classification_missing:{path}")
            continue
        if classification is None:
            failures.append(f"ownership_classification_missing:{path}")
            continue
        if classification == "authority_bearing" and (owner is None or len(owner) != 3):
            failures.append(f"authority_owner_invalid:{path}:{owner}")
        if classification == "support_only" and owner is not None:
            failures.append(f"support_only_must_not_have_owner:{path}:{owner}")
        if _is_waived(path, payload):
            continue
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate governed runtime ownership declarations")
    parser.add_argument("--base-ref", default="HEAD~1")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--path", action="append", default=[])
    args = parser.parse_args(argv)

    changed = sorted(set(args.path)) if args.path else _git_changed_paths(args.base_ref, args.head_ref)
    failures = validate_paths(changed)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 2
    print(json.dumps({"status": "ok", "validated_paths": changed}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
