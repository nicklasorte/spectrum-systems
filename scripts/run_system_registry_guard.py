#!/usr/bin/env python3
"""Run deterministic System Registry Guard (SRG) checks over changed files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.governance.system_registry_guard import (  # noqa: E402
    SystemRegistryGuardError,
    evaluate_system_registry_guard,
    load_guard_policy,
    parse_system_registry,
)
from spectrum_systems.modules.governance.changed_files import (  # noqa: E402
    ChangedFilesResolutionError,
    resolve_changed_files,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fail-closed system registry ownership guard")
    parser.add_argument("--base-ref", default="origin/main", help="Git base ref for changed-file resolution")
    parser.add_argument("--head-ref", default="HEAD", help="Git head ref for changed-file resolution")
    parser.add_argument("--changed-files", nargs="*", default=[], help="Explicit changed files")
    parser.add_argument(
        "--output",
        default="outputs/system_registry_guard/system_registry_guard_result.json",
        help="Output artifact path",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        changed_files = resolve_changed_files(
            repo_root=REPO_ROOT,
            base_ref=args.base_ref,
            head_ref=args.head_ref,
            explicit_changed_files=list(args.changed_files or []),
        )
    except ChangedFilesResolutionError as exc:
        raise SystemRegistryGuardError(str(exc)) from exc

    policy = load_guard_policy(REPO_ROOT / "contracts" / "governance" / "system_registry_guard_policy.json")
    registry = parse_system_registry(REPO_ROOT / "docs" / "architecture" / "system_registry.md")
    result = evaluate_system_registry_guard(
        repo_root=REPO_ROOT,
        changed_files=changed_files,
        policy=policy,
        registry_model=registry,
    )

    output_path = REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "status": result["status"],
                "changed_files": result["changed_files"],
                "reason_codes": result["normalized_reason_codes"],
                "output": str(output_path),
            },
            indent=2,
        )
    )
    return 1 if result["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
