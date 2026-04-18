#!/usr/bin/env python3
"""Run fail-closed authority leak detection over changed files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.authority_leak_rules import find_forbidden_vocabulary, load_authority_registry
from scripts.authority_shape_detector import detect_authority_shapes
from spectrum_systems.modules.governance.changed_files import (
    ChangedFilesResolutionError,
    resolve_changed_files,
)


class AuthorityLeakGuardError(ValueError):
    """Raised when authority leak guard cannot complete deterministically."""


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fail-closed authority leak guard")
    parser.add_argument("--base-ref", default="origin/main", help="Git base ref for changed-file resolution")
    parser.add_argument("--head-ref", default="HEAD", help="Git head ref for changed-file resolution")
    parser.add_argument("--changed-files", nargs="*", default=[], help="Explicit changed files")
    parser.add_argument(
        "--registry",
        default="contracts/governance/authority_registry.json",
        help="Authority registry path",
    )
    parser.add_argument(
        "--output",
        default="outputs/authority_leak_guard/authority_leak_guard_result.json",
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
        raise AuthorityLeakGuardError(str(exc)) from exc

    registry_path = REPO_ROOT / args.registry
    if not registry_path.is_file():
        raise AuthorityLeakGuardError(f"authority registry missing: {registry_path}")
    registry = load_authority_registry(registry_path)

    violations: list[dict[str, object]] = []
    scanned_files: list[str] = []

    for rel_path in changed_files:
        full_path = REPO_ROOT / rel_path
        if not full_path.is_file():
            continue
        if full_path.suffix.lower() not in {".py", ".json", ".md", ".yml", ".yaml", ".txt"}:
            continue

        scanned_files.append(rel_path)
        try:
            vocab_violations = find_forbidden_vocabulary(Path(rel_path), registry)
            shape_violations = detect_authority_shapes(Path(rel_path), registry)
        except (json.JSONDecodeError, UnicodeDecodeError, SyntaxError, ValueError) as exc:
            raise AuthorityLeakGuardError(f"failed to scan {rel_path}: {exc}") from exc

        violations.extend(vocab_violations)
        violations.extend(shape_violations)

    status = "fail" if violations else "pass"
    reason_codes = sorted({str(v.get("rule", "unknown")) for v in violations})
    result = {
        "artifact_type": "authority_leak_guard_result",
        "status": status,
        "changed_files": changed_files,
        "scanned_files": sorted(set(scanned_files)),
        "violations": violations,
        "normalized_reason_codes": reason_codes,
        "summary": {
            "violation_count": len(violations),
            "vocabulary_violation_count": sum(1 for v in violations if str(v.get("rule", "")).startswith("forbidden_")),
            "shape_violation_count": sum(1 for v in violations if str(v.get("rule", "")).startswith("authority_shape") or str(v.get("rule", "")).startswith("preparatory_")),
        },
    }

    output_path = REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "status": status,
                "changed_files": changed_files,
                "reason_codes": reason_codes,
                "output": str(output_path),
            },
            indent=2,
        )
    )
    return 1 if status == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
