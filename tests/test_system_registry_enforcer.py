from __future__ import annotations

from spectrum_systems.modules.runtime.system_registry_enforcer import (
    clear_registry_enforcer_caches,
    validate_artifact_authority,
    validate_system_action,
    validate_system_handoff,
)


def test_validate_system_action_allows_valid_owned_edge() -> None:
    clear_registry_enforcer_caches()
    result = validate_system_action("TLC", "orchestration", "PQX")
    assert result["allow"] is True
    assert result["violation_codes"] == []


def test_validate_system_action_blocks_invalid_actor_and_target() -> None:
    clear_registry_enforcer_caches()
    result = validate_system_action("BAD", "orchestration", "NOPE")
    assert result["allow"] is False
    assert "E_UNKNOWN_SOURCE_SYSTEM" in result["violation_codes"]
    assert "E_UNKNOWN_TARGET_SYSTEM" in result["violation_codes"]


def test_validate_system_handoff_requires_trace_continuity() -> None:
    clear_registry_enforcer_caches()
    result = validate_system_handoff(
        "TLC",
        "PQX",
        {
            "schema_name": "codex_pqx_task_wrapper",
            "action_type": "orchestration",
            "payload": {},
            "required_fields": [],
            "expected_trace_refs": ["trace:required"],
        },
    )
    assert result["allow"] is False
    assert "E_MISSING_TRACE_CONTINUITY" in result["violation_codes"]


def test_validate_artifact_authority_blocks_non_cde_closure_decision() -> None:
    result = validate_artifact_authority(emitting_system="PQX", artifact_type="closure_decision_artifact")
    assert result["allow"] is False
    assert "E_ARTIFACT_AUTHORITY_VIOLATION_CLOSURE_DECISION_CDE_ONLY" in result["violation_codes"]
