from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.routing_policy import (
    RoutingPolicyError,
    load_routing_policy,
    resolve_routing_decision,
)


def _write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _entry(*, version: str = "v1.0.0") -> dict:
    text = "You are the AG runtime control prompt. Execute only declared bounded steps."
    immutability_hash = "sha256:babde641d72a7df123f15ce11e89c00738f9592eb649ee6bf8afd6c14d4b4d02"
    return {
        "artifact_type": "prompt_registry_entry",
        "schema_version": "1.0.0",
        "prompt_id": "ag.runtime.default",
        "prompt_version": version,
        "created_at": "2026-03-24T00:00:00Z",
        "status": "approved",
        "owner": {"team": "runtime-governance", "contact": "runtime-governance@spectrum-systems.test"},
        "risk_class": "high",
        "prompt_text": text,
        "prompt_purpose": "Deterministic AG runtime execution guidance.",
        "linked_eval_set_ids": ["ag-runtime-golden-path-v1"],
        "runtime_metadata": {
            "immutability_hash": immutability_hash,
            "selection_key": f"ag.runtime.default@{version}",
        },
    }


def _alias_map(*, alias: str = "prod") -> dict:
    return {
        "artifact_type": "prompt_alias_map",
        "schema_version": "1.0.0",
        "created_at": "2026-03-24T00:00:00Z",
        "alias_scope": "ag_runtime",
        "aliases": [
            {
                "prompt_id": "ag.runtime.default",
                "alias": alias,
                "prompt_version": "v1.0.0",
                "allow_deprecated": False,
            }
        ],
    }


def _policy() -> dict:
    return {
        "artifact_type": "routing_policy",
        "schema_version": "1.0.0",
        "policy_id": "rp-ag-runtime-v1",
        "created_at": "2026-03-24T00:00:00Z",
        "policy_scope": "ag_runtime",
        "model_catalog": ["openai:gpt-4o-mini"],
        "routes": [
            {
                "route_key": "meeting_minutes_default",
                "task_class": "meeting_minutes",
                "risk_class": "high",
                "prompt_selection": {"prompt_id": "ag.runtime.default", "prompt_alias": "prod"},
                "model_selection": {"selected_model_id": "openai:gpt-4o-mini"},
            }
        ],
    }


def test_deterministic_routing_resolution() -> None:
    policy = _policy()
    entries = [_entry()]
    aliases = _alias_map()

    first = resolve_routing_decision(
        policy=policy,
        route_key="meeting_minutes_default",
        task_class="meeting_minutes",
        trace_id="trace-001",
        agent_run_id="agrun-001",
        prompt_entries=entries,
        prompt_alias_map=aliases,
    )
    second = resolve_routing_decision(
        policy=policy,
        route_key="meeting_minutes_default",
        task_class="meeting_minutes",
        trace_id="trace-001",
        agent_run_id="agrun-001",
        prompt_entries=entries,
        prompt_alias_map=aliases,
    )

    assert first == second
    assert first["routing_decision"]["selected_model_id"] == "openai:gpt-4o-mini"


def test_unknown_route_key_rejected() -> None:
    with pytest.raises(RoutingPolicyError, match="no routing policy match found"):
        resolve_routing_decision(
            policy=_policy(),
            route_key="unknown_route",
            task_class="meeting_minutes",
            trace_id="trace-001",
            agent_run_id="agrun-001",
            prompt_entries=[_entry()],
            prompt_alias_map=_alias_map(),
        )


def test_ambiguous_policy_rejected() -> None:
    policy = _policy()
    policy["routes"].append(
        {
            "route_key": "meeting_minutes_default",
            "risk_class": "high",
            "prompt_selection": {"prompt_id": "ag.runtime.default", "prompt_alias": "prod"},
            "model_selection": {"selected_model_id": "openai:gpt-4o-mini"},
        }
    )

    with pytest.raises(RoutingPolicyError, match="ambiguous routing policy match"):
        resolve_routing_decision(
            policy=policy,
            route_key="meeting_minutes_default",
            task_class="meeting_minutes",
            trace_id="trace-001",
            agent_run_id="agrun-001",
            prompt_entries=[_entry()],
            prompt_alias_map=_alias_map(),
        )


def test_invalid_prompt_alias_rejected() -> None:
    policy = _policy()
    policy["routes"][0]["prompt_selection"]["prompt_alias"] = "staging"

    with pytest.raises(RoutingPolicyError, match="routing prompt selection failed"):
        resolve_routing_decision(
            policy=policy,
            route_key="meeting_minutes_default",
            task_class="meeting_minutes",
            trace_id="trace-001",
            agent_run_id="agrun-001",
            prompt_entries=[_entry()],
            prompt_alias_map=_alias_map(alias="prod"),
        )


def test_invalid_selected_model_id_rejected() -> None:
    policy = _policy()
    policy["routes"][0]["model_selection"]["selected_model_id"] = "openai:gpt-5-nonexistent"

    with pytest.raises(RoutingPolicyError, match="is not in policy model_catalog"):
        resolve_routing_decision(
            policy=policy,
            route_key="meeting_minutes_default",
            task_class="meeting_minutes",
            trace_id="trace-001",
            agent_run_id="agrun-001",
            prompt_entries=[_entry()],
            prompt_alias_map=_alias_map(),
        )


def test_malformed_policy_rejected(tmp_path: Path) -> None:
    malformed_path = tmp_path / "routing_policy.json"
    malformed_path.write_text("{bad json", encoding="utf-8")

    with pytest.raises(RoutingPolicyError, match="malformed routing policy JSON"):
        load_routing_policy(malformed_path)


def test_policy_schema_validation_rejected(tmp_path: Path) -> None:
    bad = _policy()
    bad.pop("routes")
    path = _write_json(tmp_path / "routing_policy.json", bad)

    with pytest.raises(RoutingPolicyError, match="schema validation failed"):
        load_routing_policy(path)
