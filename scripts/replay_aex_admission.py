"""Replay AEX admission for a fixture and emit a deterministic replay record.

Usage:
    python scripts/replay_aex_admission.py --fixture <path> [--out <path>]

Exits non-zero (fail-closed) if:

* the fixture does not exist
* AEX admission produces non-deterministic output across two runs
* the emitted admission_replay_record does not validate against
  schemas/aex/aex_admission_replay_record.schema.json

REP retains replay authority. AEX produces only a replay observation.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.aex.admission_replay import (  # noqa: E402
    AEXReplayError,
    DEFAULT_REPLAY_COMMAND,
    replay_and_verify,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture",
        required=True,
        help="Path to a stored codex_build_request payload (JSON).",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Optional output path for the admission_replay_record JSON. "
        "Defaults to artifacts/aex/aex_admission_replay_<request_id>.json.",
    )
    args = parser.parse_args(argv)

    fixture_path = Path(args.fixture)
    if not fixture_path.is_absolute():
        fixture_path = (REPO_ROOT / fixture_path).resolve()

    try:
        record = replay_and_verify(
            fixture_path=fixture_path,
            replay_command=DEFAULT_REPLAY_COMMAND.format(fixture_path=str(fixture_path)),
        )
    except AEXReplayError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    out_dir = (REPO_ROOT / "artifacts" / "aex").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.out:
        out_path = Path(args.out)
        if not out_path.is_absolute():
            out_path = (REPO_ROOT / out_path).resolve()
        else:
            out_path = out_path.resolve()
    else:
        # Sanitize request_id: only [A-Za-z0-9._-] survives; any other
        # character (including path separators or NUL) is replaced with
        # '_'. The result must be a single path segment. The final write
        # target must remain rooted at artifacts/aex/.
        raw_request_id = str(record["request_id"])
        safe_request_id = re.sub(r"[^A-Za-z0-9._-]", "_", raw_request_id)
        if not safe_request_id or safe_request_id in {".", ".."}:
            safe_request_id = "unknown"
        candidate = (out_dir / f"aex_admission_replay_{safe_request_id}.json").resolve()
        if out_dir not in candidate.parents and candidate != out_dir:
            print(
                f"FAIL: replay output path escapes artifacts/aex (sanitized "
                f"request_id={safe_request_id!r})",
                file=sys.stderr,
            )
            return 1
        out_path = candidate
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"OK replay {record['replay_status']}: {out_path}")
    print(json.dumps({k: record[k] for k in ("input_hash", "output_hash", "deterministic")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
