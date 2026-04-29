#!/usr/bin/env python3
"""CLI: build failure_explanation_packet for a block/freeze outcome (CLX-ALL-01 Phase 5).

Usage:
    python scripts/run_failure_explanation.py \
        --outcome-json path/to/outcome.json \
        --trace-id TRACE_ID \
        [--output-json path/to/output.json]

The outcome JSON must have:
  - outcome_type: "block" | "freeze"
  - reason_code or block_reason
  - triggering_artifact_type
  - triggering_artifact_id

Exit codes:
    0 — packet built successfully
    1 — error building packet
    2 — usage/input error
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build failure explanation packet")
    parser.add_argument("--outcome-json", required=True, help="Path to block/freeze outcome JSON")
    parser.add_argument("--trace-id", default="")
    parser.add_argument("--output-json", default="")
    args = parser.parse_args(argv)

    outcome_path = Path(args.outcome_json)
    if not outcome_path.is_file():
        print(json.dumps({"error": f"outcome file not found: {args.outcome_json}"}))
        return 2

    try:
        outcome = json.loads(outcome_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"invalid JSON: {e}"}))
        return 2

    trace_id = args.trace_id or str(uuid.uuid4())

    from spectrum_systems.modules.runtime.failure_explanation import (
        FailureExplanationError,
        attach_explanation_to_block_outcome,
    )

    try:
        packet = attach_explanation_to_block_outcome(
            block_outcome=outcome,
            trace_id=trace_id,
        )
    except FailureExplanationError as e:
        print(json.dumps({"error": str(e)}))
        return 1

    output = json.dumps(packet, indent=2)
    print(output)

    if args.output_json:
        Path(args.output_json).write_text(output, encoding="utf-8")

    return 0


if __name__ == "__main__":
    sys.exit(main())
