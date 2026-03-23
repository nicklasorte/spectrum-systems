"""Tests for BN.6.1 — Contract Runtime Enforcement.

Proves that:
1.  Missing jsonschema fails closed (ContractRuntimeError raised).
2.  run_control_chain refuses to run without contract runtime.
3.  execute_control_signals refuses to run without contract runtime.
4.  CLI exits 3 when contract runtime is unavailable.
5.  Error message is deterministic.
6.  No artifact is emitted that falsely implies validation succeeded.
7.  Normal behavior still works when contract runtime is available.
8.  Backward compatibility is preserved when dependency exists.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.contract_runtime import (  # noqa: E402
    FAILURE_REASON,
    ContractRuntimeError,
    ensure_contract_runtime_available,
    format_contract_runtime_error,
    get_contract_runtime_status,
)
from spectrum_systems.modules.runtime.control_executor import (  # noqa: E402
    execute_control_signals,
)
from spectrum_systems.modules.runtime.control_chain import (  # noqa: E402
    run_control_chain,
)
from spectrum_systems.modules.runtime.trace_engine import start_trace  # noqa: E402
from scripts.run_slo_control_chain import main as cc_main  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _simulate_missing_jsonschema():
    """Context manager that makes jsonschema appear missing."""
    return patch(
        "spectrum_systems.modules.runtime.contract_runtime.get_contract_runtime_status",
        return_value={
            "available": False,
            "package": "jsonschema",
            "version": None,
            "failure_reason": FAILURE_REASON,
            "error": "No module named 'jsonschema'",
        },
    )


def _base_evaluation() -> Dict[str, Any]:
    return {
        "evaluation_id": "EVAL-BN61",
        "artifact_id": "ART-BN61",
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


def _base_signals(**overrides: Any) -> Dict[str, Any]:
    base = {
        "continuation_mode": "continue",
        "required_inputs": [],
        "required_validators": [],
        "repair_actions": [],
        "rerun_recommended": False,
        "human_review_required": False,
        "escalation_required": False,
        "publication_allowed": True,
        "decision_grade_allowed": True,
        "traceability_required": False,
        "control_signal_reason_codes": [],
    }
    base.update(overrides)
    return base


def _governed_context(**overrides: Any) -> Dict[str, Any]:
    ctx = {
        "artifact": {"artifact_id": "artifact-source-001"},
        "trace_id": start_trace({"source": "tests/test_contract_runtime_enforcement.py", "case": "governed"}),
        "run_id": "run-test-001",
    }
    ctx.update(overrides)
    return ctx


# ---------------------------------------------------------------------------
# 1. get_contract_runtime_status returns correct shape when available
# ---------------------------------------------------------------------------

class TestGetContractRuntimeStatus:
    def test_available_when_jsonschema_installed(self):
        status = get_contract_runtime_status()
        assert status["available"] is True
        assert status["package"] == "jsonschema"
        assert status["failure_reason"] is None
        assert status["error"] is None

    def test_version_is_string_when_available(self):
        status = get_contract_runtime_status()
        if status["available"]:
            assert isinstance(status["version"], str)

    def test_unavailable_status_structure(self):
        import sys
        from unittest.mock import patch
        # Simulate missing jsonschema by temporarily replacing it in sys.modules
        with patch.dict(sys.modules, {"jsonschema": None}):  # type: ignore[dict-item]
            import spectrum_systems.modules.runtime.contract_runtime as _cr
            status = _cr.get_contract_runtime_status()
        assert status["available"] is False
        assert status["failure_reason"] == FAILURE_REASON
        assert status["error"] is not None


# ---------------------------------------------------------------------------
# 2. format_contract_runtime_error is deterministic
# ---------------------------------------------------------------------------

class TestFormatContractRuntimeError:
    def test_deterministic_for_same_status(self):
        status = {
            "available": False,
            "package": "jsonschema",
            "version": None,
            "failure_reason": FAILURE_REASON,
            "error": "No module named 'jsonschema'",
        }
        msg1 = format_contract_runtime_error(status)
        msg2 = format_contract_runtime_error(status)
        assert msg1 == msg2

    def test_contains_key_phrases(self):
        status = {
            "available": False,
            "package": "jsonschema",
            "version": None,
            "failure_reason": FAILURE_REASON,
            "error": "No module named 'jsonschema'",
        }
        msg = format_contract_runtime_error(status)
        assert "Contract enforcement is unavailable" in msg
        assert "jsonschema" in msg

    def test_includes_install_hint(self):
        status = {
            "available": False,
            "package": "jsonschema",
            "version": None,
            "failure_reason": FAILURE_REASON,
            "error": "No module named 'jsonschema'",
        }
        msg = format_contract_runtime_error(status)
        assert "pip install jsonschema" in msg

    def test_available_status_returns_confirmation(self):
        status = get_contract_runtime_status()
        msg = format_contract_runtime_error(status)
        assert "available" in msg


# ---------------------------------------------------------------------------
# 3. ensure_contract_runtime_available fails closed when missing
# ---------------------------------------------------------------------------

class TestEnsureContractRuntimeAvailable:
    def test_raises_contract_runtime_error_when_unavailable(self):
        with _simulate_missing_jsonschema():
            with pytest.raises(ContractRuntimeError) as exc_info:
                ensure_contract_runtime_available()
        assert exc_info.value.failure_reason == FAILURE_REASON

    def test_error_message_is_deterministic(self):
        with _simulate_missing_jsonschema():
            try:
                ensure_contract_runtime_available()
            except ContractRuntimeError as e:
                msg1 = str(e)

        with _simulate_missing_jsonschema():
            try:
                ensure_contract_runtime_available()
            except ContractRuntimeError as e:
                msg2 = str(e)

        assert msg1 == msg2

    def test_succeeds_when_available(self):
        status = ensure_contract_runtime_available()
        assert status["available"] is True

    def test_payload_has_failure_reason(self):
        with _simulate_missing_jsonschema():
            with pytest.raises(ContractRuntimeError) as exc_info:
                ensure_contract_runtime_available()
        payload = exc_info.value.as_payload()
        assert payload["failure_reason"] == FAILURE_REASON
        assert "message" in payload


# ---------------------------------------------------------------------------
# 4. run_control_chain refuses to run without contract runtime (Test 2)
# ---------------------------------------------------------------------------

class TestControlChainContractRuntimeEnforcement:
    def test_raises_when_contract_runtime_unavailable(self):
        with _simulate_missing_jsonschema():
            with pytest.raises(ContractRuntimeError):
                run_control_chain(_base_evaluation())

    def test_no_artifact_emitted_when_contract_runtime_unavailable(self):
        """Verify that no artifact claiming validation succeeded is returned."""
        caught = False
        result = None
        with _simulate_missing_jsonschema():
            try:
                result = run_control_chain(_base_evaluation())
            except ContractRuntimeError:
                caught = True
        assert caught, "ContractRuntimeError should have been raised"
        assert result is None, "No artifact should be returned when runtime is unavailable"

    def test_works_normally_when_contract_runtime_available(self):
        """Backward compatibility: normal operation when jsonschema is present."""
        result = run_control_chain(_base_evaluation())
        assert "control_chain_decision" in result
        assert "continuation_allowed" in result

    def test_error_message_contains_failure_reason(self):
        with _simulate_missing_jsonschema():
            with pytest.raises(ContractRuntimeError) as exc_info:
                run_control_chain(_base_evaluation())
        assert FAILURE_REASON in exc_info.value.as_payload()["failure_reason"]


# ---------------------------------------------------------------------------
# 5. execute_control_signals refuses to run without contract runtime (Test 3)
# ---------------------------------------------------------------------------

class TestControlExecutorContractRuntimeEnforcement:
    def test_raises_when_contract_runtime_unavailable(self):
        signals = _base_signals()
        with _simulate_missing_jsonschema():
            with pytest.raises(ContractRuntimeError):
                execute_control_signals(signals, {})

    def test_no_artifact_emitted_when_contract_runtime_unavailable(self):
        signals = _base_signals()
        caught = False
        result = None
        with _simulate_missing_jsonschema():
            try:
                result = execute_control_signals(signals, {})
            except ContractRuntimeError:
                caught = True
        assert caught
        assert result is None

    def test_works_normally_when_contract_runtime_available(self):
        signals = _base_signals()
        result = execute_control_signals(signals, _governed_context(artifact={"artifact_id": "ART-1"}))
        assert result["execution_status"] == "success"


# ---------------------------------------------------------------------------
# 6. CLI exits 3 when contract runtime is unavailable (Test 4)
# ---------------------------------------------------------------------------

class TestCLIContractRuntimeEnforcement:
    def test_cli_exits_3_when_contract_runtime_unavailable(self, tmp_path: Path):
        artifact_path = tmp_path / "eval.json"
        artifact_path.write_text(json.dumps(_base_evaluation()), encoding="utf-8")

        with _simulate_missing_jsonschema():
            exit_code = cc_main([str(artifact_path)])

        assert exit_code == 3

    def test_cli_succeeds_when_contract_runtime_available(self, tmp_path: Path):
        artifact_path = tmp_path / "eval.json"
        artifact_path.write_text(json.dumps(_base_evaluation()), encoding="utf-8")

        exit_code = cc_main([str(artifact_path), "--stage", "observe"])
        assert exit_code in {0, 1, 2}

    def test_cli_emits_contract_runtime_diagnostics_line(
        self, tmp_path: Path, capsys
    ):
        artifact_path = tmp_path / "eval.json"
        artifact_path.write_text(json.dumps(_base_evaluation()), encoding="utf-8")

        cc_main([str(artifact_path), "--stage", "observe"])
        captured = capsys.readouterr()
        assert "contract runtime" in captured.out

    def test_cli_error_message_when_unavailable(self, tmp_path: Path, capsys):
        artifact_path = tmp_path / "eval.json"
        artifact_path.write_text(json.dumps(_base_evaluation()), encoding="utf-8")

        with _simulate_missing_jsonschema():
            cc_main([str(artifact_path)])
        captured = capsys.readouterr()
        # The stderr should contain a clear error message
        assert "Contract enforcement is unavailable" in captured.err or \
               "contract_runtime_unavailable" in captured.err or \
               "jsonschema" in captured.err


# ---------------------------------------------------------------------------
# 7. No artifact falsely claims validation succeeded (Test 6)
# ---------------------------------------------------------------------------

class TestNoFalseValidationClaims:
    def test_control_chain_no_artifact_on_runtime_failure(self):
        """When runtime is unavailable, no artifact with schema_errors=[] is produced."""
        with _simulate_missing_jsonschema():
            try:
                result = run_control_chain(_base_evaluation())
                # If we reach here (shouldn't), artifact must not claim validation OK
                cd = result.get("control_chain_decision", {})
                assert cd.get("schema_validated") is not True
            except ContractRuntimeError:
                pass  # expected

    def test_executor_no_artifact_on_runtime_failure(self):
        """When runtime is unavailable, no execution result is returned."""
        with _simulate_missing_jsonschema():
            try:
                result = execute_control_signals(_base_signals(), {})
                assert result is None, "No result should be returned"
            except ContractRuntimeError:
                pass  # expected


# ---------------------------------------------------------------------------
# 8. Backward compatibility when dependency exists (Test 8)
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    def test_run_control_chain_returns_expected_keys(self):
        result = run_control_chain(_base_evaluation())
        assert set(result.keys()) >= {
            "control_chain_decision",
            "continuation_allowed",
            "primary_reason_code",
            "schema_errors",
        }

    def test_execute_control_signals_returns_expected_keys(self):
        with pytest.raises(RuntimeError, match="missing_or_placeholder_correlation_keys:trace_id,run_id,source_artifact_id"):
            execute_control_signals(_base_signals(), {})

    def test_contract_runtime_error_is_runtime_error_subclass(self):
        err = ContractRuntimeError("test")
        assert isinstance(err, RuntimeError)

    def test_failure_reason_constant_value(self):
        assert FAILURE_REASON == "contract_runtime_unavailable"
