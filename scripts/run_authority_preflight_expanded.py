#!/usr/bin/env python3
"""CLI: run authority_preflight_expanded over changed files (CLX-ALL-01 Phase 1).

Usage:
    python scripts/run_authority_preflight_expanded.py \
        --base-ref origin/main --head-ref HEAD [--trace-id ID]

Exit codes:
    0 — no violations (pass)
    1 — violations detected (fail-closed)
    2 — usage/runtime error
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _changed_files(base_ref: str, head_ref: str) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{base_ref}...{head_ref}"],
            capture_output=True, text=True, cwd=REPO_ROOT, check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"git diff failed (exit {result.returncode}): "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
        return [f.strip() for f in result.stdout.splitlines() if f.strip()]
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"git diff error: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Expanded authority preflight scanner")
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--trace-id", default="")
    parser.add_argument("--output-json", default="", help="Write packet JSON to this path")
    args = parser.parse_args(argv)

    trace_id = args.trace_id or str(uuid.uuid4())

    try:
        changed = _changed_files(args.base_ref, args.head_ref)
    except RuntimeError as exc:
        print(json.dumps({"error": str(exc), "status": "error", "trace_id": trace_id}))
        return 2

    if not changed:
        print(json.dumps({"status": "pass", "message": "no changed files in scope", "trace_id": trace_id}))
        return 0

    from spectrum_systems.modules.runtime.authority_preflight_expanded import run_authority_preflight_expanded

    packet = run_authority_preflight_expanded(
        changed_files=changed,
        trace_id=trace_id,
        base_ref=args.base_ref,
        head_ref=args.head_ref,
    )

    output = json.dumps(packet, indent=2)
    print(output)

    if args.output_json:
        Path(args.output_json).write_text(output, encoding="utf-8")

    return 0 if packet["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
