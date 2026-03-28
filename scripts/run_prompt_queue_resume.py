#!/usr/bin/env python3
"""Thin CLI wrapper for resume-from-checkpoint queue execution."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.prompt_queue import (  # noqa: E402
    read_json_artifact,
    resume_queue_from_checkpoint,
    write_artifact,
)


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resume prompt queue from a validated checkpoint")
    parser.add_argument("--checkpoint-path", required=True)
    parser.add_argument("--output-path", required=True)
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    checkpoint = read_json_artifact(Path(args.checkpoint_path))

    try:
        resumed_state = resume_queue_from_checkpoint(checkpoint)
        write_artifact(resumed_state, Path(args.output_path))
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 2

    print(json.dumps({"output_path": args.output_path, "queue_id": resumed_state.get("queue_id")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
