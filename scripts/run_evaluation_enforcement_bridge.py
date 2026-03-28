#!/usr/bin/env python3
"""CLI for the BU — Governor Enforcement Bridge.

Ingests an evaluation_budget_decision artifact, translates it into an
enforceable evaluation_enforcement_action artifact, and emits that artifact.

Exit codes
----------
0   allow / warn    – workflow may proceed (action_type=allow or warn)
2   freeze / block  – workflow must halt; error state

Usage
-----
    python scripts/run_evaluation_enforcement_bridge.py \\
        --input path/to/evaluation_budget_decision.json \\
        [--output-dir path/to/output/] \\
        [--scope release|promotion|schema_change|prompt_change|pipeline_change] \\
        [--done-certification path/to/done_certification_record.json] \\
        [--override-authorization path/to/override_authorization.json]

Examples
--------
    python scripts/run_evaluation_enforcement_bridge.py \\
        --input outputs/evaluation_budget_governor/evaluation_budget_decision.json \\
        --output-dir outputs/evaluation_enforcement_bridge/

    python scripts/run_evaluation_enforcement_bridge.py \\
        --input outputs/evaluation_budget_governor/evaluation_budget_decision.json \\
        --scope promotion \\
        --override-authorization path/to/override_authorization.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.evaluation_enforcement_bridge import (  # noqa: E402
    EnforcementBridgeError,
    InvalidDecisionError,
    load_override_authorization,
    run_enforcement_bridge,
    validate_enforcement_action,
)

# ---------------------------------------------------------------------------
# Exit code constants
# ---------------------------------------------------------------------------

EXIT_ALLOW = 0
EXIT_BLOCKED = 2

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_DEFAULT_OUTPUT_DIR = _REPO_ROOT / "outputs" / "evaluation_enforcement_bridge"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_json(artifact: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(artifact, fh, indent=2)
    print(f"Written: {path}")


def _load_json_file(path: str, label: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        print(f"ERROR: {label} file not found: {path}", file=sys.stderr)
        sys.exit(EXIT_BLOCKED)
    try:
        with p.open(encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        print(f"ERROR: failed to parse {label} JSON: {exc}", file=sys.stderr)
        sys.exit(EXIT_BLOCKED)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point for the Governor Enforcement Bridge CLI.

    Returns the exit code (0=allow/warn, 2=blocked/failure).
    """
    parser = argparse.ArgumentParser(
        description=(
            "Ingest an evaluation_budget_decision artifact and emit a governed "
            "evaluation_enforcement_action artifact."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--input",
        required=True,
        metavar="PATH",
        help="Path to an evaluation_budget_decision JSON file.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        metavar="DIR",
        help=(
            f"Directory to write output artifacts. "
            f"Defaults to {_DEFAULT_OUTPUT_DIR}."
        ),
    )
    parser.add_argument(
        "--scope",
        default=None,
        metavar="SCOPE",
        choices=["promotion", "release", "schema_change", "prompt_change", "pipeline_change"],
        help=(
            "Enforcement scope for the action. "
            "One of: promotion, release, schema_change, prompt_change, pipeline_change. "
            "Defaults to 'release' when not provided."
        ),
    )
    parser.add_argument(
        "--override-authorization",
        default=None,
        metavar="PATH",
        help=(
            "Path to an evaluation_override_authorization JSON file. "
            "Reserved for override authorization artifacts. "
            "The artifact is fully validated and verified before use."
        ),
    )
    parser.add_argument(
        "--done-certification",
        default=None,
        metavar="PATH",
        help=(
            "Path to a done_certification_record JSON artifact. "
            "Optional at CLI parse time. Runtime enforcement is fail-closed for "
            "promotion scope: missing or invalid done certification causes a blocked outcome."
        ),
    )

    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir) if args.output_dir else _DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build context
    context: Dict[str, Any] = {}
    if args.scope:
        context["enforcement_scope"] = args.scope
    if args.done_certification:
        context["done_certification_path"] = args.done_certification
    if args.override_authorization:
        try:
            override_auth = load_override_authorization(args.override_authorization)
        except EnforcementBridgeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return EXIT_BLOCKED
        context["override_authorization"] = override_auth

    # --- Execute enforcement bridge ---
    try:
        action = run_enforcement_bridge(args.input, context=context or None)
    except InvalidDecisionError as exc:
        print(f"ERROR: invalid evaluation_budget_decision: {exc}", file=sys.stderr)
        return EXIT_BLOCKED
    except EnforcementBridgeError as exc:
        print(f"ERROR: enforcement bridge failure: {exc}", file=sys.stderr)
        return EXIT_BLOCKED
    except Exception as exc:  # noqa: BLE001
        print(
            f"ERROR: unexpected failure ({type(exc).__name__}): {exc}",
            file=sys.stderr,
        )
        return EXIT_BLOCKED

    # --- Write enforcement action artifact ---
    action_path = output_dir / "evaluation_enforcement_action.json"
    try:
        _write_json(action, action_path)
    except OSError as exc:
        print(
            f"ERROR: failed to write enforcement action to '{action_path}': {exc}",
            file=sys.stderr,
        )
        return EXIT_BLOCKED

    # --- Print console summary ---
    print(
        f"\nEvaluation Enforcement Action\n"
        f"  Action ID:          {action['action_id']}\n"
        f"  Decision ID:        {action['decision_id']}\n"
        f"  Summary ID:         {action['summary_id']}\n"
        f"  Status:             {action['status']}\n"
        f"  Action type:        {action['action_type']}\n"
        f"  Enforcement scope:  {action['enforcement_scope']}\n"
        f"  Allowed to proceed: {action['allowed_to_proceed']}\n"
        f"  Certification ref:  {action['certification_gate']['artifact_reference']}\n"
        f"  Certification dec:  {action['certification_gate']['certification_decision']}\n"
        f"  Certification stat: {action['certification_gate']['certification_status']}\n"
        f"  Created at:         {action['created_at']}"
    )
    if action["certification_gate"]["block_reason"]:
        print(f"  Certification block reason: {action['certification_gate']['block_reason']}")

    print("  Reasons:")
    for r in action["reasons"]:
        print(f"    - {r}")

    if action["required_human_actions"]:
        print("  Required human actions:")
        for a in action["required_human_actions"]:
            print(f"    - {a}")

    # --- Determine exit code ---
    action_type = action["action_type"]
    allowed_to_proceed = action["allowed_to_proceed"]

    if action_type in ("freeze", "block"):
        print(
            f"\nExit 2: workflow blocked (action_type={action_type})",
            file=sys.stderr,
        )
        return EXIT_BLOCKED

    if not allowed_to_proceed:
        print(
            "\nExit 2: workflow blocked (allowed_to_proceed=false catch-all, "
            f"action_type={action_type})",
            file=sys.stderr,
        )
        return EXIT_BLOCKED

    return EXIT_ALLOW


if __name__ == "__main__":
    sys.exit(main())
