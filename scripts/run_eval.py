#!/usr/bin/env python3
"""
Evaluation CLI — scripts/run_eval.py

Runs the Evaluation Framework against golden test cases and produces a
structured JSON report.

Usage
-----
Run all cases:
    python scripts/run_eval.py --all

Run a single case:
    python scripts/run_eval.py --case CASE_ID

Options:
    --all               Run all golden cases
    --case CASE_ID      Run a single case by ID
    --config PATH       Path to eval_config.yaml (default: config/eval_config.yaml)
    --output PATH       Path for JSON report (default: outputs/eval_results.json)
    --update-baseline   Save current run results as the new baseline
    --no-deterministic  Disable deterministic mode (allows non-zero temperature)

Output
------
- Console summary printed to stdout
- JSON report written to outputs/eval_results.json (or --output path)

Exit codes
----------
0   All cases passed
1   One or more cases failed
2   Configuration or setup error
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Repo root discovery
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPTS_DIR.parent

# Ensure the repo root is on sys.path so spectrum_systems can be imported.
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# ---------------------------------------------------------------------------
# Imports (after path setup)
# ---------------------------------------------------------------------------

from spectrum_systems.modules.evaluation.golden_dataset import load_all_cases, load_case, GoldenCaseError  # noqa: E402
from spectrum_systems.modules.evaluation.eval_runner import EvalRunner, EvalResult  # noqa: E402
from spectrum_systems.modules.evaluation.grounding import GroundingVerifier  # noqa: E402
from spectrum_systems.modules.evaluation.regression import RegressionHarness, BaselineRecord  # noqa: E402
from spectrum_systems.modules.engines import DecisionExtractionAdapter  # noqa: E402


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def _load_config(config_path: Path) -> dict:
    """Load eval_config.yaml.  Returns an empty dict if the file is absent."""
    if not config_path.exists():
        return {}
    # Minimal YAML parsing without external deps: only handles simple key:value
    # and nested blocks.  For production, replace with a proper YAML library.
    try:
        import json as _json  # noqa: F401 (used below)
        # Try to import yaml; fall back to a minimal built-in loader
        try:
            import yaml  # type: ignore
            return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except ImportError:
            return _minimal_yaml_load(config_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] Could not load config from {config_path}: {exc}", file=sys.stderr)
        return {}


def _minimal_yaml_load(text: str) -> dict:
    """Extremely minimal YAML-to-dict loader for flat/nested configs without PyYAML."""
    result: dict = {}
    stack: list = [result]
    indent_stack: list = [0]

    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.strip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip())
        line = raw_line.strip()
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()

        # Pop stack to current indent level
        while len(indent_stack) > 1 and indent <= indent_stack[-2]:
            stack.pop()
            indent_stack.pop()

        current = stack[-1]
        if not isinstance(current, dict):
            continue

        if not value or value.startswith("#"):
            # Nested dict
            new_dict: dict = {}
            current[key] = new_dict
            stack.append(new_dict)
            indent_stack.append(indent)
        else:
            # Scalar value — rudimentary type coercion
            current[key] = _coerce(value.split("#")[0].strip())

    return result


def _coerce(value: str):
    """Coerce a YAML scalar string to a Python primitive."""
    if value.lower() in ("true", "yes"):
        return True
    if value.lower() in ("false", "no"):
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value.strip('"').strip("'")


# ---------------------------------------------------------------------------
# Stub reasoning engine
# ---------------------------------------------------------------------------

class _StubReasoningEngine:
    """Stub engine used when no real engine is configured.

    Returns a minimal pass chain record with empty outputs so the evaluation
    framework can be exercised without a live model.
    """

    def run(self, transcript: str, config: dict = None) -> dict:
        return {
            "chain_id": "stub-chain",
            "status": "completed",
            "pass_results": [],
            "intermediate_artifacts": {},
        }


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------

def _build_runner(cfg: dict, deterministic: bool, output_dir: Path, engine_mode: str = "stub") -> EvalRunner:
    """Construct an ``EvalRunner`` from loaded config."""
    thresholds = cfg.get("regression_thresholds", {})
    latency_budgets = cfg.get("latency_budgets", {})
    baselines_dir = _REPO_ROOT / cfg.get("paths", {}).get("baselines_dir", "data/eval_baselines")

    harness = RegressionHarness(
        baselines_dir=baselines_dir,
        thresholds={k: float(v) for k, v in thresholds.items()} if thresholds else None,
    )
    grounding_min = int(cfg.get("grounding_min_overlap_tokens", 1))
    grounding = GroundingVerifier(min_overlap_tokens=grounding_min)

    if engine_mode == "decision_real":
        engine: object = DecisionExtractionAdapter(include_action_items=True)
    else:
        engine = _StubReasoningEngine()

    return EvalRunner(
        reasoning_engine=engine,
        grounding_verifier=grounding,
        regression_harness=harness,
        latency_budgets={k: int(v) for k, v in latency_budgets.items()} if latency_budgets else None,
        deterministic=deterministic,
        output_dir=output_dir,
    )


def _print_summary(results: list, output_path: Path) -> None:
    """Print a human-readable summary to stdout."""
    total = len(results)
    passed = sum(1 for r in results if r.pass_fail)
    failed = total - passed

    print()
    print("=" * 60)
    print("  EVALUATION SUMMARY")
    print("=" * 60)
    print(f"  Total cases : {total}")
    print(f"  Passed      : {passed}")
    print(f"  Failed      : {failed}")
    if total > 0:
        print(f"  Pass rate   : {100 * passed / total:.1f}%")
    print()

    for r in results:
        status = "PASS" if r.pass_fail else "FAIL"
        print(
            f"  [{status}] {r.case_id:<20} "
            f"structural={r.structural_score:.2f}  "
            f"semantic={r.semantic_score:.2f}  "
            f"grounding={r.grounding_score:.2f}"
        )
        if r.error_types:
            for err in r.error_types[:3]:
                print(f"         ↳ {err.error_type.value}: {err.message[:80]}")
            if len(r.error_types) > 3:
                print(f"         ↳ … and {len(r.error_types) - 3} more errors")

    print()
    print(f"  Report written to: {output_path}")
    print("=" * 60)
    print()


def _update_baselines(results: list, harness: RegressionHarness) -> None:
    """Persist current results as new baselines."""
    from datetime import datetime, timezone
    for r in results:
        record = BaselineRecord(
            case_id=r.case_id,
            structural_score=r.structural_score,
            semantic_score=r.semantic_score,
            grounding_score=r.grounding_score,
            recorded_at=datetime.now(timezone.utc).isoformat(),
        )
        harness.save_baseline(record)
        print(f"  [baseline] Updated baseline for {r.case_id}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluation Framework CLI — run golden-case evaluations."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Run all golden cases")
    group.add_argument("--case", metavar="CASE_ID", help="Run a single case by ID")

    parser.add_argument(
        "--config",
        metavar="PATH",
        default=str(_REPO_ROOT / "config" / "eval_config.yaml"),
        help="Path to eval_config.yaml",
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        default=str(_REPO_ROOT / "outputs" / "eval_results.json"),
        help="Path for JSON report",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Save current run results as the new baseline",
    )
    parser.add_argument(
        "--no-deterministic",
        action="store_true",
        help="Disable deterministic mode",
    )
    parser.add_argument(
        "--engine-mode",
        choices=["stub", "decision_real"],
        default="stub",
        help=(
            "Reasoning engine to use.  "
            "'stub' (default): empty outputs, deterministic plumbing only.  "
            "'decision_real': narrow real-engine path using DecisionExtractionAdapter "
            "(deterministic pattern matching, no live model)."
        ),
    )

    args = parser.parse_args(argv)

    # Load config
    cfg = _load_config(Path(args.config))
    deterministic = not args.no_deterministic and cfg.get("deterministic", True)

    output_path = Path(args.output)
    output_dir = output_path.parent

    # Build runner
    try:
        runner = _build_runner(cfg, deterministic=deterministic, output_dir=output_dir, engine_mode=args.engine_mode)
    except Exception as exc:  # noqa: BLE001
        print(f"[error] Failed to build evaluation runner: {exc}", file=sys.stderr)
        return 2

    # Load cases
    golden_cases_dir = _REPO_ROOT / cfg.get("paths", {}).get("golden_cases_dir", "data/golden_cases")

    try:
        if args.all:
            from spectrum_systems.modules.evaluation.golden_dataset import load_all_cases
            dataset = load_all_cases(golden_cases_dir)
            if len(dataset) == 0:
                print("[warn] No golden cases found.", file=sys.stderr)
                return 0
            results = runner.run_all_cases(dataset)
        else:
            case = load_case(args.case, golden_cases_dir)
            results = [runner.run_case(case)]
    except GoldenCaseError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2

    # Write report
    report_path = runner.write_report(results, output_path=output_path)

    # Update baselines if requested
    if args.update_baseline:
        baselines_dir = _REPO_ROOT / cfg.get("paths", {}).get("baselines_dir", "data/eval_baselines")
        harness = RegressionHarness(baselines_dir=baselines_dir)
        _update_baselines(results, harness)

    # Print summary
    _print_summary(results, report_path)

    # Exit 1 if any case failed
    any_failed = any(not r.pass_fail for r in results)
    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
