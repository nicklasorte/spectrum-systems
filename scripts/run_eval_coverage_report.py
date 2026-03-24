#!/usr/bin/env python3
"""Compute governed eval coverage + slice summaries and emit report artifacts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.evaluation.eval_coverage_reporting import (  # noqa: E402
    build_eval_coverage,
    load_json,
    load_json_many,
    resolve_coverage_run_id,
    utc_now,
    validate_artifact,
    write_json,
    write_text,
)

_DEFAULT_POLICY_PATH = _REPO_ROOT / "data" / "policy" / "eval_coverage_policy.json"
_DEFAULT_OUTPUT_DIR = _REPO_ROOT / "outputs" / "eval_coverage"


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

    timestamp = utc_now()

    eval_cases = load_json_many(Path(args.eval_cases))
    eval_results = load_json_many(Path(args.eval_results))
    datasets = [load_json(Path(path)) for path in args.dataset]
    for dataset in datasets:
        validate_artifact(dataset, "eval_dataset")

    policy = load_json(Path(args.policy))
    coverage_run_id = resolve_coverage_run_id(
        explicit_coverage_run_id=args.coverage_run_id,
        eval_cases_path=args.eval_cases,
        eval_results_path=args.eval_results,
        dataset_paths=args.dataset,
        policy_path=args.policy,
        policy=policy,
    )

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

    write_json(output_dir / "eval_coverage_summary.json", coverage)
    write_json(output_dir / "eval_slice_summaries.json", slices)
    write_text(output_dir / "eval_coverage_report.md", markdown)

    print(f"eval_coverage_summary_path: {output_dir / 'eval_coverage_summary.json'}")
    print(f"eval_slice_summaries_path: {output_dir / 'eval_slice_summaries.json'}")
    print(f"eval_coverage_report_path: {output_dir / 'eval_coverage_report.md'}")

    if args.blocking_on_gaps and coverage["uncovered_required_slices"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
