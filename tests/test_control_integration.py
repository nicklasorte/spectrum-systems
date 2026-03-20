"""Tests for BN.7 — Control Signal → Runtime Integration layer."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.control_integration import (  # noqa: E402
    _BYPASS_BLOCKED_RESULT,
    enforce_control_before_execution,
    generate_working_paper_with_control,
    run_simulation_with_control,
    summarize_control_integration,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _passing_artifact() -> Dict[str, Any]:
    """A minimal artifact that will pass the full control chain."""
    return {
        "evaluation_id": "EVAL-BN7",
        "artifact_id": "ART-BN7",
        "slo_status": "pass",
        "allowed_to_proceed": True,
        "slis": {"traceability_integrity": 1.0},
        "lineage_valid": True,
        "lineage_validation_mode": "strict",
        "lineage_defaulted": False,
        "parent_artifact_ids": ["PARENT-1"],
        "violations": [],
        "error_budget": 0.0,
        "inputs": {},
        "created_at": "2026-03-20T00:00:00+00:00",
    }


def _blocked_artifact() -> Dict[str, Any]:
    """An artifact that will be blocked by the control chain."""
    return {
        "evaluation_id": "EVAL-BN7-FAIL",
        "artifact_id": "ART-BN7-FAIL",
        "slo_status": "fail",
        "allowed_to_proceed": False,
        "slis": {"traceability_integrity": 0.0},
        "lineage_valid": False,
        "lineage_validation_mode": "strict",
        "lineage_defaulted": True,
        "parent_artifact_ids": [],
        "violations": ["slo_violation"],
        "error_budget": 1.0,
        "inputs": {},
        "created_at": "2026-03-20T00:00:00+00:00",
    }


def _ctx(artifact: Any = None, stage: str = "synthesis", runtime: str = "test") -> Dict[str, Any]:
    return {
        "artifact": artifact if artifact is not None else _passing_artifact(),
        "stage": stage,
        "runtime_environment": runtime,
    }


def _blocked_ctx() -> Dict[str, Any]:
    return _ctx(artifact=_blocked_artifact())


# ---------------------------------------------------------------------------
# H.1 — simulation cannot run when control blocks
# ---------------------------------------------------------------------------


def test_simulation_cannot_run_when_control_blocks():
    called = []

    def sim_fn():
        called.append(True)

    result, integration = run_simulation_with_control(_blocked_ctx(), sim_fn)
    assert integration["continuation_allowed"] is False
    assert result is None
    assert called == [], "sim_fn must not be called when control blocks"


# ---------------------------------------------------------------------------
# H.2 — working paper generation cannot run when blocked
# ---------------------------------------------------------------------------


def test_working_paper_generation_cannot_run_when_blocked():
    called = []

    def gen_fn():
        called.append(True)
        return {"paper": "data"}

    paper, integration = generate_working_paper_with_control(_blocked_ctx(), gen_fn)
    assert integration["continuation_allowed"] is False
    assert paper is None
    assert called == [], "gen_fn must not be called when control blocks"


# ---------------------------------------------------------------------------
# H.3 — publication is blocked when publication_allowed = False
# ---------------------------------------------------------------------------


def test_publication_is_blocked_when_publication_disallowed():
    # Build a patched execution_result with publication_blocked=True
    blocked_exec = {
        "execution_status": "blocked",
        "publication_blocked": True,
        "decision_blocked": True,
        "rerun_triggered": False,
        "escalation_triggered": False,
        "human_review_required": False,
        "actions_taken": [],
        "validators_run": [],
        "validators_failed": [],
        "repair_actions_applied": [],
    }
    blocked_chain = {
        "control_chain_decision": {"control_signals": {}},
        "continuation_allowed": False,
        "primary_reason_code": "control_chain_blocked_by_gating",
        "schema_errors": [],
        "enforcement_result": None,
        "gating_result": None,
        "execution_result": blocked_exec,
    }
    with patch(
        "spectrum_systems.modules.runtime.control_integration.run_control_chain",
        return_value=blocked_chain,
    ):
        result = enforce_control_before_execution(_ctx())
    assert result["publication_blocked"] is True
    assert result["continuation_allowed"] is False


# ---------------------------------------------------------------------------
# H.4 — decision-grade marking is blocked when decision_blocked = True
# ---------------------------------------------------------------------------


def test_decision_grade_marking_blocked_when_decision_blocked():
    blocked_exec = {
        "execution_status": "blocked",
        "publication_blocked": False,
        "decision_blocked": True,
        "rerun_triggered": False,
        "escalation_triggered": False,
        "human_review_required": False,
        "actions_taken": [],
        "validators_run": [],
        "validators_failed": [],
        "repair_actions_applied": [],
    }
    blocked_chain = {
        "control_chain_decision": {"control_signals": {}},
        "continuation_allowed": False,
        "primary_reason_code": "control_chain_blocked_by_gating",
        "schema_errors": [],
        "enforcement_result": None,
        "gating_result": None,
        "execution_result": blocked_exec,
    }
    with patch(
        "spectrum_systems.modules.runtime.control_integration.run_control_chain",
        return_value=blocked_chain,
    ):
        result = enforce_control_before_execution(_ctx())
    assert result["decision_blocked"] is True
    assert result["continuation_allowed"] is False


# ---------------------------------------------------------------------------
# H.5 — rerun_triggered prevents execution
# ---------------------------------------------------------------------------


def test_rerun_triggered_prevents_execution():
    blocked_exec = {
        "execution_status": "blocked",
        "publication_blocked": True,
        "decision_blocked": True,
        "rerun_triggered": True,
        "escalation_triggered": False,
        "human_review_required": False,
        "actions_taken": [],
        "validators_run": [],
        "validators_failed": [],
        "repair_actions_applied": [],
    }
    blocked_chain = {
        "control_chain_decision": {"control_signals": {}},
        "continuation_allowed": False,
        "primary_reason_code": "rerun_required",
        "schema_errors": [],
        "enforcement_result": None,
        "gating_result": None,
        "execution_result": blocked_exec,
    }
    with patch(
        "spectrum_systems.modules.runtime.control_integration.run_control_chain",
        return_value=blocked_chain,
    ):
        result = enforce_control_before_execution(_ctx())
    assert result["rerun_triggered"] is True
    assert result["continuation_allowed"] is False


# ---------------------------------------------------------------------------
# H.6 — escalation_required prevents execution
# ---------------------------------------------------------------------------


def test_escalation_required_prevents_execution():
    escalated_exec = {
        "execution_status": "escalated",
        "publication_blocked": True,
        "decision_blocked": True,
        "rerun_triggered": False,
        "escalation_triggered": True,
        "human_review_required": False,
        "actions_taken": [],
        "validators_run": [],
        "validators_failed": [],
        "repair_actions_applied": [],
    }
    escalated_chain = {
        "control_chain_decision": {"control_signals": {}},
        "continuation_allowed": False,
        "primary_reason_code": "escalation_required",
        "schema_errors": [],
        "enforcement_result": None,
        "gating_result": None,
        "execution_result": escalated_exec,
    }
    with patch(
        "spectrum_systems.modules.runtime.control_integration.run_control_chain",
        return_value=escalated_chain,
    ):
        result = enforce_control_before_execution(_ctx())
    assert result["escalation_triggered"] is True
    assert result["continuation_allowed"] is False


# ---------------------------------------------------------------------------
# H.7 — human_review_required produces a structured requirement
# ---------------------------------------------------------------------------


def test_human_review_required_produces_structured_task():
    review_exec = {
        "execution_status": "success",
        "publication_blocked": False,
        "decision_blocked": False,
        "rerun_triggered": False,
        "escalation_triggered": False,
        "human_review_required": True,
        "actions_taken": [],
        "validators_run": [],
        "validators_failed": [],
        "repair_actions_applied": [],
    }
    review_chain = {
        "control_chain_decision": {"control_signals": {}},
        "continuation_allowed": True,
        "primary_reason_code": "continue",
        "schema_errors": [],
        "enforcement_result": None,
        "gating_result": None,
        "execution_result": review_exec,
    }
    with patch(
        "spectrum_systems.modules.runtime.control_integration.run_control_chain",
        return_value=review_chain,
    ):
        result = enforce_control_before_execution(_ctx())
    assert result["human_review_required"] is True
    assert "human_review_task" in result
    task = result["human_review_task"]
    assert task["task_type"] == "human_review_required"
    assert "execution_id" in task


# ---------------------------------------------------------------------------
# H.8 — integration is idempotent
# ---------------------------------------------------------------------------


def test_integration_is_idempotent():
    ctx = _ctx()
    first = enforce_control_before_execution(ctx)
    second = enforce_control_before_execution(ctx)
    # Status and key flags must be identical across runs (execution_id may differ)
    for key in ("execution_status", "continuation_allowed", "publication_blocked", "decision_blocked"):
        assert first[key] == second[key], f"Mismatch for {key}"


# ---------------------------------------------------------------------------
# H.9 — execution_result is not re-derived downstream
# ---------------------------------------------------------------------------


def test_execution_result_is_not_re_derived_downstream():
    """continuation_allowed must come exclusively from execution_result.execution_status."""
    # Craft a chain where chain-level continuation_allowed differs from execution_result
    success_exec = {
        "execution_status": "success",
        "publication_blocked": False,
        "decision_blocked": False,
        "rerun_triggered": False,
        "escalation_triggered": False,
        "human_review_required": False,
        "actions_taken": [],
        "validators_run": [],
        "validators_failed": [],
        "repair_actions_applied": [],
    }
    chain = {
        "control_chain_decision": {"control_signals": {}},
        "continuation_allowed": False,  # chain says blocked…
        "primary_reason_code": "continue",
        "schema_errors": [],
        "enforcement_result": None,
        "gating_result": None,
        "execution_result": success_exec,  # …but execution_result says success
    }
    with patch(
        "spectrum_systems.modules.runtime.control_integration.run_control_chain",
        return_value=chain,
    ):
        result = enforce_control_before_execution(_ctx())
    # Must follow execution_result, not chain-level flag
    assert result["continuation_allowed"] is True


# ---------------------------------------------------------------------------
# H.10 — bypass attempts fail closed
# ---------------------------------------------------------------------------


def test_bypass_attempts_fail_closed_missing_context_keys():
    # Omit required keys → must block
    result = enforce_control_before_execution({"artifact": {}})
    assert result["continuation_allowed"] is False
    assert result["execution_status"] == "blocked"


def test_bypass_attempts_fail_closed_non_dict_context():
    result = enforce_control_before_execution("not a dict")  # type: ignore[arg-type]
    assert result["continuation_allowed"] is False


def test_bypass_blocked_result_sentinel_is_fully_closed():
    assert _BYPASS_BLOCKED_RESULT["continuation_allowed"] is False
    assert _BYPASS_BLOCKED_RESULT["publication_blocked"] is True
    assert _BYPASS_BLOCKED_RESULT["decision_blocked"] is True


# ---------------------------------------------------------------------------
# H.11 — adapters preserve original function signatures
# ---------------------------------------------------------------------------


def test_simulation_adapter_preserves_signature():
    """run_simulation_with_control passes args/kwargs to sim_fn unchanged."""
    received: Dict[str, Any] = {}

    def my_sim(a, b, c=None):
        received.update({"a": a, "b": b, "c": c})
        return "sim_ok"

    sim_result, integration = run_simulation_with_control(
        _ctx(), my_sim, 1, 2, c="three"
    )
    assert integration["continuation_allowed"] is True
    assert sim_result == "sim_ok"
    assert received == {"a": 1, "b": 2, "c": "three"}


def test_working_paper_adapter_preserves_signature():
    """generate_working_paper_with_control passes args/kwargs to gen_fn unchanged."""
    received: Dict[str, Any] = {}

    def my_gen(transcript, *, include_summary=True):
        received.update({"transcript": transcript, "include_summary": include_summary})
        return {"paper": "done"}

    paper, integration = generate_working_paper_with_control(
        _ctx(), my_gen, {"text": "hello"}, include_summary=False
    )
    assert integration["continuation_allowed"] is True
    assert paper == {"paper": "done"}
    assert received == {"transcript": {"text": "hello"}, "include_summary": False}


# ---------------------------------------------------------------------------
# H.12 — integration works with multiple stages
# ---------------------------------------------------------------------------


def test_integration_works_across_multiple_stages():
    for stage in ("observe", "interpret", "recommend", "synthesis", "export"):
        result = enforce_control_before_execution(
            {
                "artifact": _passing_artifact(),
                "stage": stage,
                "runtime_environment": "test",
            }
        )
        assert "continuation_allowed" in result, f"Missing continuation_allowed for stage={stage}"
        assert "execution_status" in result


# ---------------------------------------------------------------------------
# H.13 — CLI enforces control when enabled (--enforce-control)
# ---------------------------------------------------------------------------


def test_cli_enforce_control_flag_blocks_when_chain_blocked(tmp_path, capsys):
    """The --enforce-control flag must surface a blocked integration result."""
    import json
    from scripts.run_slo_control_chain import main as cc_main

    artifact_path = tmp_path / "blocked.json"
    artifact_path.write_text(json.dumps(_blocked_artifact()), encoding="utf-8")
    output_path = tmp_path / "decision.json"

    code = cc_main(
        [
            str(artifact_path),
            "--stage", "synthesis",
            "--enforce-control",
            "--output", str(output_path),
        ]
    )
    out = capsys.readouterr().out
    assert code == 2  # blocked exit code
    assert "BN.7" in out or "Control Integration" in out


def test_cli_enforce_control_flag_proceeds_when_chain_allows(tmp_path, capsys):
    """The --enforce-control flag must allow execution and print integration summary."""
    import json
    from scripts.run_slo_control_chain import main as cc_main

    artifact_path = tmp_path / "passing.json"
    artifact_path.write_text(json.dumps(_passing_artifact()), encoding="utf-8")
    output_path = tmp_path / "decision.json"

    code = cc_main(
        [
            str(artifact_path),
            "--stage", "synthesis",
            "--enforce-control",
            "--output", str(output_path),
        ]
    )
    out = capsys.readouterr().out
    assert code in {0, 1}
    assert "BN.7" in out or "Control Integration" in out


# ---------------------------------------------------------------------------
# H.14 — control_chain is always called before execution
# ---------------------------------------------------------------------------


def test_control_chain_is_always_called_before_execution():
    """enforce_control_before_execution must invoke run_control_chain."""
    with patch(
        "spectrum_systems.modules.runtime.control_integration.run_control_chain",
    ) as mock_chain:
        mock_chain.return_value = {
            "control_chain_decision": {"control_signals": {}},
            "continuation_allowed": True,
            "primary_reason_code": "continue",
            "schema_errors": [],
            "enforcement_result": None,
            "gating_result": None,
            "execution_result": {
                "execution_status": "success",
                "publication_blocked": False,
                "decision_blocked": False,
                "rerun_triggered": False,
                "escalation_triggered": False,
                "human_review_required": False,
                "actions_taken": [],
                "validators_run": [],
                "validators_failed": [],
                "repair_actions_applied": [],
            },
        }
        enforce_control_before_execution(_ctx())
        mock_chain.assert_called_once()
        _, call_kwargs = mock_chain.call_args
        assert call_kwargs.get("execute") is True, "run_control_chain must be called with execute=True"


# ---------------------------------------------------------------------------
# H.15 — execution cannot proceed without control_signals
# ---------------------------------------------------------------------------


def test_execution_cannot_proceed_without_control_signals():
    """When execution_result is absent/empty, continuation must be blocked."""
    chain_no_exec_result = {
        "control_chain_decision": {"control_signals": {}},
        "continuation_allowed": True,
        "primary_reason_code": "continue",
        "schema_errors": [],
        "enforcement_result": None,
        "gating_result": None,
        # execution_result deliberately absent
    }
    with patch(
        "spectrum_systems.modules.runtime.control_integration.run_control_chain",
        return_value=chain_no_exec_result,
    ):
        result = enforce_control_before_execution(_ctx())
    # Missing execution_result → execution_status defaults to "blocked"
    assert result["continuation_allowed"] is False


# ---------------------------------------------------------------------------
# Observability — summarize_control_integration
# ---------------------------------------------------------------------------


def test_summarize_control_integration_is_structured():
    ctx = _ctx()
    result = enforce_control_before_execution(ctx)
    summary = summarize_control_integration(ctx, result)
    assert "BN.7" in summary
    assert "continuation_allowed" in summary
    assert "execution_status" in summary


# ---------------------------------------------------------------------------
# Integration result always contains execution_result
# ---------------------------------------------------------------------------


def test_integration_result_always_contains_execution_result():
    result = enforce_control_before_execution(_ctx())
    assert "execution_result" in result
    assert isinstance(result["execution_result"], dict)


# ---------------------------------------------------------------------------
# Simulation adapter proceeds when allowed
# ---------------------------------------------------------------------------


def test_simulation_adapter_proceeds_when_allowed():
    def sim_fn():
        return "simulation_output"

    sim_result, integration = run_simulation_with_control(_ctx(), sim_fn)
    assert integration["continuation_allowed"] is True
    assert sim_result == "simulation_output"


# ---------------------------------------------------------------------------
# Working paper adapter proceeds when allowed
# ---------------------------------------------------------------------------


def test_working_paper_adapter_proceeds_when_allowed():
    def gen_fn():
        return {"paper": "content"}

    paper, integration = generate_working_paper_with_control(_ctx(), gen_fn)
    assert integration["continuation_allowed"] is True
    assert paper == {"paper": "content"}


# ---------------------------------------------------------------------------
# Exception handling — ContractRuntimeError propagates (fail-closed)
# ---------------------------------------------------------------------------


def test_enforce_control_propagates_contract_runtime_error():
    """If run_control_chain raises ContractRuntimeError, it must not be swallowed."""
    from spectrum_systems.modules.runtime.contract_runtime import ContractRuntimeError

    with patch(
        "spectrum_systems.modules.runtime.control_integration.run_control_chain",
        side_effect=ContractRuntimeError("jsonschema unavailable"),
    ):
        try:
            enforce_control_before_execution(_ctx())
            # If no exception was raised, that's also acceptable if the module
            # returns a blocked result instead of propagating — verify blocked.
            assert False, "ContractRuntimeError should propagate"
        except ContractRuntimeError:
            pass  # expected — fail-closed behaviour confirmed


def test_cli_enforce_control_handles_contract_runtime_error(tmp_path, capsys):
    """CLI --enforce-control returns EXIT_ERROR when ContractRuntimeError is raised."""
    import json
    from spectrum_systems.modules.runtime.contract_runtime import ContractRuntimeError
    from scripts.run_slo_control_chain import main as cc_main

    artifact_path = tmp_path / "passing.json"
    artifact_path.write_text(json.dumps(_passing_artifact()), encoding="utf-8")
    output_path = tmp_path / "decision.json"

    # The CLI imports enforce_control_before_execution into its own namespace,
    # so we must patch the reference there.
    with patch(
        "scripts.run_slo_control_chain.enforce_control_before_execution",
        side_effect=ContractRuntimeError("contract runtime unavailable"),
    ):
        code = cc_main(
            [
                str(artifact_path),
                "--stage", "synthesis",
                "--enforce-control",
                "--output", str(output_path),
            ]
        )
    assert code == 3  # EXIT_ERROR
