"""HS-04 deterministic routing policy engine for AG runtime."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.prompt_registry import (
    PromptRegistryError,
    resolve_prompt_version,
)
from spectrum_systems.utils.deterministic_id import canonical_json, deterministic_id


class RoutingPolicyError(RuntimeError):
    """Raised when routing policy loading or resolution fails closed."""


def _validate(instance: Dict[str, Any], schema_name: str) -> None:
    schema = load_schema(schema_name)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(instance)


def _deterministic_timestamp(seed_payload: Dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json(seed_payload).encode("utf-8")).hexdigest()
    offset_seconds = int(digest[:8], 16) % (365 * 24 * 60 * 60)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return (base + timedelta(seconds=offset_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_routing_policy(path: Path) -> Dict[str, Any]:
    """Load and validate a governed routing policy artifact."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RoutingPolicyError(f"missing routing policy file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RoutingPolicyError(f"malformed routing policy JSON at {path}: {exc}") from exc

    try:
        _validate(payload, "routing_policy")
    except Exception as exc:
        raise RoutingPolicyError(f"routing policy schema validation failed: {exc}") from exc

    catalog = set(payload["model_catalog"])
    for route in payload["routes"]:
        selected_model_id = str(route["model_selection"]["selected_model_id"])
        if selected_model_id not in catalog:
            raise RoutingPolicyError(
                "routing policy references selected_model_id outside model_catalog: "
                f"{selected_model_id}"
            )

    return payload


def _matching_routes(policy: Dict[str, Any], *, route_key: str, task_class: str) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []
    for route in policy.get("routes", []):
        if route.get("route_key") != route_key:
            continue
        route_task_class = route.get("task_class")
        if route_task_class is not None and route_task_class != task_class:
            continue
        matches.append(route)
    return matches


def resolve_routing_decision(
    *,
    policy: Dict[str, Any],
    route_key: str,
    task_class: str,
    trace_id: str,
    agent_run_id: str,
    prompt_entries: List[Dict[str, Any]],
    prompt_alias_map: Dict[str, Any],
) -> Dict[str, Any]:
    """Resolve deterministic routing decision artifact from runtime inputs.

    Fail-closed conditions:
    - route key/task class does not match exactly one policy route
    - selected prompt alias cannot be resolved by HS-01
    - selected model id is not present in policy model_catalog
    """
    if not route_key or not task_class:
        raise RoutingPolicyError("route_key and task_class are required for routing resolution")

    matches = _matching_routes(policy, route_key=route_key, task_class=task_class)
    if not matches:
        raise RoutingPolicyError(
            f"no routing policy match found for route_key='{route_key}', task_class='{task_class}'"
        )
    if len(matches) != 1:
        raise RoutingPolicyError(
            f"ambiguous routing policy match for route_key='{route_key}', task_class='{task_class}': {len(matches)} matches"
        )

    route = matches[0]
    selected_prompt_id = str(route["prompt_selection"]["prompt_id"])
    selected_prompt_alias = str(route["prompt_selection"]["prompt_alias"])

    try:
        prompt_resolution = resolve_prompt_version(
            prompt_id=selected_prompt_id,
            alias=selected_prompt_alias,
            entries=prompt_entries,
            alias_map=prompt_alias_map,
        )
    except PromptRegistryError as exc:
        raise RoutingPolicyError(f"routing prompt selection failed: {exc}") from exc

    selected_model_id = str(route["model_selection"]["selected_model_id"])
    model_catalog = set(policy.get("model_catalog", []))
    if selected_model_id not in model_catalog:
        raise RoutingPolicyError(
            f"routing selected_model_id '{selected_model_id}' is not in policy model_catalog"
        )

    identity_payload = {
        "policy_id": policy["policy_id"],
        "route_key": route_key,
        "task_class": task_class,
        "risk_class": route["risk_class"],
        "selected_prompt_id": selected_prompt_id,
        "selected_prompt_alias": selected_prompt_alias,
        "resolved_prompt_version": prompt_resolution["prompt_version"],
        "selected_model_id": selected_model_id,
        "trace": {
            "trace_id": trace_id,
            "agent_run_id": agent_run_id,
        },
    }

    decision = {
        "artifact_type": "routing_decision",
        "schema_version": "1.0.0",
        "routing_decision_id": deterministic_id(
            prefix="rd",
            namespace="routing_decision",
            payload=identity_payload,
        ),
        "created_at": _deterministic_timestamp(identity_payload),
        "route_key": route_key,
        "task_class": task_class,
        "risk_class": route["risk_class"],
        "selected_prompt_id": selected_prompt_id,
        "selected_prompt_alias": selected_prompt_alias,
        "resolved_prompt_version": prompt_resolution["prompt_version"],
        "selected_model_id": selected_model_id,
        "policy_id": policy["policy_id"],
        "trace": {
            "trace_id": trace_id,
            "agent_run_id": agent_run_id,
        },
        "related_artifact_refs": [
            f"routing_policy:{policy['policy_id']}",
            f"prompt_alias_map:{prompt_alias_map['alias_scope']}",
        ],
    }

    try:
        _validate(decision, "routing_decision")
    except Exception as exc:
        raise RoutingPolicyError(f"routing decision schema validation failed: {exc}") from exc

    return {
        "routing_decision": decision,
        "prompt_resolution": prompt_resolution,
    }
