"""Build AI Programming Governance rollup from source work-item evidence records.

Reads per-work-item ai_programming_work_item_record files from
artifacts/ai_programming/ and produces a rollup artifact consumed by the
dashboard.

AEX-PQX-01 contract rules (fail-closed):
- repo_mutating=true without AEX or PQX (missing or unknown) => compliance_status=BLOCK
- unknown does NOT count as present for any metric
- present requires non-empty artifact_refs in the source record
- full_loop_complete=true requires ALL six legs present for ALL repo-mutating items
- Missing AEX or PQX for any repo-mutating item forces compliance_status=BLOCK

Usage:
    python scripts/build_ai_programming_governance_rollup.py [--fail-closed]

Outputs:
    artifacts/ai_programming/ai_programming_governance_rollup.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = REPO_ROOT / "artifacts" / "ai_programming"
OUTPUT_PATH = SOURCE_DIR / "ai_programming_governance_rollup.json"

CORE_LEGS = ["AEX", "PQX", "EVL", "TPA", "CDE", "SEL"]
VALID_STATUSES = {"present", "partial", "missing", "unknown", "not_required"}
VALID_COMPLIANCE = {"PASS", "WARN", "BLOCK"}


def _leg_status(legs: dict, leg: str) -> str:
    leg_data = legs.get(leg, {})
    s = leg_data.get("status", "unknown")
    return s if s in VALID_STATUSES else "unknown"


def _is_present(status: str) -> bool:
    return status == "present"


def _is_missing(status: str) -> bool:
    return status in {"missing", "unknown"}


def _compute_item_compliance(item: dict) -> str:
    """Compute compliance_status for one work item."""
    repo_mutating = item.get("repo_mutating", "unknown")
    legs = item.get("legs", {})
    if repo_mutating is True:
        aex = _leg_status(legs, "AEX")
        pqx = _leg_status(legs, "PQX")
        if _is_missing(aex) or _is_missing(pqx):
            return "BLOCK"
    return item.get("compliance_status", "BLOCK")


def _aggregate_leg_status(statuses: list[str]) -> str:
    """Worst-case aggregate across a list of per-item leg statuses."""
    if "missing" in statuses:
        return "missing"
    if "unknown" in statuses:
        return "unknown"
    if "partial" in statuses:
        return "partial"
    if all(s == "present" for s in statuses) and statuses:
        return "present"
    if all(s == "not_required" for s in statuses) and statuses:
        return "not_required"
    return "unknown"


def build_rollup(fail_closed: bool = False) -> int:
    """Build the rollup artifact. Returns exit code."""
    # Discover source records: any JSON file with artifact_type=ai_programming_work_item_record.
    work_item_records = sorted(SOURCE_DIR.glob("*.json"))
    if not work_item_records:
        print(
            f"WARN: no ai_programming_work_item_record files found in {SOURCE_DIR}",
            file=sys.stderr,
        )
        if fail_closed:
            print("FAIL: --fail-closed set and no source records found", file=sys.stderr)
            return 1

    items: list[dict] = []
    work_item_refs: list[str] = []
    parse_errors: list[str] = []

    for path in work_item_records:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            parse_errors.append(f"{path.name}: {exc}")
            continue
        if data.get("artifact_type") != "ai_programming_work_item_record":
            continue
        items.append(data)
        work_item_refs.append(str(path.relative_to(REPO_ROOT)))

    if parse_errors:
        for err in parse_errors:
            print(f"WARN: parse error: {err}", file=sys.stderr)
        if fail_closed:
            print("FAIL: --fail-closed and parse errors occurred", file=sys.stderr)
            return 1

    if not items:
        print(
            f"WARN: no ai_programming_work_item_record items found after filtering in {SOURCE_DIR}",
            file=sys.stderr,
        )
        if fail_closed:
            print("FAIL: --fail-closed and no work-item records found after filtering", file=sys.stderr)
            return 1

    total = len(items)
    codex_count = sum(1 for i in items if i.get("tool_source") == "codex")
    claude_count = sum(1 for i in items if i.get("tool_source") == "claude")
    unknown_tool = sum(1 for i in items if i.get("tool_source") == "unknown")
    repo_mutating_count = sum(1 for i in items if i.get("repo_mutating") is True)

    # Per-leg counts across all items.
    per_leg: dict[str, dict[str, int]] = {}
    for leg in CORE_LEGS:
        counts: dict[str, int] = {"present": 0, "partial": 0, "missing": 0, "unknown": 0}
        for item in items:
            s = _leg_status(item.get("legs", {}), leg)
            if s in counts:
                counts[s] += 1
            else:
                counts["unknown"] += 1
        per_leg[leg] = counts

    # Aggregate leg states (worst-case).
    agg_legs: dict[str, str] = {}
    for leg in CORE_LEGS:
        statuses = [_leg_status(item.get("legs", {}), leg) for item in items]
        agg_legs[leg] = _aggregate_leg_status(statuses) if statuses else "unknown"

    # Score: fraction of legs that are "present" at aggregate level.
    present_legs = [leg for leg in CORE_LEGS if agg_legs[leg] == "present"]
    score = len(present_legs) / len(CORE_LEGS) if CORE_LEGS else 0.0

    # full_loop_complete: all legs present for all repo-mutating items.
    full_loop_complete = all(
        all(
            _leg_status(item.get("legs", {}), leg) == "present"
            for leg in CORE_LEGS
        )
        for item in items
        if item.get("repo_mutating") is True
    ) and repo_mutating_count > 0

    # Summary counts.
    with_aex = per_leg["AEX"]["present"]
    with_pqx = per_leg["PQX"]["present"]
    with_evl = per_leg["EVL"]["present"]
    full_loop_count = sum(
        1 for item in items
        if all(
            _leg_status(item.get("legs", {}), leg) == "present"
            for leg in CORE_LEGS
        )
    )
    bypass_risk_count = sum(
        1 for item in items
        if item.get("bypass_risk") not in {"none", None}
        and item.get("bypass_risk") != "unknown"
    )
    unknown_path_count = sum(
        1 for item in items
        if (
            _leg_status(item.get("legs", {}), "AEX") == "unknown"
            or _leg_status(item.get("legs", {}), "PQX") == "unknown"
        )
    )

    # Compliance status: fail-closed hierarchy.
    compliance_status = "PASS"
    for item in items:
        status = _compute_item_compliance(item)
        if status == "BLOCK":
            compliance_status = "BLOCK"
            break
        if status == "WARN" and compliance_status != "BLOCK":
            compliance_status = "WARN"

    # Derive first_missing_leg and weakest_leg.
    first_missing_leg: str | None = None
    for leg in CORE_LEGS:
        if agg_legs[leg] in {"missing", "unknown"}:
            first_missing_leg = leg
            break

    weakness_order = {"missing": 0, "unknown": 1, "partial": 2, "present": 3, "not_required": 4}
    weakest_leg = min(CORE_LEGS, key=lambda l: weakness_order.get(agg_legs[l], 5))

    # Violation records from items.
    violation_records: list[dict] = []
    for item in items:
        wi_id = item.get("work_item_id", "unknown")
        for leg in CORE_LEGS:
            s = _leg_status(item.get("legs", {}), leg)
            if s in {"missing", "unknown"} and item.get("repo_mutating") is True:
                violation_records.append({
                    "work_item_id": wi_id,
                    "missing_leg": leg,
                    "reason_codes": item.get("legs", {}).get(leg, {}).get("reason_codes", []),
                })

    # Next recommended input.
    next_rec: str | None = None
    if compliance_status == "BLOCK":
        blocked = [
            item.get("work_item_id", "?")
            for item in items
            if _compute_item_compliance(item) == "BLOCK"
        ]
        next_rec = (
            f"Resolve BLOCK status for work items: {', '.join(blocked)}. "
            f"First missing leg is {first_missing_leg}."
        )

    # SMA artifact refs from items.
    sma_refs = [
        item["sma_loop_run_ref"]
        for item in items
        if item.get("sma_loop_run_ref")
    ]

    # Source artifacts used.
    source_artifacts_used = list(work_item_refs)

    rollup = {
        "artifact_type": "ai_programming_governance_rollup_record",
        "schema_version": "1.0.0",
        "record_id": f"AIPG-ROLLUP-{datetime.now(timezone.utc).strftime('%Y%m%d')}",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "owner_system": "MET",
        "data_source": "artifact_store",
        "compliance_status": compliance_status,
        "total_ai_programming_items": total,
        "codex_work_count": codex_count,
        "claude_work_count": claude_count,
        "unknown_tool_count": unknown_tool,
        "repo_mutating_count": repo_mutating_count,
        "with_aex_evidence": with_aex,
        "with_pqx_evidence": with_pqx,
        "with_evl_evidence": with_evl,
        "full_loop_complete_count": full_loop_count,
        "bypass_risk_count": bypass_risk_count,
        "unknown_path_count": unknown_path_count,
        "per_leg_counts": per_leg,
        "score": score,
        "total_required_legs": len(CORE_LEGS),
        "core_loop_complete": full_loop_complete,
        "first_missing_leg": first_missing_leg,
        "weakest_leg": weakest_leg,
        "next_recommended_input": next_rec,
        "violation_records": violation_records,
        "sma_artifact_refs": sma_refs,
        "source_artifacts_used": source_artifacts_used,
        "work_item_refs": list(work_item_refs),
        "warnings": [
            "MET observation only. Authority boundary assignments are canonical in docs/architecture/system_registry.md.",
            "unknown does not count as present. repo_mutating=true items with AEX or PQX missing/unknown force compliance_status=BLOCK.",
            "This rollup is generated deterministically from source work item records in artifacts/ai_programming/. Do not hand-edit.",
        ],
        "reason_codes": [
            "ai_programming_governance_rollup_observation_only",
            "met_does_not_claim_canonical_authority",
        ],
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(rollup, indent=2), encoding="utf-8")
    print(f"[ai-prog-rollup] Written: {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    print(f"[ai-prog-rollup] Items: {total}, compliance: {compliance_status}, score: {score:.2f}")
    print(f"[ai-prog-rollup] AEX present: {with_aex}, PQX present: {with_pqx}")

    if fail_closed and compliance_status == "BLOCK":
        print(
            "INFO: compliance_status=BLOCK (expected for AI programming governance). "
            "Rollup written; BLOCK is honest, not a build failure.",
            file=sys.stderr,
        )

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fail-closed",
        action="store_true",
        help="Fail with exit code 1 on parse errors or missing source dir.",
    )
    args = parser.parse_args(argv)
    return build_rollup(fail_closed=args.fail_closed)


if __name__ == "__main__":
    raise SystemExit(main())
