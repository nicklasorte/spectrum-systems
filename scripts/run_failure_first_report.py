#!/usr/bin/env python3
"""Run failure-first observability report generation."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.observability.aggregation import (  # noqa: E402
    compute_failure_first_metrics,
    enrich_failure_first_flags,
)
from spectrum_systems.modules.observability.failure_ranking import (  # noqa: E402
    rank_dangerous_promotes,
    rank_failure_modes,
    rank_pass_weaknesses,
    rank_worst_cases,
)

_DEFAULT_JSON_OUTPUT = _REPO_ROOT / "outputs" / "failure_first_report.json"
_REPORT_ARCHIVE_DIR = _REPO_ROOT / "data" / "observability_reports"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _collect_case_records(observability_dir: Path, include_adversarial: bool, include_operationalization: bool) -> List[Dict[str, Any]]:
    case_records: List[Dict[str, Any]] = []

    for path in sorted(observability_dir.glob("*.json")):
        data = _load_json(path)
        if isinstance(data, dict):
            # AP observability records are pass-level, not case-level; keep minimal signal.
            flags = data.get("flags", {})
            error_summary = data.get("error_summary", {})
            case_records.append(
                {
                    "case_id": data.get("context", {}).get("case_id") or data.get("context", {}).get("artifact_id") or data.get("record_id"),
                    "artifact_id": data.get("context", {}).get("artifact_id"),
                    "pass_results": [
                        {
                            "pass_type": data.get("pass_info", {}).get("pass_type", "unknown"),
                            "schema_validation": {"status": "passed" if flags.get("schema_valid", True) else "failed"},
                        }
                    ],
                    "failure_flags": {
                        "structural_failure": bool(data.get("metrics", {}).get("structural_score", 1.0) < 0.6),
                        "inconsistent_grounding": not bool(flags.get("grounding_passed", True)),
                        "no_decisions_extracted": False,
                        "duplicate_decisions": False,
                    },
                    "promotion_recommendation": "reject" if error_summary.get("failure_count", 0) > 0 else "hold",
                    "gating_decision_reason": "derived_from_observability_record",
                    "confidence": "medium" if data.get("metrics", {}).get("semantic_score", 0.0) >= 0.7 else "low",
                    "downstream_failure": error_summary.get("failure_count", 0) > 0,
                    "structural_score": data.get("metrics", {}).get("structural_score"),
                }
            )
        elif isinstance(data, list) and include_adversarial:
            # Existing adversarial-run aggregate format.
            for row in data:
                if not isinstance(row, dict):
                    continue
                case_records.append(dict(row))

    if include_operationalization:
        sim_dir = _REPO_ROOT / "data" / "simulation_results"
        for path in sorted(sim_dir.glob("*.json")):
            data = _load_json(path)
            if not isinstance(data, dict):
                continue
            rec = {
                "case_id": data.get("simulation_id"),
                "artifact_id": data.get("simulation_id"),
                "pass_results": [
                    {
                        "pass_type": str(data.get("targeted_effect", {}).get("target_component") or "operationalization"),
                        "schema_validation": {"status": "passed" if data.get("simulation_status") == "passed" else "failed"},
                    }
                ],
                "failure_flags": {
                    "structural_failure": (data.get("candidate_summary") or {}).get("structural_score", 1.0) < 0.6,
                    "inconsistent_grounding": bool((data.get("deltas") or {}).get("grounding_score_delta", 0) < 0),
                    "no_decisions_extracted": False,
                    "duplicate_decisions": False,
                },
                "promotion_recommendation": data.get("promotion_recommendation", "hold"),
                "gating_decision_reason": "derived_from_operationalization",
                "confidence": "high" if data.get("simulation_status") == "passed" else "medium",
                "downstream_failure": not bool((data.get("regression_check") or {}).get("overall_pass", False)),
                "structural_score": (data.get("candidate_summary") or {}).get("structural_score"),
                "adversarial_type": None,
                "expected_difficulty": None,
            }
            case_records.append(rec)

    return [enrich_failure_first_flags(rec) for rec in case_records]


def build_failure_first_report(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    metrics = compute_failure_first_metrics(cases)
    promote_count = sum(1 for c in cases if str(c.get("promotion_recommendation") or c.get("gate_result") or "hold").lower() == "promote")
    hold_count = sum(1 for c in cases if str(c.get("promotion_recommendation") or c.get("gate_result") or "hold").lower() == "hold")
    reject_count = sum(1 for c in cases if str(c.get("promotion_recommendation") or c.get("gate_result") or "hold").lower() == "reject")

    structural_scores = [float(c["structural_score"]) for c in cases if c.get("structural_score") is not None]
    bins = {"lt_0_6": 0, "0_6_to_0_8": 0, "ge_0_8": 0}
    for score in structural_scores:
        if score < 0.6:
            bins["lt_0_6"] += 1
        elif score < 0.8:
            bins["0_6_to_0_8"] += 1
        else:
            bins["ge_0_8"] += 1

    false_confidence = [
        c for c in cases if c.get("high_confidence_error")
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "executive_failure_summary": {
            "total_cases": metrics["total_cases"],
            "promote_count": promote_count,
            "hold_count": hold_count,
            "reject_count": reject_count,
            "dangerous_promotes": metrics["dangerous_promote_count"],
            "high_confidence_errors": sum(1 for c in cases if c.get("high_confidence_error")),
        },
        "failure_first_metrics": metrics,
        "worst_cases": rank_worst_cases(cases, limit=5),
        "top_failure_modes": rank_failure_modes(cases, limit=10),
        "passes_components_most_at_risk": rank_pass_weaknesses(cases, limit=10),
        "false_confidence_zones": false_confidence,
        "dangerous_promotes": rank_dangerous_promotes(cases, limit=10),
        "structural_health": {
            "distribution": bins,
            "structural_failure_count": sum(
                1 for c in cases if (c.get("failure_flags") or {}).get("structural_failure")
            ),
            "scores_observed": len(structural_scores),
        },
    }


def _persist_archive(report: Dict[str, Any], report_dir: Path) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = report_dir / f"failure_first_report_{stamp}.json"
    # Never overwrite silently: increment suffix when a same-second collision happens.
    suffix = 1
    while target.exists():
        target = report_dir / f"failure_first_report_{stamp}_{suffix}.json"
        suffix += 1
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return target


def _print_output_summary(report: Dict[str, Any]) -> None:
    metrics = report["failure_first_metrics"]
    print(f"dangerous_promote_count: {metrics['dangerous_promote_count']}")
    high_conf_count = report["executive_failure_summary"]["high_confidence_errors"]
    print(f"high_confidence_error_count: {high_conf_count}")
    print("top 3 failure modes:")
    for mode in report["top_failure_modes"][:3]:
        print(f"- {mode['failure_mode']}: {mode['count']}")
    print("top 3 worst cases:")
    for case in report["worst_cases"][:3]:
        print(f"- {case.get('case_id') or case.get('artifact_id')}: {case.get('gating_decision_reason', 'n/a')}")
    print("top 3 weakest components:")
    for comp in report["passes_components_most_at_risk"][:3]:
        print(f"- {comp['pass_type']}: {comp['failure_count']}")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate failure-first observability report.")
    parser.add_argument("--observability-dir", default=str(_REPO_ROOT / "data" / "observability"))
    parser.add_argument("--output", default=str(_DEFAULT_JSON_OUTPUT))
    parser.add_argument("--no-adversarial", action="store_true")
    parser.add_argument("--no-operationalization", action="store_true")
    args = parser.parse_args(argv)

    cases = _collect_case_records(
        observability_dir=Path(args.observability_dir),
        include_adversarial=not args.no_adversarial,
        include_operationalization=not args.no_operationalization,
    )
    report = build_failure_first_report(cases)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    archive_path = _persist_archive(report, _REPORT_ARCHIVE_DIR)

    _print_output_summary(report)
    print(f"failure_first_report_path: {output_path}")
    print(f"archived_report_path: {archive_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
