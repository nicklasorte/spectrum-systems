from __future__ import annotations

from typing import Any, Dict

from jsonschema import Draft202012Validator

from spectrum_systems.contracts import load_schema


class StructuredOutputError(RuntimeError):
    """Raised when model output does not conform to required structured contract."""


def enforce_structured_response(schema_name: str, model_output: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    schema = load_schema(schema_name)
    try:
        Draft202012Validator(schema).validate(model_output)
    except Exception as exc:
        raise StructuredOutputError(f"model output rejected by schema '{schema_name}': {exc}") from exc

    return {
        "validated_output": model_output,
        "guardrails": {
            "schema_name": schema_name,
            "validated": True,
            "validation_mode": "fail_closed",
            "metadata": dict(metadata),
        },
    }
