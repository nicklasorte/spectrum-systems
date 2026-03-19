#!/usr/bin/env python3
"""Run BB+1 deterministic failure enforcement and persist governed decisions."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.observability.failure_enforcement import (  # noqa: E402
    evaluate_failure_controls,
)

_DEFAULT_OUTPUT_PATH = _REPO_ROOT / "outputs" / "failure_enforcement_decision.json"
_ARCHIVE_DIR = _REPO_ROOT / "data" / "failure_enforcement_decisions"
_SCHEMA_PATH = _REPO_ROOT / "contracts" / "schemas" / "failure_enforcement_decision.schema.json"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_failure_first_report() -> Path:
    output_report = _REPO_ROOT / "outputs" / "failure_first_report.json"
    if output_report.exists():
        return output_report

    archive_dir = _REPO_ROOT / "data" / "observability_reports"
    candidates = sorted(archive_dir.glob("failure_first_report*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if candidates:
        return candidates[0]

    raise FileNotFoundError(
        "No BB report found. Provide --report-path or generate outputs/failure_first_report.json first."
    )


def _extract_records(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for section in ("worst_cases", "dangerous_promotes", "false_confidence_zones"):
        values = report.get(section) or []
        if isinstance(values, list):
            for row in values:
                if isinstance(row, dict):
                    records.append(row)
    return records


def _normalize_metrics(report: Dict[str, Any]) -> Dict[str, Any]:
    metrics = dict(report.get("failure_first_metrics") or {})
    if "passes_components_most_at_risk" not in metrics:
        metrics["passes_components_most_at_risk"] = report.get("passes_components_most_at_risk") or []
    return metrics


def _persist_archive(decision: Dict[str, Any]) -> Path:
    _ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = _ARCHIVE_DIR / f"failure_enforcement_decision_{stamp}.json"
    suffix = 1
    while target.exists():
        target = _ARCHIVE_DIR / f"failure_enforcement_decision_{stamp}_{suffix}.json"
        suffix += 1
    target.write_text(json.dumps(decision, indent=2), encoding="utf-8")
    return target


def _validate_against_schema(decision: Dict[str, Any]) -> None:
    schema = _load_json(_SCHEMA_PATH)
    required = schema.get("required", [])
    for field in required:
        if field not in decision:
            raise ValueError(f"Missing required decision field: {field}")

    if not isinstance(decision.get("promotion_allowed"), bool):
        raise ValueError("promotion_allowed must be boolean")

    response_enum = set(schema.get("properties", {}).get("system_response", {}).get("enum", []))
    if decision.get("system_response") not in response_enum:
        raise ValueError("system_response is outside allowed enum")

    severity_enum = set(schema.get("properties", {}).get("incident_severity", {}).get("enum", []))
    if decision.get("incident_severity") not in severity_enum:
        raise ValueError("incident_severity is outside allowed enum")

    allowed_fields = set(schema.get("properties", {}).keys())
    unknown = set(decision.keys()) - allowed_fields
    # component_health is an allowed extension in decision payload but is not schema-required.
    unknown -= {"component_health"}
    if schema.get("additionalProperties") is False and unknown:
        raise ValueError(f"Unexpected decision fields: {sorted(unknown)}")

def _print_summary(decision: Dict[str, Any]) -> None:
    print(f"promotion_allowed: {decision['promotion_allowed']}")
    print(f"system_response: {decision['system_response']}")
    print(f"incident_severity: {decision['incident_severity']}")
    print(f"suppressed_component_count: {len(decision['suppressed_components'])}")
    print("top_triggering_conditions:")
    for condition in decision.get("triggering_conditions", [])[:5]:
        print(f"- {condition}")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate BB+1 failure enforcement decisions.")
    parser.add_argument("--report-path", help="Explicit BB report path. Defaults to latest report.")
    parser.add_argument("--output", default=str(_DEFAULT_OUTPUT_PATH), help="Decision output path.")
    args = parser.parse_args(argv)

    report_path = Path(args.report_path) if args.report_path else _latest_failure_first_report()
    report = _load_json(report_path)
    if not isinstance(report, dict):
        raise ValueError(f"Expected dict report JSON at {report_path}, got {type(report).__name__}")

    metrics = _normalize_metrics(report)
    records = _extract_records(report)

    try:
        source_ref = str(report_path.relative_to(_REPO_ROOT))
    except ValueError:
        source_ref = str(report_path)

    decision = evaluate_failure_controls(
        metrics,
        records,
        source_report_ref=source_ref,
    )
    _validate_against_schema(decision)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(decision, indent=2), encoding="utf-8")
    archive_path = _persist_archive(decision)

    _print_summary(decision)
    print(f"decision_output_path: {output_path}")
    print(f"archived_decision_path: {archive_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
