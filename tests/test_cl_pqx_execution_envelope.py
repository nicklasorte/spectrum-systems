"""CL-07 / CL-08 / CL-09: PQX execution envelope contract, drift red team, fix pass."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.governance.core_loop_execution_envelope import (
    ExecutionEnvelopeError,
    REASON_ADMISSION_REF_MISSING,
    REASON_BAD_STATUS,
    REASON_ENVELOPE_MISSING,
    REASON_INPUT_REFS_MISSING,
    REASON_NOT_REPLAYABLE,
    REASON_OK,
    REASON_OUTPUT_HASH_MISSING,
    REASON_OUTPUT_REFS_MISSING,
    REASON_RUN_ID_MISMATCH,
    REASON_RUN_ID_MISSING,
    REASON_TRACE_ID_MISSING,
    normalize_execution_envelope,
    validate_execution_envelope,
)


def _good_envelope():
    return normalize_execution_envelope(
        run_id="r1",
        trace_id="t1",
        input_refs=["in-1"],
        output_refs=["out-1"],
        output_hash="sha256:cafebabe",
        status="ok",
        replay_ref="rpl-1",
        replayable=True,
        aex_admission_ref="adm-1",
    )


# --- CL-07 envelope tightening ------------------------------------------


def test_cl07_normalized_envelope_has_required_keys() -> None:
    env = _good_envelope()
    assert env["artifact_type"] == "pqx_core_loop_execution_envelope"
    for key in (
        "run_id", "trace_id", "input_refs", "output_refs", "output_hash",
        "status", "replay_ref", "replayable", "aex_admission_ref",
    ):
        assert key in env


def test_cl07_passing_envelope_validates() -> None:
    env = _good_envelope()
    result = validate_execution_envelope(env)
    assert result["ok"], result["violations"]
    assert result["primary_reason"] == REASON_OK


def test_cl07_passing_envelope_with_expected_ids() -> None:
    env = _good_envelope()
    result = validate_execution_envelope(env, expected_run_id="r1", expected_trace_id="t1")
    assert result["ok"], result["violations"]


# --- CL-08 red team: each drift case -----------------------------------


def test_cl08_envelope_missing_blocks() -> None:
    result = validate_execution_envelope(None)
    assert not result["ok"]
    assert result["primary_reason"] == REASON_ENVELOPE_MISSING


def test_cl08_missing_trace_id_blocks() -> None:
    env = _good_envelope()
    env["trace_id"] = ""
    result = validate_execution_envelope(env)
    assert not result["ok"]
    assert any(v["reason_code"] == REASON_TRACE_ID_MISSING for v in result["violations"])


def test_cl08_missing_run_id_blocks() -> None:
    env = _good_envelope()
    env["run_id"] = ""
    result = validate_execution_envelope(env)
    assert not result["ok"]
    assert any(v["reason_code"] == REASON_RUN_ID_MISSING for v in result["violations"])


def test_cl08_run_id_mismatch_blocks() -> None:
    env = _good_envelope()
    result = validate_execution_envelope(env, expected_run_id="other")
    assert not result["ok"]
    assert any(v["reason_code"] == REASON_RUN_ID_MISMATCH for v in result["violations"])


def test_cl08_missing_output_hash_blocks() -> None:
    env = _good_envelope()
    env["output_hash"] = ""
    result = validate_execution_envelope(env)
    assert not result["ok"]
    assert any(v["reason_code"] == REASON_OUTPUT_HASH_MISSING for v in result["violations"])


def test_cl08_missing_input_refs_blocks() -> None:
    env = _good_envelope()
    env["input_refs"] = []
    result = validate_execution_envelope(env)
    assert not result["ok"]
    assert any(v["reason_code"] == REASON_INPUT_REFS_MISSING for v in result["violations"])


def test_cl08_missing_output_refs_blocks() -> None:
    env = _good_envelope()
    env["output_refs"] = []
    result = validate_execution_envelope(env)
    assert not result["ok"]
    assert any(v["reason_code"] == REASON_OUTPUT_REFS_MISSING for v in result["violations"])


def test_cl08_unreplayable_envelope_blocks() -> None:
    env = _good_envelope()
    env["replayable"] = False
    result = validate_execution_envelope(env)
    assert not result["ok"]
    assert any(v["reason_code"] == REASON_NOT_REPLAYABLE for v in result["violations"])


def test_cl08_replay_ref_missing_blocks() -> None:
    env = _good_envelope()
    env["replay_ref"] = ""
    result = validate_execution_envelope(env)
    assert not result["ok"]
    assert any(v["reason_code"] == REASON_NOT_REPLAYABLE for v in result["violations"])


def test_cl08_bad_status_blocks() -> None:
    env = _good_envelope()
    env["status"] = "weird"
    result = validate_execution_envelope(env)
    assert not result["ok"]
    assert any(v["reason_code"] == REASON_BAD_STATUS for v in result["violations"])


def test_cl08_missing_admission_back_ref_blocks() -> None:
    env = _good_envelope()
    env["aex_admission_ref"] = ""
    result = validate_execution_envelope(env)
    assert not result["ok"]
    assert any(v["reason_code"] == REASON_ADMISSION_REF_MISSING for v in result["violations"])


# --- CL-09 fix pass ------------------------------------------------------


def test_cl09_normalize_then_validate_passes() -> None:
    env = normalize_execution_envelope(
        run_id="rX", trace_id="tX",
        input_refs=["i"], output_refs=["o"],
        output_hash="sha256:1", status="ok",
        replay_ref="rpl", replayable=True, aex_admission_ref="adm",
    )
    result = validate_execution_envelope(env, expected_run_id="rX", expected_trace_id="tX")
    assert result["ok"], result["violations"]
    assert result["primary_reason"] == REASON_OK
