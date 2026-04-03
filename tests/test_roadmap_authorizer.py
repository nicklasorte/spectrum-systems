from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.contracts import load_example, load_schema  # noqa: E402
from spectrum_systems.modules.runtime.roadmap_authorizer import (  # noqa: E402
    authorize_selected_batch,
    read_roadmap_execution_authorization,
    validate_roadmap_execution_authorization,
    write_roadmap_execution_authorization,
)
from spectrum_systems.modules.runtime.roadmap_selector import build_roadmap_selection_result  # noqa: E402


def _roadmap() -> dict:
    artifact = copy.deepcopy(load_example("roadmap_artifact"))
    for batch in artifact["batches"]:
        if batch["batch_id"] == "BATCH-H":
            batch["status"] = "completed"
    artifact["current_batch_id"] = "BATCH-I"
    return artifact


def _selection(*, ready: bool = True, missing_signal: bool = False) -> dict:
    signals = {
        "signals": ["roadmap_authority_resolved", "executor_ingestion_valid"],
        "hard_gates": {"BATCH-G": "pass"},
        "control_loop": {"eval_present": True, "trace_present": True, "schema_valid": True},
    }
    if missing_signal:
        signals["signals"] = ["roadmap_authority_resolved"]
    result = build_roadmap_selection_result(_roadmap(), signals, evaluated_at="2026-04-03T13:00:00Z")
    if not ready:
        result["ready_to_run"] = False
        result["reason_codes"] = ["REQUIRED_SIGNAL_MISSING"]
    return result


def _auth_signals() -> dict:
    return {
        "trace_id": "trace-rdx-003-test",
        "required_signals_satisfied": True,
        "hard_gate_state": "pass",
        "certification_state": "complete",
        "review_state": "complete",
        "eval_state": "complete",
        "replay_consistency": "match",
        "control_freeze_condition": False,
        "control_block_condition": False,
        "warning_states": [],
        "source_refs": [
            "contracts/examples/roadmap_artifact.json",
            "contracts/examples/roadmap_selection_result.json",
        ],
    }


def test_allow_path_authorizes_selected_batch() -> None:
    result = authorize_selected_batch(_roadmap(), _selection(), _auth_signals(), evaluated_at="2026-04-03T13:30:00Z")
    assert result["control_decision"] == "allow"
    assert result["authorized_to_run"] is True
    assert result["reason_codes"] == ["AUTHORIZED"]


def test_warn_path_is_deterministic_and_authorized() -> None:
    signals = _auth_signals()
    signals["warning_states"] = ["minor_signal_delay"]
    first = authorize_selected_batch(_roadmap(), _selection(), signals, evaluated_at="2026-04-03T13:30:00Z")
    second = authorize_selected_batch(_roadmap(), _selection(), signals, evaluated_at="2026-04-03T13:30:00Z")
    assert first == second
    assert first["control_decision"] == "warn"
    assert first["authorized_to_run"] is True
    assert "AUTHORIZED_WITH_WARNINGS" in first["reason_codes"]


def test_freeze_on_replay_mismatch() -> None:
    signals = _auth_signals()
    signals["replay_consistency"] = "mismatch"
    result = authorize_selected_batch(_roadmap(), _selection(), signals, evaluated_at="2026-04-03T13:30:00Z")
    assert result["control_decision"] == "freeze"
    assert result["authorized_to_run"] is False
    assert "REPLAY_MISMATCH" in result["reason_codes"]


def test_block_on_missing_required_signal_or_invalid_selection() -> None:
    signals = _auth_signals()
    signals["required_signals_satisfied"] = False
    selection = _selection(ready=False)
    result = authorize_selected_batch(_roadmap(), selection, signals, evaluated_at="2026-04-03T13:30:00Z")
    assert result["control_decision"] == "block"
    assert result["authorized_to_run"] is False
    assert "MISSING_REQUIRED_SIGNAL" in result["reason_codes"]
    assert "BATCH_NOT_READY" in result["reason_codes"]


def test_block_on_unmet_hard_gate_invalid_roadmap_and_cert_required() -> None:
    signals = _auth_signals()
    signals["hard_gate_state"] = "fail"
    signals["certification_state"] = "required"

    roadmap = _roadmap()
    roadmap.pop("roadmap_id")

    result = authorize_selected_batch(roadmap, _selection(), signals, evaluated_at="2026-04-03T13:30:00Z")
    assert result["control_decision"] == "block"
    assert result["authorized_to_run"] is False
    assert "HARD_GATE_UNMET" in result["reason_codes"]
    assert "CERTIFICATION_REQUIRED" in result["reason_codes"]
    assert "INVALID_ROADMAP_ARTIFACT" in result["reason_codes"]


def test_non_execution_boundary_does_not_mutate_roadmap() -> None:
    roadmap = _roadmap()
    before = copy.deepcopy(roadmap)
    authorize_selected_batch(roadmap, _selection(), _auth_signals(), evaluated_at="2026-04-03T13:30:00Z")
    assert roadmap == before


def test_storage_and_schema_validation_helpers_round_trip(tmp_path: Path) -> None:
    payload = authorize_selected_batch(_roadmap(), _selection(), _auth_signals(), evaluated_at="2026-04-03T13:30:00Z")
    validate_roadmap_execution_authorization(payload)

    out = write_roadmap_execution_authorization(payload, tmp_path / "roadmap_execution_authorization.json")
    loaded = read_roadmap_execution_authorization(out)
    assert loaded == payload


def test_contract_example_and_generated_payload_validate() -> None:
    example = load_example("roadmap_execution_authorization")
    schema = load_schema("roadmap_execution_authorization")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    validator.validate(example)

    generated = authorize_selected_batch(_roadmap(), _selection(), _auth_signals(), evaluated_at="2026-04-03T13:30:00Z")
    validator.validate(generated)
    assert json.loads(json.dumps(generated, sort_keys=True)) == generated
