"""Replay AEX admission for a fixture and emit a deterministic replay record.

Usage:
    python scripts/replay_aex_admission.py --fixture <path> [--out <path>] [--out-dir <dir>]

Exits non-zero (fail-closed) if:

* the fixture does not exist
* AEX admission produces non-deterministic output across two runs
* the emitted admission_replay_record does not validate against
  schemas/aex/aex_admission_replay_record.schema.json
* the resolved default output path escapes the chosen output directory

REP retains replay authority. AEX produces only a replay observation.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.aex.admission_replay import (  # noqa: E402
    AEXReplayError,
    DEFAULT_REPLAY_COMMAND,
    replay_and_verify,
)


_SAFE_SEGMENT_PATTERN = re.compile(r"[^A-Za-z0-9._-]")


class ReplayPathEscapeError(AEXReplayError):
    """Raised when the default output path would escape its out_dir."""


def _sanitize_segment(value: str) -> str:
    """Reduce ``value`` to a single safe path segment.

    Only ``[A-Za-z0-9._-]`` characters survive; everything else (including
    path separators and NUL) is replaced with ``_``. Empty or
    bare-traversal forms (``"."``, ``".."``) collapse to ``"unknown"``.
    """
    safe = _SAFE_SEGMENT_PATTERN.sub("_", str(value or ""))
    if not safe or safe in {".", ".."}:
        return "unknown"
    return safe


def default_replay_output_path(*, record: Mapping[str, object], out_dir: Path) -> Path:
    """Compute the default output path for an admission_replay_record.

    The filename includes both ``request_id`` and ``replay_id`` to keep two
    replays with the same request id but different trace ids from
    overwriting each other. The resolved path must be rooted at
    ``out_dir``; otherwise ``ReplayPathEscapeError`` is raised
    (fail-closed).
    """
    out_dir_resolved = out_dir.resolve()
    safe_request_id = _sanitize_segment(str(record.get("request_id") or ""))
    safe_replay_id = _sanitize_segment(str(record.get("replay_id") or ""))
    filename = f"aex_admission_replay_{safe_request_id}_{safe_replay_id}.json"
    candidate = (out_dir_resolved / filename).resolve()
    if candidate.parent != out_dir_resolved:
        raise ReplayPathEscapeError(
            f"replay output path escapes out_dir={out_dir_resolved} "
            f"(sanitized request_id={safe_request_id!r}, "
            f"replay_id={safe_replay_id!r})"
        )
    return candidate


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
        help="Optional explicit output path for the admission_replay_record JSON. "
        "If absent, a default path is computed under --out-dir.",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Optional output directory for the default filename path. "
        "Defaults to artifacts/aex/ relative to the repo root.",
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

    out_dir = Path(args.out_dir) if args.out_dir else (REPO_ROOT / "artifacts" / "aex")
    if not out_dir.is_absolute():
        out_dir = (REPO_ROOT / out_dir).resolve()
    else:
        out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.out:
        out_path = Path(args.out)
        if not out_path.is_absolute():
            out_path = (REPO_ROOT / out_path).resolve()
        else:
            out_path = out_path.resolve()
    else:
        try:
            out_path = default_replay_output_path(record=record, out_dir=out_dir)
        except ReplayPathEscapeError as exc:
            print(f"FAIL: {exc}", file=sys.stderr)
            return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"OK replay {record['replay_status']}: {out_path}")
    print(json.dumps({k: record[k] for k in ("input_hash", "output_hash", "deterministic")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
