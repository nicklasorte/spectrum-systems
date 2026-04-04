from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.contracts import load_example, load_schema  # noqa: E402
from spectrum_systems.modules.runtime.roadmap_selector import (  # noqa: E402
    build_roadmap_selection_result,
    select_next_batch,
    validate_batch_readiness,
    validate_roadmap_against_program,
)


def _roadmap() -> dict:
    artifact = copy.deepcopy(load_example("roadmap_artifact"))
    # RDX-002 should operate after RDX-001 completion.
    for batch in artifact["batches"]:
        if batch["batch_id"] == "BATCH-H":
            batch["status"] = "completed"
    artifact["current_batch_id"] = "BATCH-I"
    return artifact


def _signals(*, include_required: bool = True) -> dict:
    signals = ["roadmap_authority_resolved"]
    if include_required:
        signals.append("executor_ingestion_valid")
    return {
        "signals": signals,
        "hard_gates": {"BATCH-G": "pass"},
        "control_loop": {
            "eval_present": True,
            "trace_present": True,
            "schema_valid": True,
        },
    }


def test_correct_next_batch_selected_and_ready_true() -> None:
    roadmap = _roadmap()
    signals = _signals()

    assert select_next_batch(roadmap, signals) == "BATCH-I"

    result = build_roadmap_selection_result(roadmap, signals, evaluated_at="2026-04-03T13:00:00Z")
    assert result["selected_batch_id"] == "BATCH-I"
    assert result["ready_to_run"] is True
    assert result["stop_reason"] is None
    assert result["stop_reason_codes"] == []
    assert result["reason_codes"] == ["READY_TO_RUN"]
    assert result["blocking_conditions"] == []


def test_missing_signal_blocks_readiness() -> None:
    roadmap = _roadmap()
    signals = _signals(include_required=False)

    assert select_next_batch(roadmap, signals) is None
    result = build_roadmap_selection_result(roadmap, signals, evaluated_at="2026-04-03T13:00:00Z")
    assert result["ready_to_run"] is False
    assert result["stop_reason"] == "missing_required_signal"
    assert "REQUIRED_SIGNAL_MISSING" in result["reason_codes"]
    assert any("missing required signals" in row for row in result["blocking_conditions"])


def test_dependency_incomplete_not_ready() -> None:
    roadmap = _roadmap()
    # Keep dependency batch H unfinished; I cannot be selected.
    for batch in roadmap["batches"]:
        if batch["batch_id"] == "BATCH-H":
            batch["status"] = "running"

    signals = _signals()
    assert select_next_batch(roadmap, signals) is None

    result = build_roadmap_selection_result(roadmap, signals, evaluated_at="2026-04-03T13:00:00Z")
    assert result["ready_to_run"] is False
    assert result["stop_reason"] == "no_eligible_batch"
    assert result["reason_codes"] == ["NO_ELIGIBLE_BATCH"]


def test_no_eligible_batch_returns_explicit_state() -> None:
    roadmap = _roadmap()
    for batch in roadmap["batches"]:
        if batch["status"] == "not_started":
            batch["status"] = "blocked"

    result = build_roadmap_selection_result(roadmap, _signals(), evaluated_at="2026-04-03T13:00:00Z")
    assert result["selected_batch_id"] is None
    assert result["ready_to_run"] is False
    assert result["stop_reason"] == "no_eligible_batch"
    assert result["reason_codes"] == ["NO_ELIGIBLE_BATCH"]


def test_multiple_candidates_choose_deterministic_list_order() -> None:
    roadmap = _roadmap()
    for batch in roadmap["batches"]:
        if batch["batch_id"] in {"BATCH-I", "BATCH-J"}:
            batch["status"] = "not_started"
    for batch in roadmap["batches"]:
        if batch["batch_id"] == "BATCH-J":
            batch["depends_on"] = []
            batch["required_signals"] = []

    assert select_next_batch(roadmap, _signals()) == "BATCH-I"


def test_determinism_same_inputs_identical_result() -> None:
    roadmap = _roadmap()
    signals = _signals()

    first = build_roadmap_selection_result(roadmap, signals, evaluated_at="2026-04-03T13:00:00Z")
    second = build_roadmap_selection_result(roadmap, signals, evaluated_at="2026-04-03T13:00:00Z")
    assert first == second


def test_validate_batch_readiness_fail_closed_on_ambiguous_state() -> None:
    readiness = validate_batch_readiness({"required_signals": ["x"]}, _signals())
    assert readiness["ready_to_run"] is False
    assert "AMBIGUOUS_STATE" in readiness["readiness_reason_codes"]


def test_example_validates_against_schema() -> None:
    payload = load_example("roadmap_selection_result")
    validator = Draft202012Validator(load_schema("roadmap_selection_result"), format_checker=FormatChecker())
    validator.validate(payload)


def test_generated_result_validates_against_schema() -> None:
    result = build_roadmap_selection_result(_roadmap(), _signals(), evaluated_at="2026-04-03T13:00:00Z")
    Draft202012Validator(load_schema("roadmap_selection_result"), format_checker=FormatChecker()).validate(result)
    assert json.loads(json.dumps(result, sort_keys=True)) == result


def test_validate_roadmap_against_program_valid_alignment() -> None:
    result = validate_roadmap_against_program(
        _roadmap(),
        {
            "program_id": "PRG-ROADMAP-EXECUTION",
            "program_version": "1.0.0",
            "allowed_targets": [],
            "disallowed_targets": [],
            "priority_ordering": ["BATCH-I", "BATCH-J", "BATCH-K"],
            "success_criteria": ["Constrain MAP and RDX output"],
            "blocking_conditions": [],
            "enforcement_mode": "block",
            "created_at": "2026-04-04T00:00:00Z",
            "trace_id": "trace-rdx-selector-001",
        },
    )
    assert result["alignment_status"] == "aligned"
    assert result["fail_closed"] is False


def test_validate_roadmap_against_program_fails_closed_on_disallowed_target() -> None:
    roadmap = _roadmap()
    for batch in roadmap["batches"]:
        if batch["batch_id"] == "BATCH-I":
            batch["batch_id"] = "BATCH-Z"
            break

    result = validate_roadmap_against_program(
        roadmap,
        {
            "program_id": "PRG-ROADMAP-EXECUTION",
            "program_version": "1.0.0",
            "allowed_targets": ["BATCH-I", "BATCH-J"],
            "disallowed_targets": ["BATCH-Z"],
            "priority_ordering": ["BATCH-I", "BATCH-J"],
            "success_criteria": ["Constrain MAP and RDX output"],
            "blocking_conditions": [],
            "enforcement_mode": "block",
            "created_at": "2026-04-04T00:00:00Z",
            "trace_id": "trace-rdx-selector-002",
        },
    )
    assert result["alignment_status"] == "invalid"
    assert result["fail_closed"] is True
    assert any(item["reason_code"] == "disallowed_target" for item in result["violations"])
