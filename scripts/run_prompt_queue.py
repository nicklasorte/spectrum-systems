#!/usr/bin/env python3
"""Thin CLI for governed prompt queue MVP orchestration."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    Priority,
    ProviderResult,
    RiskLevel,
    make_queue_state,
    make_work_item,
    run_review_with_fallback,
    validate_queue_state,
    validate_review_attempt,
    validate_work_item,
    write_artifact,
)


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run governed prompt queue MVP flow")
    parser.add_argument("--queue-id", required=True)
    parser.add_argument("--work-item-id", required=True)
    parser.add_argument("--prompt-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--scope-path", action="append", required=True, dest="scope_paths")
    parser.add_argument("--priority", choices=[e.value for e in Priority], default=Priority.MEDIUM.value)
    parser.add_argument("--risk-level", choices=[e.value for e in RiskLevel], default=RiskLevel.MEDIUM.value)
    parser.add_argument("--claude-result", choices=["success", "usage_limit", "timeout", "provider_unavailable", "failure"], default="success")
    parser.add_argument("--codex-result", choices=["success", "failure"], default="success")
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "artifacts" / "prompt_queue"))
    return parser.parse_args(argv)


def _simulate_provider(result: str, success_artifact: str):
    if result == "success":
        return lambda _wi: ProviderResult(success=True, review_artifact_path=success_artifact)
    if result in {"usage_limit", "timeout", "provider_unavailable"}:
        return lambda _wi: ProviderResult(success=False, failure_reason=result, error_message=f"Simulated {result}")
    return lambda _wi: ProviderResult(success=False, failure_reason="unknown_failure", error_message="Simulated failure")


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    output_dir = Path(args.output_dir)

    work_item = make_work_item(
        work_item_id=args.work_item_id,
        prompt_id=args.prompt_id,
        title=args.title,
        priority=Priority(args.priority),
        risk_level=RiskLevel(args.risk_level),
        repo=args.repo,
        branch=args.branch,
        scope_paths=args.scope_paths,
    )
    queue_state = make_queue_state(queue_id=args.queue_id, work_items=[work_item])

    claude_runner = _simulate_provider(args.claude_result, "artifacts/prompt_queue/claude_review.json")
    codex_runner = _simulate_provider(args.codex_result, "artifacts/prompt_queue/codex_review.json")
    updated_item, attempts = run_review_with_fallback(
        work_item,
        run_claude=claude_runner,
        run_codex=codex_runner,
    )

    queue_state["work_items"] = [updated_item]

    validate_work_item(updated_item)
    validate_queue_state(queue_state)
    for attempt in attempts:
        validate_review_attempt(attempt)

    work_item_path = write_artifact(updated_item, output_dir / f"{args.work_item_id}.work_item.json")
    queue_path = write_artifact(queue_state, output_dir / f"{args.queue_id}.queue_state.json")
    attempt_paths = [
        write_artifact(attempt, output_dir / f"{attempt['review_attempt_id']}.review_attempt.json")
        for attempt in attempts
    ]

    print(json.dumps({
        "work_item": str(work_item_path),
        "queue_state": str(queue_path),
        "review_attempts": [str(path) for path in attempt_paths],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
