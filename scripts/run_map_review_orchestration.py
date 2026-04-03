#!/usr/bin/env python3
"""Run MAP review orchestration: review->eval/control->roadmap->PQX->process-flow doc."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.repo_health_eval import (
    build_repo_health_control_decision,
    build_repo_health_eval,
)
from spectrum_systems.modules.runtime.repo_process_flow_doc import (
    generate_repo_process_flow_markdown,
    write_repo_process_flow_doc,
)
from spectrum_systems.modules.runtime.repo_review_snapshot_store import read_repo_review_snapshot
from spectrum_systems.modules.runtime.review_roadmap_generator import build_review_roadmap


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--sequence-state", required=True)
    parser.add_argument("--control-out", required=True)
    parser.add_argument("--roadmap-out", required=True)
    parser.add_argument("--process-doc-out", default="docs/reviews/repo_process_flow.md")
    args = parser.parse_args()

    snapshot = read_repo_review_snapshot(Path(args.snapshot))
    sequence_state = json.loads(Path(args.sequence_state).read_text(encoding="utf-8"))

    eval_artifacts = build_repo_health_eval(snapshot)
    control_decision = build_repo_health_control_decision(
        snapshot=snapshot,
        eval_summary=eval_artifacts["eval_summary"],
    )
    roadmap_plan = build_review_roadmap(snapshot=snapshot, control_decision=control_decision)

    control_out = Path(args.control_out)
    control_out.parent.mkdir(parents=True, exist_ok=True)
    control_out.write_text(json.dumps(control_decision, indent=2) + "\n", encoding="utf-8")

    roadmap_out = Path(args.roadmap_out)
    roadmap_out.parent.mkdir(parents=True, exist_ok=True)
    roadmap_out.write_text(json.dumps(roadmap_plan, indent=2) + "\n", encoding="utf-8")

    markdown = generate_repo_process_flow_markdown(
        snapshot=snapshot,
        eval_result=eval_artifacts["eval_result"],
        eval_summary=eval_artifacts["eval_summary"],
        control_decision=control_decision,
        roadmap_plan=roadmap_plan,
        sequence_state=sequence_state,
    )
    write_repo_process_flow_doc(markdown, output_path=args.process_doc_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
