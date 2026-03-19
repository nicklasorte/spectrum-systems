#!/usr/bin/env python3
"""
AY Adversarial Summary — scripts/run_ay_adversarial_summary.py

Reads adversarial run records from ``data/observability/adversarial_run.json``
and the full observability store, then produces a structured summary report at
``outputs/ay_adversarial_summary.json``.

The script assumes ``run_operationalization.py --adversarial`` has already
been executed and the adversarial_run.json artifact is present.

Output sections
---------------
1. CASE SUMMARY
   - total_cases, cases_with_decisions, cases_with_no_decisions

2. FAILURE DISTRIBUTION
   - count by adversarial_type
   - count by failure_flags

3. GATING OUTCOMES
   - promote_count, hold_count, reject_count

4. TOP FAILURE MODES
   - most frequent gating_flags

5. CLUSTER HEALTH
   - total_clusters, invalid_clusters, low_cohesion_rate

6. EXAMPLES
   - 2 worst-performing cases with decisions + gating reason

Usage
-----
    python scripts/run_ay_adversarial_summary.py

Exit codes
----------
0  Summary written successfully.
1  adversarial_run.json not found (run with --adversarial first).
2  Unexpected error.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).resolve().parent
_ROOT = _SCRIPTS_DIR.parent

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_ADVERSARIAL_RUN_PATH = _ROOT / "data" / "observability" / "adversarial_run.json"
_VALIDATED_CLUSTERS_DIR = _ROOT / "data" / "validated_clusters"
_ERROR_CLUSTERS_DIR = _ROOT / "data" / "error_clusters"
_OUTPUTS_DIR = _ROOT / "outputs"
_SUMMARY_OUTPUT_PATH = _OUTPUTS_DIR / "ay_adversarial_summary.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_adversarial_records() -> List[Dict[str, Any]]:
    """Load adversarial run records from data/observability/adversarial_run.json."""
    if not _ADVERSARIAL_RUN_PATH.exists():
        print(
            f"ERROR: {_ADVERSARIAL_RUN_PATH.relative_to(_ROOT)} not found.\n"
            "       Run: python scripts/run_operationalization.py --adversarial",
            file=sys.stderr,
        )
        sys.exit(1)
    data = json.loads(_ADVERSARIAL_RUN_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        print("ERROR: adversarial_run.json must be a JSON array.", file=sys.stderr)
        sys.exit(2)
    return data


def _load_validated_clusters() -> List[Dict[str, Any]]:
    """Load all validated cluster JSON files."""
    clusters: List[Dict[str, Any]] = []
    if not _VALIDATED_CLUSTERS_DIR.exists():
        return clusters
    for p in sorted(_VALIDATED_CLUSTERS_DIR.glob("*.json")):
        try:
            clusters.append(json.loads(p.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass
    return clusters


def _load_error_clusters() -> List[Dict[str, Any]]:
    """Load all error cluster JSON files."""
    clusters: List[Dict[str, Any]] = []
    if not _ERROR_CLUSTERS_DIR.exists():
        return clusters
    for p in sorted(_ERROR_CLUSTERS_DIR.glob("*.json")):
        try:
            clusters.append(json.loads(p.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass
    return clusters


def _extract_decisions_from_record(rec: Dict[str, Any]) -> List[str]:
    """Extract decision texts from a single adversarial run record's pass_results."""
    decisions: List[str] = []
    for pr in rec.get("pass_results", []):
        raw_out = pr.get("_raw_output", {}) or {}
        for d in raw_out.get("decisions", []):
            if isinstance(d, dict):
                text = d.get("text", d.get("description", ""))
            else:
                text = str(d)
            if text:
                decisions.append(text.strip())
        for ai in raw_out.get("action_items", []):
            if isinstance(ai, dict):
                text = ai.get("text", ai.get("description", ""))
            else:
                text = str(ai)
            if text:
                decisions.append(f"[action] {text.strip()}")
    return decisions


def _worst_cases(records: List[Dict[str, Any]], n: int = 2) -> List[Dict[str, Any]]:
    """Return the n worst-performing cases by number of triggered gating flags."""
    scored = sorted(
        records,
        key=lambda r: len(r.get("gating_flags", [])),
        reverse=True,
    )
    return scored[:n]


# ---------------------------------------------------------------------------
# Summary builder
# ---------------------------------------------------------------------------


def build_summary(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build the full AY adversarial summary dict."""
    total_cases = len(records)

    # -----------------------------------------------------------------------
    # 1. Case summary
    # -----------------------------------------------------------------------
    cases_with_no_decisions = sum(
        1 for r in records if r["failure_flags"].get("no_decisions_extracted", False)
    )
    cases_with_decisions = total_cases - cases_with_no_decisions

    case_summary = {
        "total_cases": total_cases,
        "cases_with_decisions": cases_with_decisions,
        "cases_with_no_decisions": cases_with_no_decisions,
    }

    # -----------------------------------------------------------------------
    # 2. Failure distribution
    # -----------------------------------------------------------------------
    by_adversarial_type: Dict[str, int] = defaultdict(int)
    by_failure_flag: Dict[str, int] = defaultdict(int)

    for r in records:
        by_adversarial_type[r.get("adversarial_type", "unknown")] += 1
        for flag_name, triggered in r.get("failure_flags", {}).items():
            if triggered:
                by_failure_flag[flag_name] += 1

    failure_distribution = {
        "by_adversarial_type": dict(sorted(by_adversarial_type.items())),
        "by_failure_flag": dict(
            sorted(by_failure_flag.items(), key=lambda x: x[1], reverse=True)
        ),
    }

    # -----------------------------------------------------------------------
    # 3. Gating outcomes
    # -----------------------------------------------------------------------
    promote_count = sum(1 for r in records if r.get("promotion_recommendation") == "promote")
    hold_count = sum(1 for r in records if r.get("promotion_recommendation") == "hold")
    reject_count = sum(1 for r in records if r.get("promotion_recommendation") == "reject")

    gating_outcomes = {
        "promote_count": promote_count,
        "hold_count": hold_count,
        "reject_count": reject_count,
    }

    # -----------------------------------------------------------------------
    # 4. Top failure modes (gating_flags frequency)
    # -----------------------------------------------------------------------
    gating_flag_counts: Dict[str, int] = defaultdict(int)
    for r in records:
        for flag in r.get("gating_flags", []):
            gating_flag_counts[flag] += 1

    top_failure_modes = [
        {"flag": flag, "count": count}
        for flag, count in sorted(
            gating_flag_counts.items(), key=lambda x: x[1], reverse=True
        )
    ]

    # -----------------------------------------------------------------------
    # 5. Cluster health
    # -----------------------------------------------------------------------
    validated_clusters = _load_validated_clusters()
    all_clusters = _load_error_clusters()

    total_clusters = len(all_clusters)
    invalid_clusters = total_clusters - len(validated_clusters)
    low_cohesion_rate: Optional[float] = None

    if validated_clusters:
        low_cohesion = sum(
            1 for c in validated_clusters
            if c.get("cohesion_score", 1.0) < 0.5
        )
        low_cohesion_rate = round(low_cohesion / len(validated_clusters), 3)

    cluster_health = {
        "total_clusters": total_clusters,
        "invalid_clusters": invalid_clusters,
        "low_cohesion_rate": low_cohesion_rate,
    }

    # -----------------------------------------------------------------------
    # 6. Worst-performing case examples
    # -----------------------------------------------------------------------
    worst = _worst_cases(records, n=2)
    examples = []
    for r in worst:
        extracted_decisions = _extract_decisions_from_record(r)
        examples.append({
            "case_id": r.get("case_id"),
            "adversarial_type": r.get("adversarial_type"),
            "promotion_recommendation": r.get("promotion_recommendation"),
            "gating_decision_reason": r.get("gating_decision_reason"),
            "gating_flags": r.get("gating_flags", []),
            "extracted_decisions": extracted_decisions,
        })

    # -----------------------------------------------------------------------
    # Assemble
    # -----------------------------------------------------------------------
    return {
        "summary_type": "ay_adversarial_summary",
        "case_summary": case_summary,
        "failure_distribution": failure_distribution,
        "gating_outcomes": gating_outcomes,
        "top_failure_modes": top_failure_modes,
        "cluster_health": cluster_health,
        "worst_case_examples": examples,
    }


# ---------------------------------------------------------------------------
# Print helpers
# ---------------------------------------------------------------------------


def _print_summary(summary: Dict[str, Any]) -> None:
    """Print human-readable summary to stdout."""
    def _section(title: str) -> None:
        print()
        print("=" * 60)
        print(f"  {title}")
        print("=" * 60)

    _section("1. CASE SUMMARY")
    cs = summary["case_summary"]
    print(f"  total_cases             : {cs['total_cases']}")
    print(f"  cases_with_decisions    : {cs['cases_with_decisions']}")
    print(f"  cases_with_no_decisions : {cs['cases_with_no_decisions']}")

    _section("2. FAILURE DISTRIBUTION")
    fd = summary["failure_distribution"]
    print("  by adversarial_type:")
    for k, v in fd["by_adversarial_type"].items():
        print(f"    {k:<40}  {v}")
    print("  by failure_flag:")
    for k, v in fd["by_failure_flag"].items():
        print(f"    {k:<40}  {v}")

    _section("3. GATING OUTCOMES")
    go = summary["gating_outcomes"]
    print(f"  promote_count           : {go['promote_count']}")
    print(f"  hold_count              : {go['hold_count']}")
    print(f"  reject_count            : {go['reject_count']}")

    _section("4. TOP FAILURE MODES")
    for item in summary["top_failure_modes"][:3]:
        print(f"  {item['flag']:<40}  {item['count']}")

    _section("5. CLUSTER HEALTH")
    ch = summary["cluster_health"]
    print(f"  total_clusters          : {ch['total_clusters']}")
    print(f"  invalid_clusters        : {ch['invalid_clusters']}")
    print(f"  low_cohesion_rate       : {ch['low_cohesion_rate']}")

    _section("6. WORST-PERFORMING EXAMPLES")
    for i, ex in enumerate(summary["worst_case_examples"], 1):
        print(f"  [{i}] {ex['case_id']} ({ex['adversarial_type']})")
        print(f"      recommendation : {ex['promotion_recommendation']}")
        print(f"      gating reason  : {ex['gating_decision_reason']}")
        if ex["extracted_decisions"]:
            print("      extracted decisions:")
            for d in ex["extracted_decisions"][:3]:
                print(f"        - {d[:80]}")
        else:
            print("      extracted decisions: (none)")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    print()
    print("=" * 60)
    print("  AY Adversarial Summary")
    print("=" * 60)

    records = _load_adversarial_records()
    print(f"  Loaded {len(records)} adversarial run record(s)")

    _OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    summary = build_summary(records)
    _print_summary(summary)

    with _SUMMARY_OUTPUT_PATH.open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    print(f"  Summary written → {_SUMMARY_OUTPUT_PATH.relative_to(_ROOT)}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
