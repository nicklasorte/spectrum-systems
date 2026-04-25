#!/usr/bin/env python3
"""Run the authority-shape preflight (AGS-001) over changed files.

This is an early, fail-closed gate. It reuses the same changed-file resolution
as the system-registry guard and authority-leak guard so the three checks share
their notion of "what changed". Two modes are supported:

* ``--suggest-only`` (default): report violations with file/line/symbol,
  authority cluster, canonical owner, and suggested replacements.
* ``--apply-safe-renames``: apply unambiguous, owner-safe renames using the
  contracted ``safe_rename_pairs`` table and re-scan. Guard scripts and
  canonical owner files are protected from auto-remediation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.governance.authority_shape_preflight import (  # noqa: E402
    AuthorityShapePreflightError,
    evaluate_preflight,
    load_vocabulary,
)
from spectrum_systems.modules.governance.changed_files import (  # noqa: E402
    ChangedFilesResolutionError,
    resolve_changed_files,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Authority-shape preflight (AGS-001)")
    parser.add_argument("--base-ref", default="origin/main", help="Git base ref for changed-file resolution")
    parser.add_argument("--head-ref", default="HEAD", help="Git head ref for changed-file resolution")
    parser.add_argument("--changed-files", nargs="*", default=[], help="Explicit changed files")
    parser.add_argument(
        "--vocabulary",
        default="contracts/governance/authority_shape_vocabulary.json",
        help="Authority-shape vocabulary path",
    )
    parser.add_argument(
        "--output",
        default="outputs/authority_shape_preflight/authority_shape_preflight_result.json",
        help="Output artifact path",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--suggest-only",
        dest="mode",
        action="store_const",
        const="suggest-only",
        help="Report violations and suggested replacements (default)",
    )
    mode_group.add_argument(
        "--apply-safe-renames",
        dest="mode",
        action="store_const",
        const="apply-safe-renames",
        help="Apply unambiguous, owner-safe renames before re-checking",
    )
    parser.set_defaults(mode="suggest-only")
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
        raise AuthorityShapePreflightError(str(exc)) from exc

    vocab_path = REPO_ROOT / args.vocabulary
    vocab = load_vocabulary(vocab_path)

    result = evaluate_preflight(
        repo_root=REPO_ROOT,
        changed_files=changed_files,
        vocab=vocab,
        mode=args.mode,
    )

    output_path = REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = result.to_dict()
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    summary = {
        "status": payload["status"],
        "mode": payload["mode"],
        "changed_files": changed_files,
        "violation_count": payload["summary"]["violation_count"],
        "applied_rename_count": payload["summary"]["applied_rename_count"],
        "refused_rename_count": payload["summary"]["refused_rename_count"],
        "output": str(output_path),
    }
    if payload["violations"]:
        summary["first_violations"] = [
            {
                "file": v["file"],
                "line": v["line"],
                "symbol": v["symbol"],
                "cluster": v["cluster"],
                "canonical_owners": v["canonical_owners"],
                "suggested_replacements": v["suggested_replacements"],
            }
            for v in payload["violations"][:10]
        ]
    print(json.dumps(summary, indent=2))
    return 1 if payload["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
