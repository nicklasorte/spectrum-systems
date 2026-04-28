#!/usr/bin/env python3
"""D3L-MASTER-01 Phase 4 — maturity report builder.

Per-system maturity from upstream artifacts (evidence attachment, trust
gap signals) + priority freshness gate. Written to
artifacts/tls/d3l_maturity_report.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = REPO_ROOT / "artifacts" / "tls" / "d3l_registry_contract.json"
EVIDENCE_PATH = REPO_ROOT / "artifacts" / "tls" / "system_evidence_attachment.json"
TRUST_GAP_PATH = REPO_ROOT / "artifacts" / "tls" / "system_trust_gap_report.json"
FRESHNESS_GATE_PATH = REPO_ROOT / "artifacts" / "tls" / "d3l_priority_freshness_gate.json"
OUTPUT_PATH = REPO_ROOT / "artifacts" / "tls" / "d3l_maturity_report.json"

LEVELS = {
    0: "Unknown",
    1: "Emerging",
    2: "Developing",
    3: "Stable",
    4: "Trusted",
}

STRUCTURAL = {
    "missing_eval",
    "missing_lineage",
    "missing_replay",
    "missing_observability",
    "missing_control",
    "missing_enforcement_signal",
    "missing_readiness_evidence",
}

KEY_GAP_ORDER = [
    "missing_enforcement_signal",
    "missing_lineage",
    "missing_replay",
    "missing_observability",
    "missing_control",
    "missing_eval",
    "missing_readiness_evidence",
    "missing_tests",
    "schema_weakness",
]


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _structural_level(has_evidence: bool, structural: list[str], trust_state: str) -> int:
    if not has_evidence:
        return 0
    failing = len(structural)
    if failing >= 3:
        return 1
    if failing >= 2:
        return 1
    if failing == 1:
        return 2
    if trust_state in ("blocked_signal", "freeze_signal", "caution_signal", "warn"):
        return 3
    return 4


def _key_gap(failing: list[str]) -> str:
    for sig in KEY_GAP_ORDER:
        if sig in failing:
            return sig
    return failing[0] if failing else "no_recorded_gap"


def build_maturity_report() -> dict:
    contract = _load(CONTRACT_PATH)
    blocking: list[str] = []
    if contract is None:
        blocking.append("contract_missing")
    evidence_payload = _load(EVIDENCE_PATH)
    trust_payload = _load(TRUST_GAP_PATH)
    fresh_gate = _load(FRESHNESS_GATE_PATH)
    priority_fresh = bool(fresh_gate and fresh_gate.get("status") == "ok")

    if blocking:
        return {
            "artifact_type": "d3l_maturity_report",
            "phase": "D3L-MASTER-01",
            "schema_version": "d3l-master-01.v1",
            "generated_at": _now_iso(),
            "status": "fail-closed",
            "blocking_reasons": blocking,
            "rows": [],
            "level_counts": {str(k): 0 for k in LEVELS},
            "maturity_universe_size": 0,
            "staleness_caps_applied": 0,
            "priority_fresh": priority_fresh,
        }

    universe = list(contract["maturity_universe"])
    evidence_by_id: dict[str, dict] = {
        row["system_id"]: row for row in (evidence_payload or {}).get("systems", []) if isinstance(row, dict) and "system_id" in row
    }
    trust_by_id: dict[str, dict] = {
        row["system_id"]: row for row in (trust_payload or {}).get("systems", []) if isinstance(row, dict) and "system_id" in row
    }

    rows = []
    counts = {k: 0 for k in LEVELS}
    staleness_caps = 0
    for sid in universe:
        ev = evidence_by_id.get(sid) or {}
        tg = trust_by_id.get(sid) or {}
        has_evidence = bool(ev.get("has_evidence"))
        evidence_count = int(ev.get("evidence_count") or 0)
        failing = [s for s in (tg.get("failing_signals") or []) if isinstance(s, str)]
        structural = [s for s in failing if s in STRUCTURAL]
        trust_state = tg.get("trust_state") or "unknown_signal"
        level = _structural_level(has_evidence, structural, trust_state)
        if not priority_fresh and level == 4:
            level = 3
            staleness_caps += 1
        blocking_for_row: list[str] = []
        if not has_evidence:
            blocking_for_row.append("missing_evidence")
        if structural:
            blocking_for_row.append(f"structural_signals:{','.join(structural)}")
        if not priority_fresh:
            blocking_for_row.append("priority_artifact_not_fresh")
        rows.append({
            "system_id": sid,
            "level": level,
            "level_label": LEVELS[level],
            "status": "ready_signal" if level == 4 else "caution_signal" if level >= 2 else "fail-closed" if level == 1 else "unknown",
            "evidence_count": evidence_count,
            "has_evidence": has_evidence,
            "failing_signals": failing,
            "failing_structural_signals": structural,
            "trust_state": trust_state,
            "freshness_ok": priority_fresh,
            "key_gap": _key_gap(failing),
            "blocking_reasons": blocking_for_row,
        })
        counts[level] += 1

    return {
        "artifact_type": "d3l_maturity_report",
        "phase": "D3L-MASTER-01",
        "schema_version": "d3l-master-01.v1",
        "generated_at": _now_iso(),
        "status": "ok",
        "blocking_reasons": [],
        "rows": rows,
        "level_counts": {str(k): v for k, v in counts.items()},
        "maturity_universe_size": len(universe),
        "staleness_caps_applied": staleness_caps,
        "priority_fresh": priority_fresh,
        "sources": {
            "contract": str(CONTRACT_PATH.relative_to(REPO_ROOT)) if contract else None,
            "evidence": str(EVIDENCE_PATH.relative_to(REPO_ROOT)),
            "trust_gap": str(TRUST_GAP_PATH.relative_to(REPO_ROOT)),
            "freshness_gate": str(FRESHNESS_GATE_PATH.relative_to(REPO_ROOT)) if fresh_gate else None,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args(argv)

    report = build_maturity_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        rel = args.output.relative_to(REPO_ROOT)
    except ValueError:
        rel = args.output
    print(f"wrote {rel} status={report['status']} rows={len(report['rows'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
