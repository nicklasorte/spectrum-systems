#!/usr/bin/env python3
"""Build deterministic source authority indexes from structured source artifacts."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "contracts" / "schemas" / "source_design_extraction.schema.json"
SOURCE_STRUCTURED_DIR = REPO_ROOT / "docs" / "source_structured"
SOURCE_INDEXES_DIR = REPO_ROOT / "docs" / "source_indexes"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _build_validator() -> Draft202012Validator:
    schema = _load_json(SCHEMA_PATH)
    return Draft202012Validator(schema)


def _validate_artifact(validator: Draft202012Validator, artifact: dict[str, Any], path: Path) -> None:
    errors = sorted(validator.iter_errors(artifact), key=lambda error: list(error.path))
    if errors:
        lines = [f"Schema validation failed for {path}:"]
        for error in errors:
            pointer = "/".join(str(part) for part in error.path)
            lines.append(f" - {pointer or '<root>'}: {error.message}")
        raise ValueError("\n".join(lines))


def _extract_machine_json_block(markdown: str, heading: str) -> Any:
    pattern = rf"##\s+{re.escape(heading)}\s*\n```json\s*(.*?)\s*```"
    match = re.search(pattern, markdown, re.DOTALL)
    if not match:
        raise ValueError(f"Missing required json block for heading: {heading}")
    return json.loads(match.group(1))


def _load_markdown_artifacts() -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for source_path in sorted(SOURCE_STRUCTURED_DIR.glob("*.source.md")):
        raw_text = source_path.read_text(encoding="utf-8")
        source_document = _extract_machine_json_block(raw_text, "machine_source_document")
        obligations = _extract_machine_json_block(raw_text, "machine_obligations")

        if source_document.get("status") not in {"active", "inactive"}:
            raise ValueError(f"Invalid source status in {source_path}: {source_document.get('status')}")

        normalized_obligations: list[dict[str, Any]] = []
        for row in obligations:
            normalized_obligations.append({
                "obligation_id": row["obligation_id"],
                "trace_id": row.get("trace_id", f"TRACE-{row['obligation_id'].replace('OBL-', '')}"),
                "component_id": row["component_id"],
                "category": row["category"],
                "description": row["description"],
                "layer": row["layer"],
                "required_artifacts": row.get("required_artifacts", []),
                "required_gates": row.get("required_gates", []),
                "status": row.get("status", "planned"),
                "source_section": row.get("source_section", "unspecified"),
                "duplicate_allowed": row.get("duplicate_allowed", False),
                "duplicate_reason": row.get("duplicate_reason", "")
            })

        try:
            relative_path = str(source_path.relative_to(REPO_ROOT))
        except ValueError:
            relative_path = str(source_path)

        artifacts.append({
            "source_document": {
                "source_id": source_document["source_id"],
                "title": source_document["title"],
                "file_path": source_document["path"],
                "status": source_document["status"],
                "notes": source_document.get("notes", "")
            },
            "source_traceability_rows": normalized_obligations,
            "__path": relative_path
        })
    return artifacts


def _load_legacy_json_artifacts() -> list[dict[str, Any]]:
    validator = _build_validator()
    artifacts: list[dict[str, Any]] = []
    for source_path in sorted(SOURCE_STRUCTURED_DIR.glob("*.json")):
        artifact = _load_json(source_path)
        _validate_artifact(validator, artifact, source_path)
        artifact["__path"] = str(source_path.relative_to(REPO_ROOT))
        artifacts.append(artifact)
    return artifacts


def _load_structured_sources() -> list[dict[str, Any]]:
    markdown_artifacts = _load_markdown_artifacts()
    if markdown_artifacts:
        return markdown_artifacts

    legacy_artifacts = _load_legacy_json_artifacts()
    if legacy_artifacts:
        return legacy_artifacts

    raise ValueError(f"No structured source files found in {SOURCE_STRUCTURED_DIR}")


def _check_duplicate_obligation_ids(artifacts: list[dict[str, Any]]) -> None:
    seen: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for artifact in artifacts:
        source_id = artifact["source_document"]["source_id"]
        for row in artifact["source_traceability_rows"]:
            obligation_id = row["obligation_id"]
            seen[obligation_id].append({
                "source_id": source_id,
                "trace_id": row["trace_id"],
                "duplicate_allowed": row.get("duplicate_allowed", False),
                "duplicate_reason": row.get("duplicate_reason", "")
            })

    duplicate_errors: list[str] = []
    for obligation_id, entries in sorted(seen.items()):
        if len(entries) <= 1:
            continue
        if not all(item["duplicate_allowed"] and item["duplicate_reason"] for item in entries):
            formatted = ", ".join(f"{item['source_id']}:{item['trace_id']}" for item in entries)
            duplicate_errors.append(
                f"Duplicate obligation_id '{obligation_id}' is not explicitly documented across entries: {formatted}"
            )

    if duplicate_errors:
        raise ValueError("\n".join(duplicate_errors))


def _emit_source_inventory(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for artifact in sorted(artifacts, key=lambda a: a["source_document"]["source_id"]):
        document = artifact["source_document"]
        rows.append({
            "source_id": document["source_id"],
            "title": document["title"],
            "file_path": document["file_path"],
            "status": document["status"],
            "structured_artifact": artifact["__path"],
            "notes": document.get("notes", "")
        })
    return {
        "index_name": "source_inventory",
        "schema_version": "1.0.0",
        "sources": rows
    }


def _emit_obligation_index(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for artifact in sorted(artifacts, key=lambda a: a["source_document"]["source_id"]):
        source_id = artifact["source_document"]["source_id"]
        for row in sorted(artifact["source_traceability_rows"], key=lambda r: (r["obligation_id"], r["trace_id"])):
            rows.append({
                "obligation_id": row["obligation_id"],
                "source_id": source_id,
                "trace_id": row["trace_id"],
                "component_id": row["component_id"],
                "category": row.get("category", "unspecified"),
                "description": row.get("description", row.get("obligation_statement", "")),
                "layer": row.get("layer", "unspecified"),
                "required_artifacts": row.get("required_artifacts", []),
                "required_gates": row.get("required_gates", []),
                "status": row.get("status", "planned"),
                "source_section": row["source_section"],
                "duplicate_allowed": row.get("duplicate_allowed", False),
                "duplicate_reason": row.get("duplicate_reason", "")
            })
    rows.sort(key=lambda r: (r["obligation_id"], r["source_id"], r["trace_id"]))
    return {
        "index_name": "obligation_index",
        "schema_version": "1.0.0",
        "obligations": rows
    }


def _emit_component_source_map(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    component_map: dict[str, dict[str, Any]] = {}
    for artifact in artifacts:
        source_id = artifact["source_document"]["source_id"]
        for row in artifact["source_traceability_rows"]:
            component_id = row["component_id"]
            component_row = component_map.setdefault(
                component_id,
                {
                    "component_id": component_id,
                    "source_ids": set(),
                    "obligation_ids": set()
                }
            )
            component_row["source_ids"].add(source_id)
            component_row["obligation_ids"].add(row["obligation_id"])

    rows = []
    for component_id in sorted(component_map):
        row = component_map[component_id]
        rows.append({
            "component_id": component_id,
            "source_ids": sorted(row["source_ids"]),
            "obligation_ids": sorted(row["obligation_ids"])
        })

    return {
        "index_name": "component_source_map",
        "schema_version": "1.0.0",
        "components": rows
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def build_indexes() -> None:
    artifacts = _load_structured_sources()
    _check_duplicate_obligation_ids(artifacts)

    source_inventory = _emit_source_inventory(artifacts)
    obligation_index = _emit_obligation_index(artifacts)
    component_source_map = _emit_component_source_map(artifacts)

    _write_json(SOURCE_INDEXES_DIR / "source_inventory.json", source_inventory)
    _write_json(SOURCE_INDEXES_DIR / "obligation_index.json", obligation_index)
    _write_json(SOURCE_INDEXES_DIR / "component_source_map.json", component_source_map)


if __name__ == "__main__":
    build_indexes()
