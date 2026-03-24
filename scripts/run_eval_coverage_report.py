#!/usr/bin/env python3
"""Compute governed eval coverage + slice summaries and emit report artifacts."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.contracts import load_schema  # noqa: E402

_DEFAULT_POLICY_PATH = _REPO_ROOT / "data" / "policy" / "eval_coverage_policy.json"
_DEFAULT_OUTPUT_DIR = _REPO_ROOT / "outputs" / "eval_coverage"

_RISK_WEIGHTS = {
    "critical": 1.0,
    "high": 0.75,
    "medium": 0.5,
    "low": 0.25,
}
_ALLOWED_RISK = set(_RISK_WEIGHTS.keys())
_ALLOWED_PRIORITY = {"p0", "p1", "p2", "p3"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _load_json_many(path: Path) -> list[dict[str, Any]]:
    payload = _load_json(path)
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        if not all(isinstance(item, dict) for item in payload):
            raise ValueError(f"{path}: expected list of JSON objects")
        return payload
    raise ValueError(f"{path}: expected JSON object or array")


def _validate(instance: dict[str, Any], schema_name: str) -> None:
    schema = load_schema(schema_name)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(instance)


def _normalize_slice_tags(case: dict[str, Any]) -> list[str]:
    candidates = case.get("slice_tags") or case.get("domain_tags")
    if not isinstance(candidates, list):
        return []
    values = [str(item).strip() for item in candidates if str(item).strip()]
    deduped = sorted(set(values))
    return deduped


def _normalize_risk_class(case: dict[str, Any]) -> str:
    risk = str(case.get("risk_class", "medium")).strip().lower()
    return risk if risk in _ALLOWED_RISK else "medium"


def _normalize_priority(case: dict[str, Any]) -> str:
    priority = str(case.get("priority", "p2")).strip().lower()
    return priority if priority in _ALLOWED_PRIORITY else "p2"


def _validate_policy(policy: dict[str, Any]) -> None:
    required_keys = {
        "required_slices",
        "optional_slices",
        "minimum_cases_per_required_slice",
        "minimum_pass_rate_by_risk_class",
        "indeterminate_counts_as_failure",
        "gap_severity_mapping",
    }
    missing = [key for key in required_keys if key not in policy]
    if missing:
        raise ValueError(f"coverage policy missing required keys: {missing}")

    if not isinstance(policy["required_slices"], list):
        raise ValueError("required_slices must be an array")

    for item in policy["required_slices"]:
        if not isinstance(item, dict):
            raise ValueError("required_slices entries must be objects")
        if not item.get("slice_id") or not item.get("slice_name"):
            raise ValueError("required_slices entries require slice_id and slice_name")


def _build_required_slice_index(policy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in policy.get("required_slices", []):
        slice_id = str(item["slice_id"]).strip()
        risk_class = str(item.get("risk_class", "medium")).strip().lower()
        index[slice_id] = {
            "slice_id": slice_id,
            "slice_name": str(item.get("slice_name", slice_id)),
            "risk_class": risk_class if risk_class in _ALLOWED_RISK else "medium",
            "priority": _normalize_priority(item),
            "weight": float(item.get("weight", _RISK_WEIGHTS.get(risk_class, 0.5))),
        }
    return index


def _risk_threshold(policy: dict[str, Any], risk_class: str) -> float:
    table = policy.get("minimum_pass_rate_by_risk_class", {})
    raw = table.get(risk_class, table.get("medium", 0.0))
    return max(0.0, min(1.0, float(raw)))


def _calculate_slice_status(*, total_cases: int, failure_rate: float, pass_rate: float, min_pass_rate: float) -> str:
    if total_cases == 0:
        return "blocked"
    if failure_rate >= 0.5:
        return "exhausted"
    if pass_rate < min_pass_rate:
        return "warning"
    return "healthy"


def _to_rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 6)


def _build_markdown_report(
    *,
    coverage: dict[str, Any],
    slices: list[dict[str, Any]],
    required_slice_index: dict[str, dict[str, Any]],
) -> str:
    covered_required = len(set(required_slice_index).intersection(set(coverage["covered_slices"])))
    total_required = len(required_slice_index)
    aggregate_pass = _to_rate(sum(s["pass_count"] for s in slices), sum(s["total_cases"] for s in slices))

    top_failing = sorted(
        [s for s in slices if s["total_cases"] > 0],
        key=lambda s: (-s["failure_rate"], s["slice_id"]),
    )[:5]

    lines = [
        "# Eval Coverage + Slice Summary",
        "",
        "This report is deterministic and repo-native. Aggregate pass rate alone is insufficient; slice-level risk can hide concentrated failures.",
        "",
        "## Coverage Overview",
        f"- Coverage run id: `{coverage['coverage_run_id']}`",
        f"- Timestamp: `{coverage['timestamp']}`",
        f"- Total eval cases: **{coverage['total_eval_cases']}**",
        f"- Required slices covered: **{covered_required}/{total_required}**",
        f"- Uncovered required slices: **{len(coverage['uncovered_required_slices'])}**",
        f"- Aggregate pass rate: **{aggregate_pass:.3f}**",
        f"- Risk-weighted coverage score: **{coverage['risk_weighted_coverage_score']:.3f}**",
        "",
        "## Required Slice Gaps",
    ]

    if coverage["coverage_gaps"]:
        for gap in coverage["coverage_gaps"]:
            lines.append(
                f"- `{gap['slice_id']}` ({gap['severity']}): {gap['reason']}"
            )
    else:
        lines.append("- None")

    lines.extend(["", "## Per-Slice Breakdown", "", "| Slice | Risk | Cases | Pass | Fail | Indeterminate | Pass Rate | Status |", "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |"])

    for item in sorted(slices, key=lambda s: (s["slice_id"])):
        lines.append(
            f"| {item['slice_id']} | {item['risk_class']} | {item['total_cases']} | {item['pass_count']} | {item['fail_count']} | {item['indeterminate_count']} | {item['pass_rate']:.3f} | {item['status']} |"
        )

    lines.extend(["", "## Top Failing Slices", ""])
    if top_failing:
        for item in top_failing:
            lines.append(
                f"- `{item['slice_id']}` failure_rate={item['failure_rate']:.3f} (fail={item['fail_count']}, indeterminate={item['indeterminate_count']})"
            )
    else:
        lines.append("- None")

    lines.extend(["", "## Zero-Case Slices", ""])
    zero_case = [s for s in slices if s["total_cases"] == 0]
    if zero_case:
        for item in zero_case:
            lines.append(f"- `{item['slice_id']}` ({item['slice_name']})")
    else:
        lines.append("- None")

    lines.append("")
    return "\n".join(lines)


def build_eval_coverage(
    *,
    eval_cases: list[dict[str, Any]],
    eval_results: list[dict[str, Any]],
    datasets: list[dict[str, Any]],
    policy: dict[str, Any],
    coverage_run_id: str,
    timestamp: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    _validate_policy(policy)

    case_by_id: dict[str, dict[str, Any]] = {}
    for case in eval_cases:
        _validate(case, "eval_case")
        case_id = str(case["eval_case_id"])
        slice_tags = _normalize_slice_tags(case)
        if not slice_tags:
            raise ValueError(f"eval_case '{case_id}' has no slice_tags/domain_tags; coverage assignment is impossible")

        case_by_id[case_id] = {
            **case,
            "slice_tags": slice_tags,
            "risk_class": _normalize_risk_class(case),
            "priority": _normalize_priority(case),
        }

    statuses_by_case_id: dict[str, list[str]] = defaultdict(list)
    run_refs_by_case_id: dict[str, list[str]] = defaultdict(list)

    for result in eval_results:
        _validate(result, "eval_result")
        case_id = str(result["eval_case_id"])
        if case_id not in case_by_id:
            continue
        status = str(result.get("result_status", "indeterminate")).strip().lower()
        if status not in {"pass", "fail", "indeterminate"}:
            status = "indeterminate"
        statuses_by_case_id[case_id].append(status)
        run_refs_by_case_id[case_id].append(str(result.get("trace_id", "")))

    required_slice_index = _build_required_slice_index(policy)
    minimum_cases = int(policy.get("minimum_cases_per_required_slice", 1))
    indeterminate_is_failure = bool(policy.get("indeterminate_counts_as_failure", True))

    slice_acc: dict[str, dict[str, Any]] = {}

    def _ensure_slice(slice_id: str, *, slice_name: str | None = None, risk_class: str = "medium") -> dict[str, Any]:
        if slice_id not in slice_acc:
            name = slice_name or required_slice_index.get(slice_id, {}).get("slice_name", slice_id)
            rc = risk_class if risk_class in _ALLOWED_RISK else required_slice_index.get(slice_id, {}).get("risk_class", "medium")
            slice_acc[slice_id] = {
                "slice_id": slice_id,
                "slice_name": name,
                "risk_class": rc,
                "case_ids": set(),
                "pass_count": 0,
                "fail_count": 0,
                "indeterminate_count": 0,
                "latest_eval_run_refs": set(),
            }
        return slice_acc[slice_id]

    for case_id, case in case_by_id.items():
        case_statuses = statuses_by_case_id.get(case_id, ["indeterminate"])
        pass_hits = sum(1 for st in case_statuses if st == "pass")
        fail_hits = sum(1 for st in case_statuses if st == "fail")
        indeterminate_hits = sum(1 for st in case_statuses if st == "indeterminate")

        for slice_id in case["slice_tags"]:
            bucket = _ensure_slice(slice_id, risk_class=case["risk_class"])
            bucket["case_ids"].add(case_id)
            bucket["pass_count"] += pass_hits
            bucket["fail_count"] += fail_hits
            bucket["indeterminate_count"] += indeterminate_hits
            bucket["latest_eval_run_refs"].update(run_refs_by_case_id.get(case_id, []))

    # Ensure required and optional slices are represented even when zero-case.
    for slice_id, detail in required_slice_index.items():
        _ensure_slice(slice_id, slice_name=detail["slice_name"], risk_class=detail["risk_class"])
    for maybe_optional in policy.get("optional_slices", []):
        if isinstance(maybe_optional, dict):
            _ensure_slice(
                str(maybe_optional.get("slice_id", "")).strip(),
                slice_name=str(maybe_optional.get("slice_name", "")).strip() or None,
                risk_class=str(maybe_optional.get("risk_class", "medium")).strip().lower(),
            )
        else:
            opt_id = str(maybe_optional).strip()
            if opt_id:
                _ensure_slice(opt_id)

    gap_severity_map = policy.get("gap_severity_mapping", {})
    slice_summaries: list[dict[str, Any]] = []
    covered_slices: list[str] = []
    uncovered_required_slices: list[str] = []
    coverage_gaps: list[dict[str, Any]] = []
    slice_case_counts: dict[str, int] = {}

    weighted_actual = 0.0
    weighted_possible = 0.0

    for slice_id, bucket in sorted(slice_acc.items()):
        total_cases = len(bucket["case_ids"])
        counted_total = bucket["pass_count"] + bucket["fail_count"] + bucket["indeterminate_count"]
        effective_fail_count = bucket["fail_count"] + (bucket["indeterminate_count"] if indeterminate_is_failure else 0)

        pass_rate = _to_rate(bucket["pass_count"], counted_total)
        failure_rate = _to_rate(effective_fail_count, counted_total)

        risk_class = bucket["risk_class"]
        min_pass_rate = _risk_threshold(policy, risk_class)
        status = _calculate_slice_status(
            total_cases=total_cases,
            failure_rate=failure_rate,
            pass_rate=pass_rate,
            min_pass_rate=min_pass_rate,
        )

        slice_summary = {
            "artifact_type": "eval_slice_summary",
            "schema_version": "1.0.0",
            "coverage_run_id": coverage_run_id,
            "slice_id": slice_id,
            "slice_name": bucket["slice_name"],
            "total_cases": total_cases,
            "pass_count": bucket["pass_count"],
            "fail_count": bucket["fail_count"],
            "indeterminate_count": bucket["indeterminate_count"],
            "pass_rate": pass_rate,
            "failure_rate": failure_rate,
            "latest_eval_run_refs": sorted(ref for ref in bucket["latest_eval_run_refs"] if ref),
            "risk_class": risk_class,
            "priority": required_slice_index.get(slice_id, {}).get("priority", "p2"),
            "status": status,
        }
        _validate(slice_summary, "eval_slice_summary")
        slice_summaries.append(slice_summary)

        slice_case_counts[slice_id] = total_cases
        if total_cases > 0:
            covered_slices.append(slice_id)

        if slice_id in required_slice_index:
            weight = float(required_slice_index[slice_id].get("weight", _RISK_WEIGHTS.get(risk_class, 0.5)))
            weighted_possible += weight
            weighted_actual += weight if total_cases >= minimum_cases else 0.0

            if total_cases == 0:
                uncovered_required_slices.append(slice_id)
                coverage_gaps.append(
                    {
                        "slice_id": slice_id,
                        "severity": str(gap_severity_map.get("zero_cases", "high")),
                        "reason": "required slice has zero eval cases",
                    }
                )
            elif total_cases < minimum_cases:
                uncovered_required_slices.append(slice_id)
                coverage_gaps.append(
                    {
                        "slice_id": slice_id,
                        "severity": str(gap_severity_map.get("below_min_cases", "medium")),
                        "reason": f"required slice has {total_cases} cases; minimum is {minimum_cases}",
                    }
                )

            if pass_rate < min_pass_rate:
                coverage_gaps.append(
                    {
                        "slice_id": slice_id,
                        "severity": str(gap_severity_map.get("below_pass_rate", "medium")),
                        "reason": f"required slice pass_rate {pass_rate:.3f} below minimum {min_pass_rate:.3f}",
                    }
                )

    for slice_id in sorted(required_slice_index):
        if slice_id not in slice_acc:
            uncovered_required_slices.append(slice_id)
            coverage_gaps.append(
                {
                    "slice_id": slice_id,
                    "severity": str(gap_severity_map.get("missing_required_slice", "critical")),
                    "reason": "required slice missing from coverage computation",
                }
            )

    dataset_refs = [
        f"{ds.get('dataset_id', 'unknown')}@{ds.get('dataset_version', 'unknown')}"
        for ds in datasets
    ]

    coverage_summary = {
        "artifact_type": "eval_coverage_summary",
        "schema_version": "1.0.0",
        "coverage_run_id": coverage_run_id,
        "timestamp": timestamp,
        "dataset_refs": sorted(dataset_refs),
        "total_eval_cases": len(case_by_id),
        "covered_slices": sorted(set(covered_slices)),
        "uncovered_required_slices": sorted(set(uncovered_required_slices)),
        "slice_case_counts": {k: slice_case_counts[k] for k in sorted(slice_case_counts)},
        "risk_weighted_coverage_score": _to_rate(int(round(weighted_actual * 1000000)), int(round(weighted_possible * 1000000)))
        if weighted_possible > 0
        else 0.0,
        "coverage_gaps": sorted(
            coverage_gaps,
            key=lambda g: (g["slice_id"], g["severity"], g["reason"]),
        ),
    }
    _validate(coverage_summary, "eval_coverage_summary")

    report = _build_markdown_report(
        coverage=coverage_summary,
        slices=slice_summaries,
        required_slice_index=required_slice_index,
    )
    return coverage_summary, slice_summaries, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compute eval coverage + slice summaries from governed eval artifacts")
    parser.add_argument("--eval-cases", default="contracts/examples/eval_case.json")
    parser.add_argument("--eval-results", default="contracts/examples/eval_result.json")
    parser.add_argument("--dataset", action="append", default=[], help="Path to eval_dataset artifact (repeatable)")
    parser.add_argument("--policy", default=str(_DEFAULT_POLICY_PATH))
    parser.add_argument("--output-dir", default=str(_DEFAULT_OUTPUT_DIR))
    parser.add_argument("--coverage-run-id", default="")
    parser.add_argument("--blocking-on-gaps", action="store_true", help="Return non-zero when required slice gaps exist")
    args = parser.parse_args(argv)

    coverage_run_id = args.coverage_run_id.strip() or f"coverage-{uuid.uuid4()}"
    timestamp = _utc_now()

    eval_cases = _load_json_many(Path(args.eval_cases))
    eval_results = _load_json_many(Path(args.eval_results))
    datasets = [_load_json(Path(path)) for path in args.dataset]
    for dataset in datasets:
        _validate(dataset, "eval_dataset")

    policy = _load_json(Path(args.policy))

    coverage, slices, markdown = build_eval_coverage(
        eval_cases=eval_cases,
        eval_results=eval_results,
        datasets=datasets,
        policy=policy,
        coverage_run_id=coverage_run_id,
        timestamp=timestamp,
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    _write_json(output_dir / "eval_coverage_summary.json", coverage)
    _write_json(output_dir / "eval_slice_summaries.json", slices)
    _write_text(output_dir / "eval_coverage_report.md", markdown)

    print(f"eval_coverage_summary_path: {output_dir / 'eval_coverage_summary.json'}")
    print(f"eval_slice_summaries_path: {output_dir / 'eval_slice_summaries.json'}")
    print(f"eval_coverage_report_path: {output_dir / 'eval_coverage_report.md'}")

    if args.blocking_on_gaps and coverage["uncovered_required_slices"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
