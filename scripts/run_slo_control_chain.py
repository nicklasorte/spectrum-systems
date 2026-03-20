#!/usr/bin/env python3
"""CLI for the Control-Chain Orchestrator (BN.4).

**REQUIRED entry point for decision-grade operation.**

This script runs the full SLO control chain (evaluation → enforcement →
gating → control decision) and enforces that decision-bearing stages
(recommend, synthesis, export) cannot bypass gating.

Exit codes
----------
0   continue
1   continue_with_warning
2   blocked (halt)
3   execution / malformed error

CRITICAL:
    Exit code 2 (blocked/halt) is NEVER confused with exit code 3 (error).
    A halt always returns 2 regardless of schema errors.

Usage
-----
    python scripts/run_slo_control_chain.py <artifact.json> \\
        [--stage STAGE] [--policy POLICY] [--input-kind KIND]

Examples
--------
    # Gate an SLO evaluation artifact (auto-detect kind)
    python scripts/run_slo_control_chain.py outputs/slo_evaluation.json \\
        --stage synthesis

    # Gate an enforcement decision artifact
    python scripts/run_slo_control_chain.py outputs/slo_enforcement_decision.json

    # Audit mode with a gating decision artifact
    python scripts/run_slo_control_chain.py outputs/slo_gating_decision.json \\
        --input-kind gating

    # Override policy
    python scripts/run_slo_control_chain.py outputs/slo_evaluation.json \\
        --stage recommend --policy decision_grade

    # Write to custom output path
    python scripts/run_slo_control_chain.py outputs/slo_evaluation.json \\
        --stage synthesis --output /tmp/cc_decision.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.control_chain import (  # noqa: E402
    INPUT_KIND_EVALUATION,
    INPUT_KIND_ENFORCEMENT,
    INPUT_KIND_GATING,
    KNOWN_INPUT_KINDS,
    REASON_CONTINUE,
    REASON_CONTINUE_WITH_WARNING,
    run_control_chain,
    summarize_control_chain_decision,
)
from spectrum_systems.modules.runtime.contract_runtime import (  # noqa: E402
    ContractRuntimeError,
    get_contract_runtime_status,
    format_contract_runtime_error,
)
from spectrum_systems.modules.runtime.control_signals import (  # noqa: E402
    explain_blocking_requirements,
    list_required_followups,
)
from spectrum_systems.modules.runtime.control_executor import (  # noqa: E402
    summarize_execution_result,
    explain_execution_path,
)
from spectrum_systems.modules.runtime.policy_registry import (  # noqa: E402
    KNOWN_POLICIES,
    KNOWN_STAGES,
)

# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------

EXIT_CONTINUE = 0
EXIT_CONTINUE_WITH_WARNING = 1
EXIT_BLOCKED = 2
EXIT_ERROR = 3

_OUTPUT_DIR = _REPO_ROOT / "outputs"
_DEFAULT_OUTPUT_FILENAME = "slo_control_chain_decision.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_artifact(path: Path) -> Any:
    """Load JSON from *path*."""
    return json.loads(path.read_text(encoding="utf-8"))


def _write_decision(decision: Dict[str, Any], output_path: Path) -> None:
    """Write the control-chain decision artifact as JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(decision, indent=2), encoding="utf-8")


def _outcome_exit_code(
    continuation_allowed: bool,
    primary_reason_code: str,
    has_schema_errors: bool,
) -> int:
    """Map continuation status to an exit code.

    Halt (blocked) takes precedence over schema errors: exit 2 is NEVER
    confused with exit 3.
    """
    if not continuation_allowed:
        return EXIT_BLOCKED
    # continuation is allowed — but may have warnings or schema errors
    if primary_reason_code == REASON_CONTINUE_WITH_WARNING:
        return EXIT_CONTINUE_WITH_WARNING
    if has_schema_errors:
        return EXIT_ERROR
    return EXIT_CONTINUE


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point for the SLO control-chain CLI.

    Returns the exit code (0/1/2/3).
    """
    parser = argparse.ArgumentParser(
        description=(
            "Run the full SLO control chain (evaluation → enforcement → gating). "
            "REQUIRED for decision-grade pipeline stages. "
            "Decision-bearing stages (recommend, synthesis, export) cannot bypass gating."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "artifact_path",
        nargs="?",
        default=None,
        help="Path to the input artifact JSON file (evaluation, enforcement, or gating).",
    )
    parser.add_argument(
        "--stage",
        choices=sorted(KNOWN_STAGES),
        default=None,
        help=(
            "Pipeline stage to gate against. "
            "When not provided, the stage is extracted from the artifact."
        ),
    )
    parser.add_argument(
        "--policy",
        choices=sorted(KNOWN_POLICIES),
        default=None,
        help=(
            "Enforcement policy override. "
            "When not provided, the stage-default policy is used."
        ),
    )
    parser.add_argument(
        "--input-kind",
        choices=sorted(KNOWN_INPUT_KINDS),
        default=None,
        dest="input_kind",
        help=(
            "Explicit input kind override. "
            "Auto-detected from artifact shape when not provided. "
            "Use this when auto-detection may be ambiguous."
        ),
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            f"Output path for the control-chain decision artifact. "
            f"Defaults to outputs/{_DEFAULT_OUTPUT_FILENAME}."
        ),
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Execute BN.6 control-signal consumption after deriving control signals "
            "and print a deterministic execution summary."
        ),
    )

    args = parser.parse_args(argv)

    # BN.6.1: Emit diagnostics line and fail closed if contract runtime is unavailable.
    runtime_status = get_contract_runtime_status()
    _rt_state = "available" if runtime_status["available"] else "unavailable"
    _rt_ver = f" (jsonschema {runtime_status['version']})" if runtime_status.get("version") else ""
    print(f"  contract runtime           : {_rt_state}{_rt_ver}")
    if not runtime_status["available"]:
        print(
            f"ERROR: {format_contract_runtime_error(runtime_status)}",
            file=sys.stderr,
        )
        return EXIT_ERROR

    if args.artifact_path is None:
        print(
            "ERROR: artifact_path is required.",
            file=sys.stderr,
        )
        parser.print_usage(sys.stderr)
        return EXIT_ERROR

    artifact_path = Path(args.artifact_path)
    if not artifact_path.exists():
        print(f"ERROR: artifact path not found: {artifact_path}", file=sys.stderr)
        return EXIT_ERROR

    try:
        raw_input = _load_artifact(artifact_path)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: failed to load artifact JSON: {exc}", file=sys.stderr)
        return EXIT_ERROR

    # Run control chain
    try:
        result = run_control_chain(
            raw_input,
            stage=args.stage,
            policy=args.policy,
            input_kind=args.input_kind,
            execute=args.execute,
        )
    except ContractRuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_ERROR

    # Print human-readable summary (includes BN.5 control signals)
    print(summarize_control_chain_decision(result))

    # Print blocking requirements when continuation is not allowed
    cd = result.get("control_chain_decision") or {}
    cs = cd.get("control_signals") or {}
    blocking_explanation = explain_blocking_requirements(cs)
    if blocking_explanation:
        print()
        print(blocking_explanation)

    followups = list_required_followups(cs)
    if followups:
        print()
        print("Required follow-up actions:")
        for f in followups:
            print(f"  - {f}")

    if args.execute:
        execution_result = result.get("execution_result") or {}
        print()
        print(summarize_execution_result(execution_result))
        print()
        print(
            json.dumps(
                explain_execution_path(cs, execution_result),
                indent=2,
            )
        )

    # Write control-chain decision artifact
    output_path = Path(args.output) if args.output else _OUTPUT_DIR / _DEFAULT_OUTPUT_FILENAME
    try:
        _write_decision(result["control_chain_decision"], output_path)
        print(f"  output_path              : {output_path}")
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: failed to write control-chain decision artifact: {exc}", file=sys.stderr)
        return EXIT_ERROR

    schema_errors: List[str] = result.get("schema_errors") or []
    exit_code = _outcome_exit_code(
        continuation_allowed=result["continuation_allowed"],
        primary_reason_code=result["primary_reason_code"],
        has_schema_errors=bool(schema_errors),
    )
    if exit_code == EXIT_ERROR:
        print(
            f"ERROR: control chain returned an execution/schema error "
            f"(reason: {result['primary_reason_code']}). "
            "Check the errors field in the artifact for details.",
            file=sys.stderr,
        )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
