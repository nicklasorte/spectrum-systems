#!/usr/bin/env python3
"""Validate a strategic knowledge artifact and emit a governed decision artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.strategic_knowledge.validation_loader import (  # noqa: E402
    load_artifact_payload,
    load_artifact_registry_payload,
    load_source_catalog_payload,
)
from spectrum_systems.modules.strategic_knowledge.validator import validate_strategic_knowledge_artifact  # noqa: E402

EXIT_CODES = {
    "allow": 0,
    "require_review": 0,
    "require_rebuild": 2,
    "block": 1,
}


def _emit_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, indent=2))


def _missing_trace_context(args: argparse.Namespace) -> list[str]:
    required = ("trace_id", "span_id", "parent_span_id", "run_id")
    missing: list[str] = []
    for field_name in required:
        value = getattr(args, field_name)
        if not isinstance(value, str) or not value.strip():
            missing.append(field_name)
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-path", required=True, type=Path, help="Path to candidate strategic artifact JSON.")
    parser.add_argument(
        "--data-lake-root",
        required=True,
        type=Path,
        help="Data lake root containing strategic_knowledge metadata/lineage directories.",
    )
    parser.add_argument("--trace-id", type=str, default=None, help="Required trace identifier for governed validation.")
    parser.add_argument("--span-id", type=str, default=None, help="Required span identifier for governed validation.")
    parser.add_argument(
        "--parent-span-id",
        type=str,
        default=None,
        help="Required parent span identifier for governed validation.",
    )
    parser.add_argument("--run-id", type=str, default=None, help="Required run identifier for governed validation.")
    args = parser.parse_args()

    missing_trace_fields = _missing_trace_context(args)
    if missing_trace_fields:
        _emit_json(
            {
                "status": "error",
                "system_response": "block",
                "error": {
                    "code": "MISSING_TRACE_CONTEXT",
                    "message": (
                        "governed strategic-knowledge validation requires explicit trace context "
                        "(trace_id, span_id, parent_span_id, run_id)"
                    ),
                    "missing_fields": missing_trace_fields,
                },
            }
        )
        return 2

    try:
        artifact = load_artifact_payload(args.artifact_path)
        source_catalog = load_source_catalog_payload(args.data_lake_root)
        artifact_registry = load_artifact_registry_payload(args.data_lake_root)
        decision = validate_strategic_knowledge_artifact(
            artifact,
            {
                "source_catalog": source_catalog,
                "artifact_registry": artifact_registry,
                "trace_id": args.trace_id,
                "span_id": args.span_id,
                "parent_span_id": args.parent_span_id,
                "run_id": args.run_id,
            },
        )
    except FileNotFoundError as exc:
        _emit_json(
            {
                "status": "error",
                "system_response": "block",
                "error": {"code": "FILE_NOT_FOUND", "message": str(exc)},
            }
        )
        return 2
    except json.JSONDecodeError as exc:
        _emit_json(
            {
                "status": "error",
                "system_response": "block",
                "error": {"code": "ARTIFACT_JSON_PARSE_FAILED", "message": str(exc)},
            }
        )
        return 2
    except ValueError as exc:
        _emit_json(
            {
                "status": "error",
                "system_response": "block",
                "error": {"code": "VALIDATION_CONTEXT_ERROR", "message": str(exc)},
            }
        )
        return 2
    _emit_json(decision)
    return EXIT_CODES[decision["system_response"]]


if __name__ == "__main__":
    raise SystemExit(main())
