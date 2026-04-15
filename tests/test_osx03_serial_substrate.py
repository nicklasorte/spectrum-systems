from __future__ import annotations

from spectrum_systems.contracts import load_example, load_schema, validate_artifact
from spectrum_systems.modules.runtime.ctx import (
    detect_context_conflicts,
    gather_sources,
    run_context_preflight,
)
from spectrum_systems.modules.runtime.dataset_registry import validate_dataset_registration
from spectrum_systems.modules.runtime.hnd import build_handoff_record
from spectrum_systems.modules.runtime.osx03_serial import run_bounded_canary
from spectrum_systems.modules.runtime.rollout_gate import enforce_a2a_intake, enforce_rollout_gate
from spectrum_systems.modules.runtime.tlx import apply_tool_output_limits, validate_tool_contract


NEW_SCHEMAS = [
    "prompt_spec",
    "prompt_version",
    "task_spec",
    "prompt_rollout_record",
    "eval_regression_report",
    "dataset_lineage_record",
    "observability_contract_record",
    "lineage_completeness_report",
    "replay_integrity_record",
    "evidence_gap_report",
    "entropy_report",
    "policy_lifecycle_record",
    "release_record",
    "calibration_summary",
    "wrong_allow_record",
    "wrong_block_record",
    "confidence_drift_record",
    "hit_override_record",
    "hit_correction_diff",
    "handoff_record",
]


def _base_inputs() -> dict:
    prompt_entry = {
        "artifact_type": "prompt_registry_entry",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.0.0",
        "prompt_id": "prompt_task_bundle.summary",
        "prompt_version": "1.0.0",
        "status": "approved",
        "created_at": "2026-04-15T00:00:00Z",
        "prompt_text": "Summarize deterministically.",
        "runtime_metadata": {
            "selection_key": "prompt_task_bundle.summary@1.0.0",
            "immutability_hash": "sha256:fafe3433f0f0f576f68a08723f9f5d43d6ff3ac55aa6116f7aec7338d7ec4df4",
        },
    }
    alias_map = {
        "artifact_type": "prompt_alias_map",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.0.0",
        "aliases": [
            {
                "prompt_id": "prompt_task_bundle.summary",
                "alias": "prod",
                "prompt_version": "1.0.0",
                "allow_deprecated": False,
            }
        ],
    }
    return {
        "run_id": "RUN-OSX03",
        "trace_id": "TRACE-0001",
        "recipe": {
            "recipe_id": "ctx.recipe.prompt_task_bundle",
            "artifact_family": "prompt_task_bundle",
            "strict_mode": True,
            "required_sources": ["source.A", "source.B"],
        },
        "context_candidates": [
            {"source_id": "source.A", "trace_ref": "trace:a", "fresh": True, "content_hash": "ha", "policy_key": "p", "policy_value": "allow"},
            {"source_id": "source.B", "trace_ref": "trace:b", "fresh": True, "content_hash": "hb", "policy_key": "q", "policy_value": "allow"},
        ],
        "prompt_entries": [prompt_entry],
        "alias_map": alias_map,
        "task_registry": {"tasks": [{"task_id": "prompt_task_bundle.summarize", "description": "summary"}]},
        "eval_registry": {"evals": [{"eval_id": "EVL-REQ-1", "artifact_family": "prompt_task_bundle", "required": True}]},
        "dataset_record": {"dataset_id": "DS-1", "lineage_ref": "lineage:1", "age_days": 1, "source_refs": ["s1"], "version": "v1"},
        "judgments": [{"judgment_id": "J-1", "status": "active", "policy_key": "k", "policy_value": "v"}],
        "rollout_checks": {
            "bounded_family_passed": True,
            "all_redteams_complete": True,
            "all_fixes_complete": True,
            "replay_trace_parity": True,
            "promotion_readiness_enforced": True,
            "no_authority_duplication": True,
            "authority_lineage_complete": True,
        },
    }


def test_new_schema_examples_validate() -> None:
    for schema_name in NEW_SCHEMAS:
        schema = load_schema(schema_name)
        assert schema["additionalProperties"] is False
        validate_artifact(load_example(schema_name), schema_name)


def test_ctx_conflict_and_preflight_blocking_paths() -> None:
    conflicts = detect_context_conflicts(
        candidates=[
            {"source_id": "A", "policy_key": "topic", "policy_value": "allow"},
            {"source_id": "B", "policy_key": "topic", "policy_value": "deny"},
        ]
    )
    assert conflicts["has_conflicts"] is True
    passed, reasons = run_context_preflight(
        recipe={"required_sources": ["A"], "strict_mode": True},
        admitted_candidates=[{"source_id": "A", "fresh": False, "trace_ref": "x"}],
    )
    assert passed is False
    assert "stale_context:A" in reasons


def test_tlx_contract_and_output_limits() -> None:
    ok, reasons = validate_tool_contract(
        contract={"required_inputs": ["query"], "permission_metadata": {"permission_ref": "perm.search"}},
        payload={"query": "x"},
    )
    assert ok is True
    assert reasons == []
    envelope = {"tool_id": "search", "records": [{"a": "x"}, {"b": "y"}, {"c": "z"}], "record_count": 3}
    limited = apply_tool_output_limits(envelope=envelope, max_records=2, max_chars=5)
    assert limited["truncated"] is True
    assert limited["pagination"]["next_offset"] == 2


def test_dataset_and_handoff_fail_closed() -> None:
    ok, reasons = validate_dataset_registration(dataset_record={"dataset_id": "", "age_days": 40})
    assert ok is False
    assert "missing_lineage_ref" in reasons
    handoff = build_handoff_record(handoff_id="HND-1", required_keys=["ctx", "eval"], state={"ctx": 1})
    assert handoff["status"] == "blocked"


def test_phase14_rollout_and_a2a_guards() -> None:
    passed, reasons = enforce_rollout_gate(checks={"a": True, "b": False})
    assert passed is False
    assert reasons == ["missing:b"]
    intake_ok, intake_reasons = enforce_a2a_intake(
        lineage=False,
        context_preflight=True,
        eval_coverage=True,
        authority_lineage=True,
        policy_permission=True,
        budget_compatible=True,
    )
    assert intake_ok is False
    assert "missing:lineage" in intake_reasons


def test_end_to_end_happy_path() -> None:
    result = run_bounded_canary(**_base_inputs())
    assert result["status"] == "passed"
    assert result["artifacts"]["route"]["selected_route"] == "RQX"


def test_end_to_end_missing_eval_blocks() -> None:
    payload = _base_inputs()
    payload["eval_registry"] = {"evals": []}
    result = run_bounded_canary(**payload)
    assert result["status"] == "blocked"
    assert result["phase"] == "EVL_DAT"


def test_end_to_end_stale_context_blocks() -> None:
    payload = _base_inputs()
    payload["context_candidates"][0]["fresh"] = False
    result = run_bounded_canary(**payload)
    assert result["status"] == "blocked"
    assert result["phase"] == "CTX"


def test_end_to_end_promotion_bypass_blocks() -> None:
    payload = _base_inputs()
    payload["rollout_checks"]["promotion_readiness_enforced"] = False
    result = run_bounded_canary(**payload)
    assert result["status"] == "blocked"
    assert result["phase"] == "ROLLOUT"


def test_replay_and_rerun_consistency() -> None:
    a = run_bounded_canary(**_base_inputs())
    b = run_bounded_canary(**_base_inputs())
    assert a["status"] == b["status"] == "passed"
    assert a["artifacts"]["route"] == b["artifacts"]["route"]


def test_malformed_context_source_path() -> None:
    payload = _base_inputs()
    payload["context_candidates"] = gather_sources(candidates=[{"source_id": "source.A"}])
    result = run_bounded_canary(**payload)
    assert result["status"] == "blocked"
    assert result["phase"] == "CTX"
