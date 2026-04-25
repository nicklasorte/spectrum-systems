"""HOP query CLI.

Usage::

    python -m spectrum_systems.cli.hop_cli --root <store_path> <command> [options]

Commands:

- ``list-top-candidates`` — top-N candidate scores by score (descending).
- ``show-frontier`` — recompute and print the Pareto frontier from the store.
- ``diff-candidates`` — structured diff of two candidates by ``candidate_id``.
- ``show-failures`` — list ``hop_harness_failure_hypothesis`` artifacts.
- ``inspect-trace`` — print a single trace artifact.

The CLI streams the on-disk index (``iter_index``) line by line. Full history
is never loaded into memory; only the entries that match the filter survive.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from spectrum_systems.modules.hop.experience_store import ExperienceStore, HopStoreError
from spectrum_systems.modules.hop.frontier import compute_frontier


def _load_score(store: ExperienceStore, score_artifact_id: str) -> dict[str, Any]:
    return store.read_artifact("hop_harness_score", score_artifact_id)


def _parse_iso(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def _ts_filter_factory(
    after: str | None,
    before: str | None,
):
    after_dt = _parse_iso(after) if after else None
    before_dt = _parse_iso(before) if before else None

    def _accept(record: dict[str, Any]) -> bool:
        ts = record.get("timestamp")
        if ts is None:
            return True
        try:
            ts_dt = _parse_iso(ts)
        except ValueError:
            return True
        if after_dt is not None and ts_dt < after_dt:
            return False
        if before_dt is not None and ts_dt > before_dt:
            return False
        return True

    return _accept


def _emit(payload: Any) -> None:
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")


# ---------------------------------------------------------------------------
# subcommands
# ---------------------------------------------------------------------------

def cmd_list_top_candidates(args: argparse.Namespace) -> int:
    store = ExperienceStore(args.root)
    ts_pred = _ts_filter_factory(args.after, args.before)
    rows: list[dict[str, Any]] = []
    for rec in store.iter_index(artifact_type="hop_harness_score"):
        if not ts_pred(rec):
            continue
        fields = rec.get("fields", {})
        score = fields.get("score")
        if score is None:
            continue
        if args.min_score is not None and score < args.min_score:
            continue
        rows.append(
            {
                "candidate_id": fields.get("candidate_id"),
                "run_id": fields.get("run_id"),
                "score": score,
                "score_artifact_id": rec.get("artifact_id"),
                "timestamp": rec.get("timestamp"),
            }
        )
    rows.sort(key=lambda r: (-(r["score"] or 0), r.get("timestamp") or ""))
    _emit(rows[: args.limit])
    return 0


def cmd_show_frontier(args: argparse.Namespace) -> int:
    store = ExperienceStore(args.root)
    ts_pred = _ts_filter_factory(args.after, args.before)
    score_payloads: list[dict[str, Any]] = []
    for rec in store.iter_index(artifact_type="hop_harness_score"):
        if not ts_pred(rec):
            continue
        try:
            score_payloads.append(_load_score(store, rec["artifact_id"]))
        except HopStoreError as exc:
            sys.stderr.write(f"warning:hop_store_skipped:{exc}\n")
    members, dominated_count, considered = compute_frontier(score_payloads)
    _emit(
        {
            "considered_count": considered,
            "dominated_count": dominated_count,
            "member_count": len(members),
            "members": members,
        }
    )
    return 0


def _resolve_candidate(store: ExperienceStore, candidate_id: str) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    for rec in store.iter_index(artifact_type="hop_harness_candidate"):
        if rec.get("fields", {}).get("candidate_id") == candidate_id:
            matches.append(rec)
    if not matches:
        raise HopStoreError(f"hop_cli_candidate_not_found:{candidate_id}")
    if len(matches) > 1:
        raise HopStoreError(f"hop_cli_candidate_ambiguous:{candidate_id}")
    return store.read_artifact("hop_harness_candidate", matches[0]["artifact_id"])


def cmd_diff_candidates(args: argparse.Namespace) -> int:
    store = ExperienceStore(args.root)
    a = _resolve_candidate(store, args.left)
    b = _resolve_candidate(store, args.right)
    diff: dict[str, Any] = {"left": args.left, "right": args.right, "differences": {}}
    for key in sorted(set(a.keys()) | set(b.keys())):
        if a.get(key) != b.get(key):
            diff["differences"][key] = {"left": a.get(key), "right": b.get(key)}
    _emit(diff)
    return 0


def cmd_show_failures(args: argparse.Namespace) -> int:
    store = ExperienceStore(args.root)
    ts_pred = _ts_filter_factory(args.after, args.before)
    out: list[dict[str, Any]] = []
    for rec in store.iter_index(artifact_type="hop_harness_failure_hypothesis"):
        if not ts_pred(rec):
            continue
        fields = rec.get("fields", {})
        if args.candidate_id and fields.get("candidate_id") != args.candidate_id:
            continue
        if args.run_id and fields.get("run_id") != args.run_id:
            continue
        if args.severity and fields.get("severity") != args.severity:
            continue
        out.append(
            {
                "artifact_id": rec.get("artifact_id"),
                "timestamp": rec.get("timestamp"),
                "fields": fields,
            }
        )
        if args.limit and len(out) >= args.limit:
            break
    _emit(out)
    return 0


def cmd_inspect_trace(args: argparse.Namespace) -> int:
    store = ExperienceStore(args.root)
    payload = store.read_artifact("hop_harness_trace", args.trace_artifact_id)
    _emit(payload)
    return 0


# ---------------------------------------------------------------------------
# entrypoint
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hop_cli",
        description="HOP query CLI (read-only over the experience store).",
    )
    parser.add_argument(
        "--root",
        required=True,
        help="Path to the experience store root (directory containing index.jsonl).",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list-top-candidates")
    p_list.add_argument("--limit", type=int, default=10)
    p_list.add_argument("--min-score", type=float, default=None)
    p_list.add_argument("--after", default=None)
    p_list.add_argument("--before", default=None)
    p_list.set_defaults(func=cmd_list_top_candidates)

    p_front = sub.add_parser("show-frontier")
    p_front.add_argument("--after", default=None)
    p_front.add_argument("--before", default=None)
    p_front.set_defaults(func=cmd_show_frontier)

    p_diff = sub.add_parser("diff-candidates")
    p_diff.add_argument("--left", required=True)
    p_diff.add_argument("--right", required=True)
    p_diff.set_defaults(func=cmd_diff_candidates)

    p_fail = sub.add_parser("show-failures")
    p_fail.add_argument("--candidate-id", default=None)
    p_fail.add_argument("--run-id", default=None)
    p_fail.add_argument("--severity", default=None, choices=["info", "warn", "reject"])
    p_fail.add_argument("--limit", type=int, default=None)
    p_fail.add_argument("--after", default=None)
    p_fail.add_argument("--before", default=None)
    p_fail.set_defaults(func=cmd_show_failures)

    p_trace = sub.add_parser("inspect-trace")
    p_trace.add_argument("trace_artifact_id")
    p_trace.set_defaults(func=cmd_inspect_trace)

    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except HopStoreError as exc:
        sys.stderr.write(f"error:{exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
