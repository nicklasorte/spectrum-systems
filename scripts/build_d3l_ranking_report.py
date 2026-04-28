#!/usr/bin/env python3
"""D3L-MASTER-01 Phase 3 — ranking report artifact builder.

Projects the priority artifact onto the registry contract and emits
artifacts/tls/d3l_ranking_report.json with Top 3, Top 10, and Full
ranking views (active systems only).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PRIORITY_PATH = REPO_ROOT / "artifacts" / "system_dependency_priority_report.json"
PRIORITY_TLS_PATH = REPO_ROOT / "artifacts" / "tls" / "system_dependency_priority_report.json"
CONTRACT_PATH = REPO_ROOT / "artifacts" / "tls" / "d3l_registry_contract.json"
OUTPUT_PATH = REPO_ROOT / "artifacts" / "tls" / "d3l_ranking_report.json"


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _row_from_artifact(row: dict, fallback_rank: int) -> dict:
    return {
        "rank": row.get("rank") if isinstance(row.get("rank"), int) else fallback_rank,
        "system_id": row.get("system_id"),
        "classification": row.get("classification") or "active_system",
        "score": row.get("score") if isinstance(row.get("score"), (int, float)) else None,
        "action": row.get("action") or "",
        "why_now": row.get("why_now") or "",
        "trust_gap_signals": list(row.get("trust_gap_signals") or []),
        "prerequisite_systems": list((row.get("dependencies") or {}).get("upstream") or []),
        "unlocks": list(row.get("unlocks") or []),
        "finish_definition": row.get("finish_definition") or "",
        "next_prompt": row.get("next_prompt") or "",
        "trust_state": row.get("trust_state") or "unknown_signal",
        "is_in_priority_artifact": True,
        "is_registry_active": True,
    }


def _missing_row(system_id: str) -> dict:
    return {
        "rank": None,
        "system_id": system_id,
        "classification": "active_system",
        "score": None,
        "action": "no recommendation in current priority artifact",
        "why_now": "system absent from priority artifact; recompute pipeline",
        "trust_gap_signals": [],
        "prerequisite_systems": [],
        "unlocks": [],
        "finish_definition": "",
        "next_prompt": "",
        "trust_state": "unknown_signal",
        "is_in_priority_artifact": False,
        "is_registry_active": True,
    }


def build_ranking_report() -> dict:
    priority = _load(PRIORITY_PATH) or _load(PRIORITY_TLS_PATH)
    contract = _load(CONTRACT_PATH)

    blocking: list[str] = []
    if priority is None:
        blocking.append("priority_artifact_missing")
    if contract is None:
        blocking.append("contract_missing")
    if blocking:
        return {
            "artifact_type": "d3l_ranking_report",
            "phase": "D3L-MASTER-01",
            "schema_version": "d3l-master-01.v1",
            "generated_at": _now_iso(),
            "status": "fail-closed",
            "blocking_reasons": blocking,
            "ranking_universe_size": 0,
            "top_3": [],
            "top_10": [],
            "full": [],
            "excluded_from_priority": [],
            "missing_from_priority": [],
            "warnings": [],
        }

    universe = list(contract["ranking_universe"])  # type: ignore[index]
    universe_set = set(universe)
    source = priority.get("global_ranked_systems") or priority.get("top_5") or []  # type: ignore[union-attr]

    excluded: list[str] = []
    seen: set[str] = set()
    admitted: list[dict] = []
    running_rank = 0
    for row in source:
        if not isinstance(row, dict):
            continue
        sid = row.get("system_id")
        if not isinstance(sid, str):
            continue
        if sid in seen:
            continue
        if sid not in universe_set:
            excluded.append(sid)
            continue
        seen.add(sid)
        running_rank += 1
        admitted.append(_row_from_artifact(row, running_rank))

    missing: list[str] = []
    for sid in universe:
        if sid not in seen:
            missing.append(sid)
            admitted.append(_missing_row(sid))

    in_artifact = [r for r in admitted if r["is_in_priority_artifact"]]
    return {
        "artifact_type": "d3l_ranking_report",
        "phase": "D3L-MASTER-01",
        "schema_version": "d3l-master-01.v1",
        "generated_at": _now_iso(),
        "priority_generated_at": priority.get("generated_at"),
        "status": "ok",
        "blocking_reasons": [],
        "ranking_universe_size": len(universe),
        "top_3": in_artifact[:3],
        "top_10": in_artifact[:10],
        "full": admitted,
        "excluded_from_priority": excluded,
        "missing_from_priority": missing,
        "warnings": (
            [f"excluded_non_active:{','.join(excluded)}"] if excluded else []
        )
        + ([f"missing_from_priority:{','.join(missing)}"] if missing else []),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args(argv)

    report = build_ranking_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        rel = args.output.relative_to(REPO_ROOT)
    except ValueError:
        rel = args.output
    print(f"wrote {rel} status={report['status']} top_3_count={len(report['top_3'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
