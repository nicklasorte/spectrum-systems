#!/usr/bin/env python3
"""
AW1 Remediation Summary — scripts/run_aw1_summary.py

Reads persisted RemediationPlan objects from data/remediation_plans/,
produces a human-readable console report, and writes a structured JSON
summary to outputs/aw1_remediation_summary.json.

Usage
-----
    python scripts/run_aw1_summary.py

If data/remediation_plans/ is empty, run first:
    python scripts/run_remediation_mapping.py --all

Outputs
-------
- Console: summary statistics, target/action-type distributions, top mapped
  plans, and top ambiguous plans.
- JSON: outputs/aw1_remediation_summary.json
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List

# Ensure project root is on sys.path when run directly
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from spectrum_systems.modules.improvement.remediation_mapping import RemediationPlan
from spectrum_systems.modules.improvement.remediation_store import list_remediation_plans

_REMEDIATION_STORE_DIR = _ROOT / "data" / "remediation_plans"
_OUTPUTS_DIR = _ROOT / "outputs"

_RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _primary_proposal(plan: RemediationPlan) -> Dict:
    """Return the primary proposed action dict, or an empty dict."""
    if not plan.proposed_actions:
        return {}
    idx = plan.primary_proposal_index
    if 0 <= idx < len(plan.proposed_actions):
        return plan.proposed_actions[idx]
    return plan.proposed_actions[0]


def _print_divider(width: int = 60) -> None:
    print("  " + "─" * width)


def _print_plan_brief(plan: RemediationPlan) -> None:
    """Print the top-level fields shared by mapped and ambiguous plans."""
    print(f"    remediation_id:        {plan.remediation_id}")
    print(f"    cluster_id:            {plan.cluster_id}")
    print(f"    cluster_signature:     {plan.cluster_signature}")
    print(f"    dominant_error_codes:  {', '.join(plan.dominant_error_codes)}")
    print(f"    remediation_targets:   {', '.join(plan.remediation_targets)}")


def _print_mapped_plan(plan: RemediationPlan) -> None:
    _print_plan_brief(plan)
    pp = _primary_proposal(plan)
    if pp:
        print("    primary_proposal:")
        print(f"      action_type:       {pp.get('action_type', '')}")
        print(f"      target_component:  {pp.get('target_component', '')}")
        print(f"      confidence_score:  {pp.get('confidence_score', '')}")
        print(f"      risk_level:        {pp.get('risk_level', '')}")
        print(f"      rationale:         {pp.get('rationale', '')}")
    ev = plan.evidence_summary
    print("    evidence_summary:")
    print(f"      record_count:          {ev.get('record_count', '')}")
    print(f"      avg_cluster_confidence:{ev.get('avg_cluster_confidence', '')}")
    print(f"      pass_types:            {', '.join(ev.get('pass_types', []))}")


def _print_ambiguous_plan(plan: RemediationPlan) -> None:
    _print_plan_brief(plan)
    print(f"    mapping_status:        {plan.mapping_status}")
    print("    mapping_reasons:")
    for r in plan.mapping_reasons:
        print(f"      - {r}")


def _plan_to_mapped_dict(plan: RemediationPlan) -> dict:
    """Serialise a mapped plan to the report structure."""
    pp = _primary_proposal(plan)
    ev = plan.evidence_summary
    return {
        "remediation_id": plan.remediation_id,
        "cluster_id": plan.cluster_id,
        "cluster_signature": plan.cluster_signature,
        "dominant_error_codes": plan.dominant_error_codes,
        "remediation_targets": plan.remediation_targets,
        "primary_proposal": {
            "action_type": pp.get("action_type", ""),
            "target_component": pp.get("target_component", ""),
            "confidence_score": pp.get("confidence_score", 0.0),
            "risk_level": pp.get("risk_level", ""),
            "rationale": pp.get("rationale", ""),
        },
        "evidence_summary": {
            "record_count": ev.get("record_count", 0),
            "avg_cluster_confidence": ev.get("avg_cluster_confidence", 0.0),
            "pass_types": ev.get("pass_types", []),
        },
    }


def _plan_to_ambiguous_dict(plan: RemediationPlan) -> dict:
    """Serialise an ambiguous plan to the report structure."""
    return {
        "remediation_id": plan.remediation_id,
        "cluster_id": plan.cluster_id,
        "cluster_signature": plan.cluster_signature,
        "dominant_error_codes": plan.dominant_error_codes,
        "remediation_targets": plan.remediation_targets,
        "mapping_status": plan.mapping_status,
        "mapping_reasons": plan.mapping_reasons,
    }


# ---------------------------------------------------------------------------
# Selection helpers
# ---------------------------------------------------------------------------


def _select_top_mapped(plans: List[RemediationPlan], n: int = 3) -> List[RemediationPlan]:
    """Return up to *n* mapped plans sorted by (confidence DESC, record_count DESC, risk ASC)."""

    def _sort_key(p: RemediationPlan):
        pp = _primary_proposal(p)
        confidence = pp.get("confidence_score", 0.0)
        risk_rank = _RISK_ORDER.get(pp.get("risk_level", "medium"), 1)
        record_count = p.evidence_summary.get("record_count", 0)
        return (-confidence, -record_count, risk_rank)

    return sorted(plans, key=_sort_key)[:n]


def _select_top_ambiguous(plans: List[RemediationPlan], n: int = 3) -> List[RemediationPlan]:
    """Return up to *n* ambiguous plans sorted by (record_count DESC, mapping_reasons DESC)."""

    def _sort_key(p: RemediationPlan):
        record_count = p.evidence_summary.get("record_count", 0)
        return (-record_count, -len(p.mapping_reasons))

    return sorted(plans, key=_sort_key)[:n]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    plans = list_remediation_plans(_REMEDIATION_STORE_DIR)

    if not plans:
        print(
            "No remediation plans found in data/remediation_plans/.\n"
            "Run first:  python scripts/run_remediation_mapping.py --all"
        )
        sys.exit(0)

    mapped_plans = [p for p in plans if p.mapping_status == "mapped"]
    ambiguous_plans = [p for p in plans if p.mapping_status == "ambiguous"]
    rejected_plans = [p for p in plans if p.mapping_status == "rejected"]

    total = len(plans)
    n_mapped = len(mapped_plans)
    n_ambiguous = len(ambiguous_plans)
    n_rejected = len(rejected_plans)
    mapped_pct = round(100.0 * n_mapped / total, 2) if total > 0 else 0.0

    # Target component distribution (mapped plans only)
    target_counter: Counter[str] = Counter()
    for p in mapped_plans:
        for target in p.remediation_targets:
            target_counter[target] += 1

    # Action type distribution (all proposed actions across mapped plans)
    action_type_counter: Counter[str] = Counter()
    for p in mapped_plans:
        for action in p.proposed_actions:
            at = action.get("action_type", "")
            if at:
                action_type_counter[at] += 1

    top_mapped = _select_top_mapped(mapped_plans)
    top_ambiguous = _select_top_ambiguous(ambiguous_plans)

    # ── Console Output ────────────────────────────────────────────────────
    print()
    print("=" * 62)
    print("  AW1 REMEDIATION MAPPING SUMMARY")
    print("=" * 62)

    print()
    print("  1. SUMMARY STATISTICS")
    _print_divider()
    print(f"  total_plans:       {total}")
    print(f"  mapped_plans:      {n_mapped}")
    print(f"  ambiguous_plans:   {n_ambiguous}")
    print(f"  rejected_plans:    {n_rejected}")
    print(f"  mapped_percentage: {mapped_pct:.2f}%")
    print()

    print("  2. REMEDIATION TARGET DISTRIBUTION")
    _print_divider()
    if target_counter:
        for target, count in target_counter.most_common():
            print(f"  {target}: {count}")
    else:
        print("  (no mapped plans)")
    print()

    print("  3. ACTION TYPE DISTRIBUTION")
    _print_divider()
    if action_type_counter:
        for action_type, count in action_type_counter.most_common():
            print(f"  {action_type}: {count}")
    else:
        print("  (no mapped plans)")
    print()

    print("  4. TOP MAPPED PLANS (up to 3)")
    _print_divider()
    if top_mapped:
        for i, plan in enumerate(top_mapped, start=1):
            print(f"  [{i}]")
            _print_mapped_plan(plan)
            print()
    else:
        print("  (no mapped plans)")
        print()

    print("  5. AMBIGUOUS PLANS (up to 3)")
    _print_divider()
    if top_ambiguous:
        for i, plan in enumerate(top_ambiguous, start=1):
            print(f"  [{i}]")
            _print_ambiguous_plan(plan)
            print()
    else:
        print("  (no ambiguous plans)")
        print()

    # ── JSON Output ────────────────────────────────────────────────────────
    output = {
        "summary": {
            "total_plans": total,
            "mapped_plans": n_mapped,
            "ambiguous_plans": n_ambiguous,
            "rejected_plans": n_rejected,
            "mapped_percentage": mapped_pct,
        },
        "target_distribution": dict(target_counter.most_common()),
        "action_type_distribution": dict(action_type_counter.most_common()),
        "top_mapped_plans": [_plan_to_mapped_dict(p) for p in top_mapped],
        "ambiguous_plans": [_plan_to_ambiguous_dict(p) for p in top_ambiguous],
    }

    _OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = _OUTPUTS_DIR / "aw1_remediation_summary.json"
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2)

    print(f"  6. JSON output written to: {report_path}")
    print()


if __name__ == "__main__":
    main()
