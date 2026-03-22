#!/usr/bin/env python3
"""Thin CLI for findings-to-repair reentry wiring for one prompt queue work item."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    FindingsReentryError,
    FindingsReentryQueueIntegrationError,
    apply_findings_reentry_to_queue,
    default_findings_reentry_path,
    default_repair_prompt_path,
    run_findings_reentry,
    validate_queue_state,
    write_artifact,
    write_findings_reentry_artifact,
    write_repair_prompt_artifact,
)
from spectrum_systems.modules.prompt_queue.findings_artifact_io import read_json_artifact  # noqa: E402


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run findings-to-repair reentry for one governed prompt queue work item")
    parser.add_argument("--work-item-id", required=True)
    parser.add_argument("--queue-state-path", required=True)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    return parser.parse_args(argv)


def _find_work_item(queue_state: dict, work_item_id: str) -> dict:
    for item in queue_state.get("work_items", []):
        if item.get("work_item_id") == work_item_id:
            return item
    raise ValueError(f"Work item '{work_item_id}' not found.")


def _load_required_artifact(repo_root: Path, path: str, *, label: str) -> dict:
    if not path:
        raise ValueError(f"Work item missing {label}.")
    artifact_path = repo_root / path
    if not artifact_path.exists() or not artifact_path.is_file():
        raise ValueError(f"Missing {label}: {path}")
    return read_json_artifact(artifact_path)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    repo_root = Path(args.repo_root)
    queue_state_path = Path(args.queue_state_path)
    queue_state = read_json_artifact(queue_state_path)
    validate_queue_state(queue_state)

    try:
        work_item = _find_work_item(queue_state, args.work_item_id)
        findings_artifact_path = work_item.get("findings_artifact_path")
        handoff_artifact_path = work_item.get("review_parsing_handoff_artifact_path")
        invocation_result_artifact_path = work_item.get("review_invocation_result_artifact_path")

        findings_artifact = _load_required_artifact(
            repo_root,
            findings_artifact_path,
            label="findings_artifact_path",
        )
        handoff_artifact = _load_required_artifact(
            repo_root,
            handoff_artifact_path,
            label="review_parsing_handoff_artifact_path",
        )
        invocation_result_artifact = _load_required_artifact(
            repo_root,
            invocation_result_artifact_path,
            label="review_invocation_result_artifact_path",
        )

        repair_prompt_output_path = default_repair_prompt_path(work_item_id=args.work_item_id, root_dir=repo_root)
        repair_prompt_rel_path = str(repair_prompt_output_path.relative_to(repo_root))
        findings_reentry_output_path = default_findings_reentry_path(work_item_id=args.work_item_id, root_dir=repo_root)
        findings_reentry_rel_path = str(findings_reentry_output_path.relative_to(repo_root))

        result = run_findings_reentry(
            work_item=work_item,
            findings_artifact=findings_artifact,
            findings_artifact_path=findings_artifact_path,
            review_parsing_handoff_artifact=handoff_artifact,
            review_parsing_handoff_artifact_path=handoff_artifact_path,
            review_invocation_result_artifact=invocation_result_artifact,
            review_invocation_result_artifact_path=invocation_result_artifact_path,
            repair_prompt_artifact_path=repair_prompt_rel_path,
            source_queue_state_path=str(queue_state_path),
        )

        write_repair_prompt_artifact(result["repair_prompt_artifact"], repair_prompt_output_path)
        write_findings_reentry_artifact(artifact=result["reentry_artifact"], output_path=findings_reentry_output_path)

        updated_queue, updated_item = apply_findings_reentry_to_queue(
            queue_state=queue_state,
            work_item_id=args.work_item_id,
            findings_reentry_artifact_path=findings_reentry_rel_path,
            repair_prompt_artifact_path=repair_prompt_rel_path,
        )
        write_artifact(updated_queue, queue_state_path)
    except (ValueError, FindingsReentryError, FindingsReentryQueueIntegrationError) as exc:
        print(json.dumps({"error": str(exc), "work_item_id": args.work_item_id}, indent=2), file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "queue_state_path": str(queue_state_path),
                "work_item_id": updated_item["work_item_id"],
                "repair_prompt_artifact_path": repair_prompt_rel_path,
                "findings_reentry_artifact_path": findings_reentry_rel_path,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
