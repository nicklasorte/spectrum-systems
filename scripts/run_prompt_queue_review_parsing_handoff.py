#!/usr/bin/env python3
"""Thin CLI: invocation result output_reference -> findings parse handoff -> queue update."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    apply_review_parsing_handoff_to_queue,
    default_findings_path,
    default_review_parsing_handoff_path,
    run_review_parsing_handoff,
    validate_queue_state,
    write_artifact,
    write_findings_artifact,
    write_review_parsing_handoff_artifact,
)


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run governed prompt queue review parsing handoff")
    parser.add_argument("--work-item-id", required=True)
    parser.add_argument("--queue-state-path", required=True)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    return parser.parse_args(argv)


def _load_queue_state(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_work_item(queue_state: dict, work_item_id: str) -> dict:
    for item in queue_state.get("work_items", []):
        if item.get("work_item_id") == work_item_id:
            return item
    raise ValueError(f"Work item '{work_item_id}' not found.")


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    repo_root = Path(args.repo_root)
    queue_state_path = Path(args.queue_state_path)

    queue_state = _load_queue_state(queue_state_path)
    validate_queue_state(queue_state)
    work_item = _find_work_item(queue_state, args.work_item_id)

    invocation_result_artifact_path = work_item.get("review_invocation_result_artifact_path")
    if not invocation_result_artifact_path:
        raise ValueError("Work item missing review_invocation_result_artifact_path.")
    invocation_payload = json.loads((repo_root / invocation_result_artifact_path).read_text(encoding="utf-8"))

    handoff = run_review_parsing_handoff(
        work_item=work_item,
        review_invocation_result=invocation_payload,
        review_invocation_result_artifact_path=invocation_result_artifact_path,
        repo_root=repo_root,
        source_queue_state_path=str(queue_state_path),
    )

    findings_out = default_findings_path(work_item_id=args.work_item_id, root_dir=repo_root)
    write_findings_artifact(handoff["findings_artifact"], findings_out)

    handoff_out = default_review_parsing_handoff_path(work_item_id=args.work_item_id, queue_state_path=queue_state_path)
    write_review_parsing_handoff_artifact(artifact=handoff["handoff_artifact"], output_path=handoff_out)

    queue_updated, work_item_updated = apply_review_parsing_handoff_to_queue(
        queue_state=queue_state,
        work_item_id=args.work_item_id,
        findings_artifact_path=handoff["findings_artifact_path"],
        review_parsing_handoff_artifact_path=str(handoff_out.relative_to(repo_root)),
    )
    write_artifact(queue_updated, queue_state_path)

    print(
        json.dumps(
            {
                "queue_state_path": str(queue_state_path),
                "work_item_id": work_item_updated["work_item_id"],
                "findings_artifact_path": handoff["findings_artifact_path"],
                "review_parsing_handoff_artifact_path": str(handoff_out.relative_to(repo_root)),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
