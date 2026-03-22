#!/usr/bin/env python3
"""Thin CLI for parsing governed prompt queue review artifacts into findings artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    attach_findings_to_work_item,
    build_findings_artifact,
    default_findings_path,
    parse_review_markdown,
    validate_work_item,
    write_artifact,
    write_findings_artifact,
)
from spectrum_systems.modules.prompt_queue.findings_artifact_io import read_json_artifact  # noqa: E402
from spectrum_systems.modules.prompt_queue.queue_models import utc_now  # noqa: E402


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse review markdown and attach findings to prompt queue work item")
    parser.add_argument("--work-item-id", required=True)
    parser.add_argument("--review-artifact-path", required=True)
    parser.add_argument("--review-provider", choices=["claude", "codex"], required=True)
    parser.add_argument("--work-item-path", default=None)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    repo_root = Path(args.repo_root)

    work_item_path = Path(args.work_item_path) if args.work_item_path else (
        repo_root / "artifacts" / "prompt_queue" / f"{args.work_item_id}.work_item.json"
    )
    review_path = Path(args.review_artifact_path)

    work_item = read_json_artifact(work_item_path)
    markdown = review_path.read_text(encoding="utf-8")

    parsed_review = parse_review_markdown(markdown, provider=args.review_provider)
    findings = build_findings_artifact(
        work_item=work_item,
        parsed_review=parsed_review,
        source_review_artifact_path=str(review_path),
        clock=utc_now,
    )

    findings_path = default_findings_path(work_item_id=args.work_item_id, root_dir=repo_root)
    write_findings_artifact(findings, findings_path)

    updated_work_item = attach_findings_to_work_item(
        work_item,
        findings_artifact_path=str(findings_path),
        clock=utc_now,
    )
    validate_work_item(updated_work_item)
    write_artifact(updated_work_item, work_item_path)

    print(
        json.dumps(
            {
                "work_item_path": str(work_item_path),
                "findings_artifact_path": str(findings_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
