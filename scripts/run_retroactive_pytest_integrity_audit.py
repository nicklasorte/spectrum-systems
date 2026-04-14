#!/usr/bin/env python3
"""Run deterministic retroactive PYX-01 pytest integrity backtest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.retroactive_pytest_integrity_audit import (  # noqa: E402
    RetroactivePytestIntegrityAuditError,
    run_retroactive_pytest_integrity_audit,
    scan_historical_preflight_artifacts,
)


DEFAULT_SCAN_ROOTS = ["outputs", "artifacts", "data"]
DEFAULT_OUTPUT_DIR = "outputs/retroactive_pytest_integrity_audit"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run retroactive pytest integrity audit against local governed artifacts.")
    parser.add_argument(
        "--scan-root",
        action="append",
        default=[],
        help="Optional scan roots (repeatable). Defaults to repo-known roots: outputs, artifacts, data.",
    )
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Output directory for audit artifacts.")
    parser.add_argument("--remediation-queue-limit", type=int, default=50, help="Maximum remediation items to emit.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    scan_roots_raw = args.scan_root or DEFAULT_SCAN_ROOTS
    scan_roots = [
        (REPO_ROOT / root).resolve() if not Path(root).is_absolute() else Path(root)
        for root in scan_roots_raw
    ]

    scanned_artifacts = scan_historical_preflight_artifacts(scan_roots)
    audit_scope = {
        "roots": [str(path) for path in scan_roots],
        "artifact_globs": ["**/contract_preflight_result_artifact.json", "**/contract_preflight_report.json"],
        "repo_root": str(REPO_ROOT),
    }

    result, queue = run_retroactive_pytest_integrity_audit(
        scanned_artifacts=scanned_artifacts,
        audit_scope=audit_scope,
        remediation_queue_limit=args.remediation_queue_limit,
    )

    output_dir = (REPO_ROOT / args.output_dir).resolve() if not Path(args.output_dir).is_absolute() else Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    result_path = output_dir / "retroactive_pytest_integrity_audit_result.json"
    queue_path = output_dir / "retroactive_pytest_remediation_queue.json"

    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    queue_path.write_text(json.dumps(queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "result_path": str(result_path),
                "queue_path": str(queue_path),
                "scanned_run_count": result["scanned_run_count"],
                "suspect_count": result["suspect_count"],
                "unable_to_evaluate_count": result["unable_to_evaluate_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RetroactivePytestIntegrityAuditError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
