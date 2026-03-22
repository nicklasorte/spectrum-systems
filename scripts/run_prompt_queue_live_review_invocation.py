#!/usr/bin/env python3
"""Thin CLI for single-item governed prompt queue live review invocation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    InvocationProviderResult,
    apply_live_review_invocation,
)


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run bounded live review invocation for a single work item")
    parser.add_argument("--queue-state-path", required=True)
    parser.add_argument("--work-item-id", required=True)
    parser.add_argument("--codex-result", choices=["success", "usage_limit", "rate_limited", "auth_failure", "timeout", "provider_unavailable", "failure"], default="success")
    parser.add_argument("--claude-result", choices=["success", "failure"], default="success")
    parser.add_argument("--output-reference", default="artifacts/prompt_queue/reviews/simulated.review.md")
    return parser.parse_args(argv)


def _simulate(result: str, output_reference: str):
    if result == "success":
        return lambda _wi: InvocationProviderResult(success=True, output_reference=output_reference)
    if result in {"usage_limit", "rate_limited", "auth_failure", "timeout", "provider_unavailable"}:
        return lambda _wi: InvocationProviderResult(success=False, failure_reason=result, error_message=f"simulated {result}")
    return lambda _wi: InvocationProviderResult(success=False, failure_reason="unexpected_failure", error_message="simulated failure")


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    queue_state_path = Path(args.queue_state_path)
    queue_state = json.loads(queue_state_path.read_text(encoding="utf-8"))

    updated_queue, updated_item, invocation_result = apply_live_review_invocation(
        queue_state=queue_state,
        work_item_id=args.work_item_id,
        queue_state_path=queue_state_path,
        repo_root=REPO_ROOT,
        run_codex=_simulate(args.codex_result, args.output_reference),
        run_claude=_simulate(args.claude_result, args.output_reference),
    )

    queue_state_path.write_text(json.dumps(updated_queue, indent=2) + "\n", encoding="utf-8")

    if updated_item.get("status") not in {
        "review_invocation_succeeded",
        "review_invocation_failed",
        "blocked",
    }:
        return 1

    print(json.dumps({"work_item": updated_item, "invocation_result": invocation_result}, indent=2))
    if updated_item.get("status") == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
