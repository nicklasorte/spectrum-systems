from __future__ import annotations

import argparse
import json
from pathlib import Path

from spectrum_systems.modules.hop.experience_store import ExperienceStore


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hop-cli", description="HOP artifact store query CLI")
    parser.add_argument("--store", required=True, help="Path to HOP store root")
    parser.add_argument("--min-score", type=float)
    parser.add_argument("--max-score", type=float)
    parser.add_argument("--since")
    parser.add_argument("--until")
    parser.add_argument("--artifact-type")

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list-top-candidates")
    sub.add_parser("show-frontier")

    diff = sub.add_parser("diff-candidates")
    diff.add_argument("candidate_a")
    diff.add_argument("candidate_b")

    sub.add_parser("show-failures")

    trace = sub.add_parser("inspect-trace")
    trace.add_argument("trace_id")
    return parser


def _rows(store: ExperienceStore, args: argparse.Namespace):
    return store.iter_records(
        min_score=args.min_score,
        max_score=args.max_score,
        since=args.since,
        until=args.until,
        artifact_type=args.artifact_type,
    )


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    store = ExperienceStore(Path(args.store))

    if args.command == "list-top-candidates":
        rows = [r for r in _rows(store, args) if r["schema"] == "harness_score"]
        rows.sort(key=lambda item: item["artifact"]["score"], reverse=True)
        print(json.dumps([row["artifact"] for row in rows[:20]], indent=2))
        return 0

    if args.command == "show-frontier":
        rows = [r for r in _rows(store, args) if r["schema"] == "harness_frontier"]
        print(json.dumps([row["artifact"] for row in rows], indent=2))
        return 0

    if args.command == "diff-candidates":
        a = store.get_candidate(args.candidate_a)
        b = store.get_candidate(args.candidate_b)
        print(json.dumps({"candidate_a": a, "candidate_b": b}, indent=2))
        return 0

    if args.command == "show-failures":
        rows = [r for r in _rows(store, args) if r["schema"] == "harness_failure_hypothesis"]
        print(json.dumps([row["artifact"] for row in rows], indent=2))
        return 0

    if args.command == "inspect-trace":
        rows = list(store.iter_records(trace_id=args.trace_id))
        print(json.dumps(rows, indent=2))
        return 0

    parser.error("unsupported command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
