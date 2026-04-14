#!/usr/bin/env python3
"""Run deterministic historical pytest exposure backtest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.historical_pytest_exposure_backtest import (  # noqa: E402
    run_historical_pytest_exposure_backtest,
    scan_historical_preflight_artifacts,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic historical pytest exposure backtest.")
    parser.add_argument("--scan-root", action="append", default=[], help="Scan root (repeatable). Defaults to outputs/artifacts/data.")
    parser.add_argument("--max-items", type=int, default=200, help="Maximum preflight artifacts to evaluate.")
    parser.add_argument("--window-label", default="historical_local_scan", help="Audit window label.")
    parser.add_argument("--output-dir", default="outputs/historical_pytest_exposure_backtest", help="Output directory.")
    parser.add_argument("--report-path", default="docs/reviews/BXT-01_historical_pytest_exposure_backtest.md", help="Human-readable report path.")
    return parser.parse_args()


def _render_report(result: dict, *, report_path: Path) -> None:
    lines: list[str] = []
    lines.append("# BXT-01 Historical Pytest Exposure Backtest")
    lines.append("")
    lines.append("## Analyzed period")
    lines.append(f"- Window label: `{result['audit_window'].get('window_label', 'unknown')}`")
    lines.append(f"- Generated at: `{result['generated_at']}`")
    lines.append("")
    lines.append("## Evidence available")
    for root in result["audit_window"].get("scan_roots", []):
        lines.append(f"- Scan root: `{root}`")
    lines.append(f"- Evaluated items: `{result['evaluated_items']}`")
    lines.append("")
    lines.append("## What may have slipped through")
    if result["suspect_items"]:
        for item in result["classifications"]:
            if item["classification"] == "trustworthy":
                continue
            lines.append(f"- `{item['identifier']}` → `{item['classification']}` ({item['confidence']})")
            for reason in item["reasons"]:
                lines.append(f"  - reason: `{reason}`")
    else:
        lines.append("- No suspect items found in scanned evidence.")
    lines.append("")
    lines.append("## Confidence limits")
    lines.append("- This backtest only evaluates artifacts discovered in the configured local scan roots.")
    lines.append("- Missing artifacts are represented as uncertainty and explicit suspect classifications.")
    lines.append("")
    lines.append("## Operator follow-up")
    if result["final_decision"] == "PASS":
        lines.append("- No immediate operator follow-up required.")
    else:
        lines.append("- Operator follow-up is required for suspect classifications before claiming historical trust cleanliness.")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = _parse_args()
    scan_root_raw = args.scan_root or ["outputs", "artifacts", "data"]
    roots = [Path(root) if Path(root).is_absolute() else (REPO_ROOT / root) for root in scan_root_raw]
    scanned = scan_historical_preflight_artifacts(roots, max_items=args.max_items)
    evidence_sources = {
        "audit_window": {
            "window_label": args.window_label,
            "scan_roots": [str(path) for path in roots],
            "artifact_globs": ["**/contract_preflight_result_artifact.json"],
            "max_items": args.max_items,
        },
        "source_type": "repo_local_artifacts",
        "evidence_priority": ["governed_artifacts", "workflow_evidence", "local_repo_evidence"],
    }
    result = run_historical_pytest_exposure_backtest(evidence_sources=evidence_sources, evaluated_items=scanned)

    output_dir = Path(args.output_dir) if Path(args.output_dir).is_absolute() else (REPO_ROOT / args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "historical_pytest_exposure_backtest_result.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report_path = Path(args.report_path) if Path(args.report_path).is_absolute() else (REPO_ROOT / args.report_path)
    _render_report(result, report_path=report_path)

    print(
        json.dumps(
            {
                "result_path": str(result_path),
                "report_path": str(report_path),
                "evaluated_items": result["evaluated_items"],
                "suspect_items": len(result["suspect_items"]),
                "final_decision": result["final_decision"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
