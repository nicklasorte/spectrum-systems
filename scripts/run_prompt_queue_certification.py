#!/usr/bin/env python3
"""Thin CLI wrapper for deterministic fail-closed prompt queue certification."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    QueueCertificationError,
    run_queue_certification,
    validate_queue_certification_record,
    write_artifact,
)


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run prompt queue certification trust gate")
    parser.add_argument("--manifest-ref", required=True)
    parser.add_argument("--final-queue-state-ref", required=True)
    parser.add_argument("--observability-ref", required=True)
    parser.add_argument("--replay-checkpoint-ref", action="append", default=[])
    parser.add_argument("--replay-record-ref", required=True)
    parser.add_argument("--output-path", required=True)
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    refs = {
        "manifest_ref": args.manifest_ref,
        "final_queue_state_ref": args.final_queue_state_ref,
        "observability_ref": args.observability_ref,
        "replay_checkpoint_refs": args.replay_checkpoint_ref,
        "replay_record_ref": args.replay_record_ref,
    }

    try:
        certification = run_queue_certification(refs)
        validate_queue_certification_record(certification)
        write_artifact(certification, Path(args.output_path))
    except (QueueCertificationError, ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 2

    print(json.dumps({"output_path": args.output_path, "certification_status": certification["certification_status"]}, indent=2))
    return 0 if certification["certification_status"] == "passed" else 3


if __name__ == "__main__":
    raise SystemExit(main())
