#!/usr/bin/env python3
"""CLI: run proof_presence_enforcement gate for a PR (CLX-ALL-01 Phase 2).

Usage:
    python scripts/run_proof_presence_enforcement.py \
        --base-ref origin/main --head-ref HEAD \
        --proof-artifact-json path/to/proof.json \
        [--pr-ref PR-123] [--trace-id ID]

Exit codes:
    0 — gate passes
    1 — gate blocks (proof missing or invalid)
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
    parser = argparse.ArgumentParser(description="Proof presence enforcement gate")
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--proof-artifact-json", default="", help="Path to proof artifact JSON file")
    parser.add_argument("--pr-ref", default="")
    parser.add_argument("--trace-id", default="")
    parser.add_argument("--output-json", default="")
    args = parser.parse_args(argv)

    trace_id = args.trace_id or str(uuid.uuid4())

    try:
        changed = _changed_files(args.base_ref, args.head_ref)
    except RuntimeError as exc:
        print(json.dumps({"error": str(exc), "status": "error", "gate_status": "error"}))
        return 2

    proof_artifact = None
    if args.proof_artifact_json:
        proof_path = Path(args.proof_artifact_json)
        if not proof_path.is_file():
            print(json.dumps({"error": f"proof artifact file not found: {args.proof_artifact_json}"}))
            return 2
        try:
            proof_artifact = json.loads(proof_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(json.dumps({"error": f"malformed proof artifact JSON: {exc}", "status": "error", "gate_status": "error"}))
            return 2

    from spectrum_systems.governance.proof_presence_enforcement import enforce_proof_presence

    result = enforce_proof_presence(
        changed_files=changed,
        proof_artifact=proof_artifact,
        trace_id=trace_id,
        pr_ref=args.pr_ref,
    )

    output = json.dumps(result, indent=2)
    print(output)

    if args.output_json:
        Path(args.output_json).write_text(output, encoding="utf-8")

    return 0 if result["gate_status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
