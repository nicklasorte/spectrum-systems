#!/usr/bin/env python3
"""Thin CLI for deterministic Codex-to-PQX task wrapper construction (CON-038)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.codex_to_pqx_task_wrapper import (
    CodexToPQXWrapperError,
    build_codex_pqx_task_wrapper,
    dump_wrapper,
    run_wrapped_pqx_task,
)


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build deterministic Codex-to-PQX wrapper payload")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--step-id", required=True)
    parser.add_argument("--step-name", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--execution-context", required=True)
    parser.add_argument("--requested-at", default=_utc_now())
    parser.add_argument("--dependency", action="append", default=[])
    parser.add_argument("--changed-path", action="append", default=[])
    parser.add_argument("--authority-evidence-ref")
    parser.add_argument("--contract-preflight-result-artifact-path")
    parser.add_argument("--authority-notes")
    parser.add_argument("--roadmap-version")
    parser.add_argument("--row-index", type=int, default=0)
    parser.add_argument("--row-status", default="ready")
    parser.add_argument("--output-path", type=Path)
    parser.add_argument("--execute-pqx", action="store_true")
    parser.add_argument("--pqx-output-text")
    parser.add_argument("--roadmap-path", type=Path, default=REPO_ROOT / "docs" / "roadmap" / "system_roadmap.md")
    parser.add_argument("--state-path", type=Path, default=REPO_ROOT / "data" / "pqx_state.json")
    parser.add_argument("--runs-root", type=Path, default=REPO_ROOT / "data" / "pqx_runs")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        build_result = build_codex_pqx_task_wrapper(
            {
                "task_id": args.task_id,
                "run_id": args.run_id,
                "step_id": args.step_id,
                "step_name": args.step_name,
                "prompt": args.prompt,
                "execution_context": args.execution_context,
                "requested_at": args.requested_at,
                "dependencies": list(args.dependency),
                "changed_paths": list(args.changed_path),
                "authority_context": {
                    "authority_evidence_ref": args.authority_evidence_ref,
                    "contract_preflight_result_artifact_path": args.contract_preflight_result_artifact_path,
                    "notes": args.authority_notes,
                },
                "roadmap_version": args.roadmap_version,
                "row_index": args.row_index,
                "row_status": args.row_status,
            }
        )
    except CodexToPQXWrapperError as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, indent=2))
        return 2

    wrapper = build_result.wrapper

    if args.output_path:
        dump_wrapper(args.output_path, wrapper)

    response: dict[str, object] = {
        "status": "ok",
        "wrapper": wrapper,
        "runner_kwargs": build_result.runner_kwargs,
        "output_path": str(args.output_path) if args.output_path else None,
    }

    if args.execute_pqx:
        if not isinstance(args.pqx_output_text, str) or not args.pqx_output_text.strip():
            print(json.dumps({"status": "blocked", "error": "--pqx-output-text is required when --execute-pqx is set"}, indent=2))
            return 2
        try:
            response["pqx_result"] = run_wrapped_pqx_task(
                wrapper=wrapper,
                roadmap_path=args.roadmap_path,
                state_path=args.state_path,
                runs_root=args.runs_root,
                pqx_output_text=args.pqx_output_text,
            )
        except CodexToPQXWrapperError as exc:
            print(json.dumps({"status": "blocked", "error": str(exc)}, indent=2))
            return 2

    print(json.dumps(response, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
