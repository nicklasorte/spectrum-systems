#!/usr/bin/env python3
"""
Regression Check CLI — scripts/run_regression_check.py

Usage examples
--------------
Create a baseline from current eval and observability outputs:

    python scripts/run_regression_check.py \\
        --create-baseline my_baseline \\
        --from-eval outputs/eval_results.json \\
        --from-observability outputs/metrics_report.json

Compare a candidate run against a named baseline:

    python scripts/run_regression_check.py \\
        --baseline my_baseline \\
        --candidate current

With a specific policy:

    python scripts/run_regression_check.py \\
        --baseline my_baseline \\
        --candidate current \\
        --policy config/regression_policy.json

Filter to a specific case:

    python scripts/run_regression_check.py \\
        --baseline my_baseline \\
        --candidate current \\
        --case case_001

Exit codes
----------
0 = pass
1 = warnings only (use --strict-warnings to treat as hard fail)
2 = hard fail
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

# Ensure repo root on sys.path when invoked directly
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.regression.harness import (
    RegressionHarness,
    RegressionPolicy,
    eval_result_to_dict,
    observability_record_to_dict,
)
from spectrum_systems.modules.regression.baselines import (
    BaselineManager,
    BaselineExistsError,
    BaselineNotFoundError,
)


# ---------------------------------------------------------------------------
# Output path
# ---------------------------------------------------------------------------

_DEFAULT_OUTPUT = _REPO_ROOT / "outputs" / "regression_report.json"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    baselines_dir = Path(args.baselines_dir) if args.baselines_dir else None
    manager = BaselineManager(baselines_dir)

    # ------------------------------------------------------------------ #
    # CREATE BASELINE mode                                                 #
    # ------------------------------------------------------------------ #
    if args.create_baseline:
        return _handle_create_baseline(args, manager)

    # ------------------------------------------------------------------ #
    # COMPARE mode                                                         #
    # ------------------------------------------------------------------ #
    return _handle_compare(args, manager)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def _handle_create_baseline(args: argparse.Namespace, manager: BaselineManager) -> int:
    name = args.create_baseline

    eval_results: list[dict] = []
    obs_records: list[dict] = []

    if args.from_eval:
        eval_path = Path(args.from_eval)
        if not eval_path.exists():
            _err(f"Eval results file not found: {eval_path}")
            return 2
        raw = json.loads(eval_path.read_text(encoding="utf-8"))
        # Support both a list and a dict with a "results" key
        if isinstance(raw, list):
            eval_results = [eval_result_to_dict(r) for r in raw]
        elif isinstance(raw, dict) and "results" in raw:
            eval_results = [eval_result_to_dict(r) for r in raw["results"]]
        else:
            eval_results = [eval_result_to_dict(raw)]

    if args.from_observability:
        obs_path = Path(args.from_observability)
        if not obs_path.exists():
            _err(f"Observability file not found: {obs_path}")
            return 2
        raw = json.loads(obs_path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            obs_records = [observability_record_to_dict(r) for r in raw]
        elif isinstance(raw, dict) and "records" in raw:
            obs_records = [observability_record_to_dict(r) for r in raw["records"]]
        else:
            obs_records = [observability_record_to_dict(raw)]

    metadata: dict = {}
    if args.deterministic:
        metadata["deterministic_mode"] = True
    if args.notes:
        metadata["notes"] = args.notes

    try:
        baseline_dir = manager.save_baseline(
            name,
            eval_results,
            obs_records,
            metadata=metadata,
            update=args.update_baseline,
            notes=args.notes or "",
        )
        print(f"✓ Baseline '{name}' saved to {baseline_dir}")
        print(f"  eval_results   : {len(eval_results)} case(s)")
        print(f"  obs_records    : {len(obs_records)} record(s)")
        return 0
    except BaselineExistsError as exc:
        _err(str(exc))
        return 2
    except Exception as exc:
        _err(f"Failed to save baseline: {exc}")
        return 2


def _handle_compare(args: argparse.Namespace, manager: BaselineManager) -> int:
    if not args.baseline:
        _err("--baseline is required for comparison mode.")
        return 2

    candidate_id = args.candidate or "current"

    # Load policy
    policy_path = Path(args.policy) if args.policy else None
    try:
        policy = RegressionPolicy.load(policy_path)
    except Exception as exc:
        _err(f"Failed to load policy: {exc}")
        return 2

    # Load baseline
    try:
        baseline = manager.load_baseline(args.baseline)
    except BaselineNotFoundError as exc:
        _err(str(exc))
        return 2
    except Exception as exc:
        _err(f"Failed to load baseline '{args.baseline}': {exc}")
        return 2

    # Determinism mismatch warning
    if args.deterministic is not None:
        warning = manager.warn_if_determinism_mismatch(args.baseline, args.deterministic)
        if warning:
            print(f"⚠  {warning}", file=sys.stderr)

    baseline_eval = baseline["eval_results"]
    baseline_obs = baseline["observability_records"]

    # Load candidate eval results
    candidate_eval: list[dict] = []
    if args.from_eval:
        eval_path = Path(args.from_eval)
        if not eval_path.exists():
            _err(f"Eval results file not found: {eval_path}")
            return 2
        raw = json.loads(eval_path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            candidate_eval = [eval_result_to_dict(r) for r in raw]
        elif isinstance(raw, dict) and "results" in raw:
            candidate_eval = [eval_result_to_dict(r) for r in raw["results"]]
        else:
            candidate_eval = [eval_result_to_dict(raw)]

    # Load candidate observability records
    candidate_obs: list[dict] = []
    if args.from_observability:
        obs_path = Path(args.from_observability)
        if not obs_path.exists():
            _err(f"Observability file not found: {obs_path}")
            return 2
        raw = json.loads(obs_path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            candidate_obs = [observability_record_to_dict(r) for r in raw]
        elif isinstance(raw, dict) and "records" in raw:
            candidate_obs = [observability_record_to_dict(r) for r in raw["records"]]
        else:
            candidate_obs = [observability_record_to_dict(raw)]

    # Filter to a single case if requested
    if args.case:
        baseline_eval = [r for r in baseline_eval if r.get("case_id") == args.case]
        candidate_eval = [r for r in candidate_eval if r.get("case_id") == args.case]
        baseline_obs = [r for r in baseline_obs if r.get("case_id") == args.case]
        candidate_obs = [r for r in candidate_obs if r.get("case_id") == args.case]

    # Use baseline data as candidate if no candidate eval/obs provided
    # (comparison against self → always passes; useful for smoke testing)
    if not candidate_eval:
        candidate_eval = baseline_eval
    if not candidate_obs:
        candidate_obs = baseline_obs

    harness = RegressionHarness(policy=policy)
    eval_comparison = harness.compare_eval_runs(baseline_eval, candidate_eval)
    obs_comparison = harness.compare_observability_runs(baseline_obs, candidate_obs)

    report = harness.generate_report(
        baseline_id=args.baseline,
        candidate_id=candidate_id,
        eval_comparison=eval_comparison,
        observability_comparison=obs_comparison,
        candidate_deterministic=args.deterministic,
    )

    # Write report
    output_path = Path(args.output) if args.output else _DEFAULT_OUTPUT
    report.write(output_path)

    # Print console summary
    _print_summary(report.to_dict())

    # Validate against schema
    schema_errors = report.validate_against_schema()
    if schema_errors:
        print("\n⚠  Report schema validation errors:", file=sys.stderr)
        for e in schema_errors:
            print(f"   {e}", file=sys.stderr)

    # Exit code
    summary = report.to_dict()["summary"]
    if summary["hard_failures"] > 0:
        return 2
    if summary["warnings"] > 0 and args.strict_warnings:
        return 1
    if summary["warnings"] > 0:
        return 1
    return 0


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------


def _print_summary(report: dict) -> None:
    summary = report["summary"]
    sep = "─" * 60
    print(sep)
    status = "✓ PASS" if summary["overall_pass"] else "✗ FAIL"
    print(f"Regression Check: {status}")
    print(f"  Baseline     : {report['baseline_id']}")
    print(f"  Candidate    : {report['candidate_id']}")
    print(f"  Policy       : {report['policy_id']}")
    print(f"  Cases        : {summary['cases_compared']}")
    print(f"  Passes       : {summary['passes_compared']}")
    print(f"  Hard failures: {summary['hard_failures']}")
    print(f"  Warnings     : {summary['warnings']}")

    dim_results = report.get("dimension_results", {})
    if dim_results:
        print("\nDimension Results:")
        for dim, result in sorted(dim_results.items()):
            icon = "✓" if result["passed"] else ("✗" if result["severity"] == "hard_fail" else "⚠")
            insufficient = " [insufficient data]" if result.get("insufficient_data") else ""
            print(
                f"  {icon} {dim:<22} "
                f"baseline={result['baseline_value']:.4f}  "
                f"candidate={result['candidate_value']:.4f}  "
                f"delta={result['delta']:+.4f}{insufficient}"
            )

    worst = report.get("worst_regressions", [])
    if worst:
        print(f"\nWorst Regressions (top {min(len(worst), 5)}):")
        for entry in worst[:5]:
            parts = []
            if entry.get("case_id"):
                parts.append(f"case={entry['case_id']}")
            if entry.get("pass_type"):
                parts.append(f"pass={entry['pass_type']}")
            parts.append(f"dim={entry['dimension']}")
            parts.append(f"delta={entry['delta']:+.4f}")
            parts.append(f"[{entry['severity']}]")
            print(f"  • {' '.join(parts)}")

    recs = report.get("recommendations", [])
    if recs:
        print("\nRecommendations:")
        for rec in recs:
            print(f"  → {rec}")
    print(sep)


def _err(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Spectrum Systems Regression Harness CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Mode: create baseline
    p.add_argument(
        "--create-baseline",
        metavar="NAME",
        help="Create a named regression baseline from current outputs.",
    )
    p.add_argument(
        "--update-baseline",
        action="store_true",
        help="Allow overwriting an existing baseline (required with --create-baseline).",
    )

    # Mode: compare
    p.add_argument(
        "--baseline",
        metavar="NAME",
        help="Baseline name to compare against.",
    )
    p.add_argument(
        "--candidate",
        metavar="NAME",
        default="current",
        help="Candidate run identifier (default: 'current').",
    )
    p.add_argument(
        "--all-cases",
        action="store_true",
        help="Compare all cases in the baseline (default behaviour).",
    )
    p.add_argument(
        "--case",
        metavar="CASE_ID",
        help="Restrict comparison to a single case.",
    )
    p.add_argument(
        "--policy",
        metavar="PATH",
        help="Path to a regression policy JSON file.",
    )

    # Inputs
    p.add_argument(
        "--from-eval",
        metavar="PATH",
        help="Path to eval_results.json (list of EvalResult dicts).",
    )
    p.add_argument(
        "--from-observability",
        metavar="PATH",
        help="Path to observability metrics_report.json.",
    )

    # Output
    p.add_argument(
        "--output",
        metavar="PATH",
        default=str(_DEFAULT_OUTPUT),
        help=f"Output path for regression_report.json (default: {_DEFAULT_OUTPUT}).",
    )

    # Flags
    p.add_argument(
        "--deterministic",
        action="store_true",
        default=None,
        help="Declare that the candidate run was deterministic.",
    )
    p.add_argument(
        "--strict-warnings",
        action="store_true",
        help="Exit with code 1 if warnings are present (default: warnings exit 0).",
    )
    p.add_argument(
        "--notes",
        metavar="TEXT",
        default="",
        help="Human-readable notes to embed in baseline metadata.",
    )
    p.add_argument(
        "--baselines-dir",
        metavar="PATH",
        help="Override the baselines root directory.",
    )

    return p


if __name__ == "__main__":
    sys.exit(main())
