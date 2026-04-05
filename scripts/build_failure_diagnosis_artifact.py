#!/usr/bin/env python3
"""Build deterministic failure diagnosis artifact (BATCH-FRE-01)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from jsonschema import Draft202012Validator, FormatChecker

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import load_schema  # noqa: E402
from spectrum_systems.modules.runtime.failure_diagnosis_engine import (  # noqa: E402
    FailureDiagnosisError,
    build_failure_diagnosis_artifact,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build deterministic failure diagnosis artifact")
    parser.add_argument("--input", required=True, help="Path to normalized diagnosis input bundle JSON")
    parser.add_argument("--output", required=True, help="Output JSON path for failure_diagnosis_artifact")
    parser.add_argument("--emitted-at", required=True, help="Deterministic RFC3339 timestamp")
    parser.add_argument("--run-id", default="run-fre-cli", help="Run identifier")
    parser.add_argument("--trace-id", default="trace-fre-cli", help="Trace identifier")
    parser.add_argument("--policy-id", default="FRE-001.failure_diagnosis.v1", help="Policy identifier")
    parser.add_argument(
        "--governing-ref",
        default="docs/roadmaps/system_roadmap.md#batch-fre-01",
        help="Roadmap/reference anchor",
    )
    return parser.parse_args()


def _load_json(path: Path, *, label: str) -> dict:
    if not path.is_file():
        raise FailureDiagnosisError(f"{label} file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FailureDiagnosisError(f"{label} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise FailureDiagnosisError(f"{label} must be a JSON object")
    return payload


def main() -> int:
    args = _parse_args()
    try:
        bundle = _load_json(Path(args.input), label="input")
        failure_source_type = str(bundle.get("failure_source_type") or "")
        source_artifact_refs = bundle.get("source_artifact_refs")
        failure_payload = bundle.get("failure_payload")

        if not isinstance(source_artifact_refs, list):
            raise FailureDiagnosisError("input.source_artifact_refs must be a list")
        if not isinstance(failure_payload, dict):
            raise FailureDiagnosisError("input.failure_payload must be an object")

        artifact = build_failure_diagnosis_artifact(
            failure_source_type=failure_source_type,
            source_artifact_refs=[str(item) for item in source_artifact_refs],
            failure_payload=failure_payload,
            emitted_at=args.emitted_at,
            run_id=args.run_id,
            trace_id=args.trace_id,
            policy_id=args.policy_id,
            governing_ref=args.governing_ref,
        )

        Draft202012Validator(load_schema("failure_diagnosis_artifact"), format_checker=FormatChecker()).validate(artifact)
    except FailureDiagnosisError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(str(output_path))

    if artifact["blocking_severity"] == "blocker":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
