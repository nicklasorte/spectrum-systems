#!/usr/bin/env python3
"""D3L-MASTER-01 Phase 5 — Rank ↔ Maturity alignment artifact builder.

Compares the Top 3 from artifacts/tls/d3l_ranking_report.json with the
maturity rows in artifacts/tls/d3l_maturity_report.json. Mismatch is a
warning; never a re-ranking.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RANKING_PATH = REPO_ROOT / "artifacts" / "tls" / "d3l_ranking_report.json"
MATURITY_PATH = REPO_ROOT / "artifacts" / "tls" / "d3l_maturity_report.json"
OUTPUT_PATH = REPO_ROOT / "artifacts" / "tls" / "d3l_rank_maturity_alignment.json"


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def evaluate(top3: list[dict], maturity_rows: list[dict]) -> dict:
    if not top3 or not maturity_rows:
        return {
            "ok": True,
            "warning": None,
            "top_3_above_lowest_maturity": [],
            "lowest_maturity_level": None,
            "top_3_levels": [],
            "notes": (["top_3_empty"] if not top3 else []) + (["maturity_universe_empty"] if not maturity_rows else []),
        }
    by_id = {row["system_id"]: row for row in maturity_rows}
    levels = [row["level"] for row in maturity_rows]
    lowest = min(levels)
    top3_levels = [
        {"system_id": r["system_id"], "level": by_id.get(r["system_id"], {}).get("level")}
        for r in top3
    ]
    above = [t["system_id"] for t in top3_levels if isinstance(t["level"], int) and t["level"] > lowest]
    missing = [t["system_id"] for t in top3_levels if t["level"] is None]
    notes: list[str] = []
    if missing:
        notes.append(f"top_3_without_maturity:{','.join(missing)}")
    warning: str | None = None
    ok = not above and not missing
    if above:
        warning = (
            f"Top 3 contains systems above the lowest maturity ({lowest}). "
            f"Above-lowest: {', '.join(above)}. "
            "Mismatch is informational; control authority (CDE) decides."
        )
    elif missing:
        warning = (
            f"Top 3 contains systems with no maturity data ({', '.join(missing)}). "
            "Mismatch is informational; control authority (CDE) decides."
        )
        ok = False
    return {
        "ok": ok,
        "warning": warning,
        "top_3_above_lowest_maturity": above,
        "lowest_maturity_level": lowest,
        "top_3_levels": top3_levels,
        "notes": notes,
    }


def build_alignment_report() -> dict:
    ranking = _load(RANKING_PATH)
    maturity = _load(MATURITY_PATH)
    blocking: list[str] = []
    if ranking is None:
        blocking.append("ranking_report_missing")
    if maturity is None:
        blocking.append("maturity_report_missing")
    if blocking:
        return {
            "artifact_type": "d3l_rank_maturity_alignment",
            "phase": "D3L-MASTER-01",
            "schema_version": "d3l-master-01.v1",
            "generated_at": _now_iso(),
            "status": "fail-closed",
            "blocking_reasons": blocking,
            "alignment": None,
        }

    top3 = ranking.get("top_3") or []
    rows = maturity.get("rows") or []
    alignment = evaluate(top3, rows)
    return {
        "artifact_type": "d3l_rank_maturity_alignment",
        "phase": "D3L-MASTER-01",
        "schema_version": "d3l-master-01.v1",
        "generated_at": _now_iso(),
        "status": "ok",
        "blocking_reasons": [],
        "alignment": alignment,
        "sources": {
            "ranking": str(RANKING_PATH.relative_to(REPO_ROOT)),
            "maturity": str(MATURITY_PATH.relative_to(REPO_ROOT)),
        },
        "rules": [
            "alignment is informational only; never mutates ranking",
            "control authority (CDE) decides; dashboard never re-orders",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args(argv)
    report = build_alignment_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        rel = args.output.relative_to(REPO_ROOT)
    except ValueError:
        rel = args.output
    print(f"wrote {rel} status={report['status']} alignment_ok={report.get('alignment', {}).get('ok') if report.get('alignment') else None}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
