"""
Contract utilities for loading and validating Spectrum Systems artifact contracts.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


_BASE_DIR = Path(__file__).resolve().parents[2]
_CONTRACTS_DIR = _BASE_DIR / "contracts"
_SCHEMAS_DIR = _CONTRACTS_DIR / "schemas"
_EXAMPLES_DIR = _CONTRACTS_DIR / "examples"


def list_supported_contracts() -> List[str]:
    """
    Return the canonical list of contract names discovered in contracts/schemas.
    """
    contracts = []
    for path in _SCHEMAS_DIR.glob("*.schema.json"):
        name = path.name.replace(".schema.json", "")
        contracts.append(name)
    return sorted(contracts)


def load_schema(name: str) -> Dict[str, Any]:
    """
    Load a JSON Schema by contract name (e.g., \"working_paper_input\").
    """
    schema_path = _SCHEMAS_DIR / f"{name}.schema.json"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema not found: {schema_path}")
    return json.loads(schema_path.read_text())


def load_example(name: str) -> Dict[str, Any]:
    """
    Load a JSON example instance for a contract.
    """
    primary_path = _EXAMPLES_DIR / f"{name}.json"
    fallback_path = _EXAMPLES_DIR / f"{name}.example.json"

    if primary_path.exists():
        return json.loads(primary_path.read_text())
    if fallback_path.exists():
        return json.loads(fallback_path.read_text())
    raise FileNotFoundError(f"Example not found: {primary_path} or {fallback_path}")


def validate_artifact(instance: Dict[str, Any], schema_name: str) -> None:
    """
    Validate an artifact instance against a named schema. Raises ValidationError on failure.
    """
    schema = load_schema(schema_name)
    Draft202012Validator(schema).validate(instance)
