#!/usr/bin/env python3
"""CLI for the TI Enforcement Layer (Prompt 11B).

Evaluates a pipeline artifact against a named enforcement policy and
determines whether the stage may proceed, must warn, or must fail.

Exit codes
----------
0   allow
1   allow_with_warning
2   fail
3   malformed input / schema / execution error

Usage
-----
    python scripts/run_slo_enforcement.py <artifact.json> [--policy POLICY] [--stage STAGE]

Examples
--------
    # Default (permissive) policy
    python scripts/run_slo_enforcement.py outputs/slo_evaluation.json

    # Explicit decision_grade policy
    python scripts/run_slo_enforcement.py outputs/slo_evaluation.json --policy decision_grade

    # Stage-driven policy (synthesis stage uses decision_grade by default)
    python scripts/run_slo_enforcement.py outputs/slo_evaluation.json --stage synthesis

    # Write output to a custom path
    python scripts/run_slo_enforcement.py outputs/slo_evaluation.json --output /tmp/decision.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.slo_enforcement import (  # noqa: E402
    CONTRACT_VERSION,
    DECISION_ALLOW,
    DECISION_ALLOW_WITH_WARNING,
    DECISION_FAIL,
    KNOWN_POLICIES,
    STAGE_DEFAULT_POLICIES,
    run_slo_enforcement,
)

# ---------------------------------------------------------------------------
# Exit code constants
# ---------------------------------------------------------------------------

EXIT_ALLOW: int = 0
EXIT_ALLOW_WITH_WARNING: int = 1
EXIT_FAIL: int = 2
EXIT_ERROR: int = 3

_OUTPUT_DIR = _REPO_ROOT / "outputs"
_DEFAULT_OUTPUT_FILENAME = "slo_enforcement_decision.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_artifact(path: Path) -> Any:
    """Load JSON artifact from *path*; return the parsed value."""
    return json.loads(path.read_text(encoding="utf-8"))


def _write_decision(decision: Dict[str, Any], output_path: Path) -> None:
    """Write *decision* as formatted JSON to *output_path*."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(decision, indent=2), encoding="utf-8")


def _print_summary(result: Dict[str, Any]) -> None:
    """Print a human-readable summary of the enforcement result to stdout."""
    d = result.get("enforcement_decision") or {}
    status = result.get("decision_status", "(unknown)")
    reason = result.get("decision_reason_code", "(unknown)")
    policy = d.get("enforcement_policy", "(unknown)")
    ti = d.get("traceability_integrity_sli")
    ti_str = f"{ti:.1f}" if ti is not None else "None"
    scope = d.get("enforcement_scope", "")
    action = d.get("recommended_action", "(unknown)")

    print("=" * 60)
    print("SLO Enforcement Decision")
    print("=" * 60)
    print(f"  policy           : {policy}")
    if scope:
        print(f"  stage            : {scope}")
    print(f"  decision_status  : {status}")
    print(f"  reason_code      : {reason}")
    print(f"  TI (sli)         : {ti_str}")
    print(f"  recommended      : {action}")

    warnings: List[str] = result.get("warnings") or []
    if warnings:
        print("  warnings:")
        for w in warnings:
            print(f"    - {w}")

    errors: List[str] = result.get("errors") or []
    if errors:
        print("  errors:", file=sys.stderr)
        for e in errors:
            print(f"    - {e}", file=sys.stderr)

    schema_errors: List[str] = result.get("schema_errors") or []
    if schema_errors:
        print("  schema_errors:", file=sys.stderr)
        for se in schema_errors:
            print(f"    - {se}", file=sys.stderr)

    decision_id = d.get("decision_id", "(unknown)")
    print(f"  decision_id      : {decision_id}")
    print("=" * 60)


def _decision_exit_code(status: str, has_schema_errors: bool) -> int:
    """Map a decision status to a CLI exit code."""
    if has_schema_errors:
        return EXIT_ERROR
    if status == DECISION_ALLOW:
        return EXIT_ALLOW
    if status == DECISION_ALLOW_WITH_WARNING:
        return EXIT_ALLOW_WITH_WARNING
    if status == DECISION_FAIL:
        return EXIT_FAIL
    return EXIT_ERROR


# ---------------------------------------------------------------------------
# CLI main
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point for the SLO enforcement CLI.

    Returns the exit code (0/1/2/3).
    """
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate a pipeline artifact against a named enforcement policy "
            "and determine whether the stage may proceed."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "artifact_path",
        help="Path to the input artifact JSON file to evaluate.",
    )
    parser.add_argument(
        "--policy",
        choices=sorted(KNOWN_POLICIES),
        default=None,
        help=(
            "Enforcement policy profile to apply. "
            "Defaults to the stage default (if --stage is provided) "
            "or 'permissive' otherwise."
        ),
    )
    parser.add_argument(
        "--stage",
        choices=sorted(STAGE_DEFAULT_POLICIES.keys()),
        default=None,
        help=(
            "Pipeline stage identifier. Sets the default policy for the stage "
            "if --policy is not explicitly provided."
        ),
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            f"Path to write the decision artifact JSON. "
            f"Defaults to outputs/{_DEFAULT_OUTPUT_FILENAME}."
        ),
    )

    args = parser.parse_args(argv)

    # Load artifact
    artifact_path = Path(args.artifact_path)
    if not artifact_path.exists():
        print(f"ERROR: artifact path not found: {artifact_path}", file=sys.stderr)
        return EXIT_ERROR

    try:
        raw_input = _load_artifact(artifact_path)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: failed to load artifact JSON: {exc}", file=sys.stderr)
        return EXIT_ERROR

    # Run enforcement
    result = run_slo_enforcement(
        raw_input=raw_input,
        policy=args.policy,
        stage=args.stage,
    )

    # Print summary
    _print_summary(result)

    # Write decision artifact
    output_path = Path(args.output) if args.output else _OUTPUT_DIR / _DEFAULT_OUTPUT_FILENAME
    try:
        _write_decision(result["enforcement_decision"], output_path)
        print(f"  output_path      : {output_path}")
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: failed to write decision artifact: {exc}", file=sys.stderr)
        return EXIT_ERROR

    schema_errors: List[str] = result.get("schema_errors") or []
    return _decision_exit_code(result["decision_status"], bool(schema_errors))


if __name__ == "__main__":
    raise SystemExit(main())
