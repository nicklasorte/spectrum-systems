"""Contract constants and validators for strategic knowledge schema family."""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator

from spectrum_systems.contracts import load_schema

SCHEMA_NAMES = (
    "strategic_knowledge_source_ref",
    "strategic_knowledge_artifact_ref",
    "book_intelligence_pack",
    "transcript_intelligence_pack",
    "story_bank_entry",
    "tactic_register",
    "viewpoint_pack",
    "evidence_map",
)


def validate(instance: dict[str, Any], schema_name: str) -> None:
    if schema_name not in SCHEMA_NAMES:
        raise ValueError(f"Unsupported strategic schema: {schema_name}")
    schema = load_schema(schema_name)
    Draft202012Validator(schema).validate(instance)

