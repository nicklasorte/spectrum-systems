#!/usr/bin/env python3
"""Thin CLI for generating governed prompt queue repair prompt artifacts from findings."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    RepairPromptGenerationError,
    attach_repair_prompt_to_work_item,
    default_repair_prompt_path,
    generate_repair_prompt_artifact,
    validate_work_item,
    write_artifact,
    write_repair_prompt_artifact,
)
from spectrum_systems.modules.prompt_queue.findings_artifact_io import read_json_artifact  # noqa: E402
from spectrum_systems.modules.prompt_queue.queue_models import utc_now  # noqa: E402


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate repair prompt artifact and attach to prompt queue work item")
    parser.add_argument("--work-item-id", required=True)
    parser.add_argument("--findings-artifact-path", required=True)
    parser.add_argument("--work-item-path", default=None)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    repo_root = Path(args.repo_root)
    findings_path = Path(args.findings_artifact_path)
    work_item_path = Path(args.work_item_path) if args.work_item_path else (
        repo_root / "artifacts" / "prompt_queue" / f"{args.work_item_id}.work_item.json"
    )

    work_item = read_json_artifact(work_item_path)
    findings_artifact = read_json_artifact(findings_path)

    try:
        repair_prompt_artifact = generate_repair_prompt_artifact(
            work_item=work_item,
            findings_artifact=findings_artifact,
            source_findings_artifact_path=str(findings_path),
            clock=utc_now,
        )
    except RepairPromptGenerationError as exc:
        print(json.dumps({"error": str(exc), "work_item_id": args.work_item_id}, indent=2), file=sys.stderr)
        return 2

    repair_prompt_path = default_repair_prompt_path(work_item_id=args.work_item_id, root_dir=repo_root)
    write_repair_prompt_artifact(repair_prompt_artifact, repair_prompt_path)

    updated_work_item = attach_repair_prompt_to_work_item(
        work_item,
        repair_prompt_artifact_path=str(repair_prompt_path),
        clock=utc_now,
    )
    validate_work_item(updated_work_item)
    write_artifact(updated_work_item, work_item_path)

    print(
        json.dumps(
            {
                "work_item_path": str(work_item_path),
                "repair_prompt_artifact_path": str(repair_prompt_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
