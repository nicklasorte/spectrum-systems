"""TLX — Tooling Layer eXecutor."""

from __future__ import annotations

from typing import Any


def load_tool_registry(*, registry: dict[str, Any]) -> dict[str, Any]:
    tools = registry.get("tools", [])
    if not isinstance(tools, list):
        raise ValueError("tool registry must provide list at tools")
    return {str(tool["tool_id"]): dict(tool) for tool in tools}


def validate_tool_contract(*, contract: dict[str, Any], payload: dict[str, Any]) -> tuple[bool, list[str]]:
    required_inputs = contract.get("required_inputs", [])
    missing = [field for field in required_inputs if field not in payload]
    return len(missing) == 0, [f"missing_input:{field}" for field in missing]


def normalize_tool_output(*, tool_id: str, raw_output: Any) -> dict[str, Any]:
    if isinstance(raw_output, str):
        records = [{"text": raw_output}]
    elif isinstance(raw_output, list):
        records = raw_output
    else:
        records = [raw_output]
    return {"tool_id": tool_id, "records": records, "record_count": len(records)}


def apply_tool_output_limits(*, envelope: dict[str, Any], max_records: int, max_chars: int) -> dict[str, Any]:
    records = list(envelope.get("records", []))[:max_records]
    truncated = []
    for item in records:
        text = str(item)
        truncated.append(text[:max_chars])
    return {
        "tool_id": envelope.get("tool_id"),
        "records": truncated,
        "record_count": len(truncated),
        "truncated": len(truncated) < int(envelope.get("record_count", len(truncated))),
    }


def enforce_tool_permission_profile(*, permission_profile: dict[str, Any], dispatch_request: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if dispatch_request.get("permission") not in set(permission_profile.get("allowed_permissions", [])):
        reasons.append("permission_not_allowed")
    if dispatch_request.get("network") and not permission_profile.get("allow_network", False):
        reasons.append("network_not_allowed")
    return len(reasons) == 0, reasons


def build_tool_dispatch_record(*, run_id: str, trace_id: str, tool_id: str, contract_ref: str, permission_ref: str, output_ref: str) -> dict[str, Any]:
    return {
        "artifact_type": "tool_dispatch_record",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "dispatch_id": f"TDIS-{run_id}-{trace_id}-{tool_id}",
        "run_id": run_id,
        "trace_id": trace_id,
        "tool_id": tool_id,
        "contract_ref": contract_ref,
        "permission_ref": permission_ref,
        "output_ref": output_ref,
    }
