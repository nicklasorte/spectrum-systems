"""AEX-TRUST-01 — focused trust-gap hardening tests.

These tests verify that AEX's admission boundary produces the schema-bound,
replayable, observable, lineage-anchored, and SEL-consumable evidence the
TLS-03 trust-gap detector requires, and that AEX never claims authority
over enforcement / promotion / certification / control / governance
readiness / replay / lineage / observability / evaluation.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

import pytest

from spectrum_systems.aex.admission_replay import (
    AEXReplayError,
    DEFAULT_REPLAY_COMMAND,
    build_admission_replay_record,
    replay_admission,
    replay_and_verify,
)
from spectrum_systems.aex.engine import admit_codex_request
from spectrum_systems.aex.observability_emitter import (
    build_admission_evidence_record,
    build_admission_trace_record,
    derive_run_id,
    derive_span_id,
    write_admission_observability_artifacts,
)
from spectrum_systems.aex.sel_admission_signal import (
    assert_no_enforcement_authority_claim,
    build_sel_admission_input,
)
from spectrum_systems.contracts import load_schema, validate_artifact


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = REPO_ROOT / "tests" / "aex" / "fixtures"
ADMIT_FIXTURE = FIXTURES_DIR / "admission_admit_repo_write.json"
REJECT_MISSING_FIXTURE = FIXTURES_DIR / "admission_reject_missing_field.json"
REJECT_INDET_FIXTURE = FIXTURES_DIR / "admission_reject_indeterminate.json"


def _admit() -> dict[str, Any]:
    fixture = json.loads(ADMIT_FIXTURE.read_text(encoding="utf-8"))
    result = admit_codex_request(fixture)
    assert result.accepted, "fixture must admit cleanly"
    assert result.build_admission_record is not None
    assert result.normalized_execution_request is not None
    return {
        "fixture": fixture,
        "result": result,
        "build_admission_record": result.build_admission_record,
        "normalized_execution_request": result.normalized_execution_request,
    }


# ---------- Part D: happy-path admission ----------

def test_happy_path_admission_emits_schema_valid_artifacts() -> None:
    bundle = _admit()
    validate_artifact(bundle["build_admission_record"], "build_admission_record")
    validate_artifact(bundle["normalized_execution_request"], "normalized_execution_request")
    assert bundle["build_admission_record"]["admission_status"] == "accepted"
    assert bundle["build_admission_record"]["execution_type"] == "repo_write"
    assert bundle["normalized_execution_request"]["repo_mutation_requested"] is True


def test_happy_path_lineage_refs_match_across_artifacts() -> None:
    bundle = _admit()
    bar = bundle["build_admission_record"]
    nr = bundle["normalized_execution_request"]
    assert bar["request_id"] == nr["request_id"]
    assert bar["trace_id"] == nr["trace_id"]
    expected_ref = f"normalized_execution_request:{nr['request_id']}"
    assert bar["normalized_execution_request_ref"] == expected_ref


# ---------- Part D: fail-closed rejections ----------

def test_missing_required_field_fails_closed() -> None:
    fixture = json.loads(REJECT_MISSING_FIXTURE.read_text(encoding="utf-8"))
    assert "request_id" not in fixture, "fixture must omit a required field"
    result = admit_codex_request(fixture)
    assert not result.accepted
    assert result.build_admission_record is None
    rej = result.admission_rejection_record
    assert rej is not None
    validate_artifact(rej, "admission_rejection_record")
    assert "missing_required_field" in rej["rejection_reason_codes"]


def test_indeterminate_admission_fails_closed() -> None:
    fixture = json.loads(REJECT_INDET_FIXTURE.read_text(encoding="utf-8"))
    result = admit_codex_request(fixture)
    assert not result.accepted, "ambiguous prompt with repo-sensitive paths must reject"
    rej = result.admission_rejection_record
    assert rej is not None
    assert "unknown_execution_type" in rej["rejection_reason_codes"]


def test_invalid_request_shape_fails_closed() -> None:
    result = admit_codex_request("not a mapping")  # type: ignore[arg-type]
    assert not result.accepted
    rej = result.admission_rejection_record
    assert rej is not None
    assert "invalid_request_shape" in rej["rejection_reason_codes"]


# ---------- Part D: schema validation surface ----------

def test_aex_owned_artifact_schemas_load() -> None:
    """AEX-owned contract schemas load and have additionalProperties:false."""
    for name in (
        "build_admission_record",
        "normalized_execution_request",
        "admission_rejection_record",
        "admission_policy_observation",
        "admission_evidence_record",
        "admission_trace_record",
    ):
        schema = load_schema(name)
        assert schema.get("additionalProperties") is False, (
            f"{name} schema must declare additionalProperties:false"
        )


def test_supplemental_aex_schemas_present_and_strict() -> None:
    """Supplemental schemas under schemas/aex/ must exist for the schemas
    bucket (TLS-01) and must declare additionalProperties:false."""
    aex_schemas_dir = REPO_ROOT / "schemas" / "aex"
    assert aex_schemas_dir.is_dir(), "schemas/aex/ directory must exist"
    files = sorted(aex_schemas_dir.glob("aex_*.schema.json"))
    assert len(files) >= 4, f"expected ≥4 supplemental AEX schemas, found {len(files)}"
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data.get("additionalProperties") is False, (
            f"{path.name} must declare additionalProperties:false"
        )


# ---------- Part D / E: observability + lineage ----------

def test_admission_trace_record_has_trace_provenance() -> None:
    bundle = _admit()
    bar = bundle["build_admission_record"]
    nr = bundle["normalized_execution_request"]
    trace = build_admission_trace_record(
        admission_outcome="admitted",
        request_id=nr["request_id"],
        trace_id=nr["trace_id"],
        admission_artifact_ref=f"build_admission_record:{bar['admission_id']}",
        normalized_execution_request_ref=f"normalized_execution_request:{nr['request_id']}",
        downstream_refs=["PQX", "SEL", "OBS"],
        started_at="2026-04-29T12:00:00Z",
        finished_at="2026-04-29T12:00:01Z",
    )
    validate_artifact(trace, "admission_trace_record")
    assert trace["producer_authority"] == "AEX"
    assert trace["observability_owner_ref"] == "OBS"
    assert trace["trace_id"] == nr["trace_id"]
    assert trace["run_id"] == derive_run_id(request_id=nr["request_id"], trace_id=nr["trace_id"])
    assert trace["span_id"] == derive_span_id(request_id=nr["request_id"], trace_id=nr["trace_id"])


def test_admission_evidence_record_anchors_lineage_observability_replay() -> None:
    bundle = _admit()
    bar = bundle["build_admission_record"]
    nr = bundle["normalized_execution_request"]
    evidence = build_admission_evidence_record(
        admission_outcome="admitted",
        request_id=nr["request_id"],
        trace_id=nr["trace_id"],
        admission_artifact_ref=f"build_admission_record:{bar['admission_id']}",
        normalized_execution_request_ref=f"normalized_execution_request:{nr['request_id']}",
        source_request_ref=f"codex_build_request:{nr['request_id']}",
        downstream_refs=["PQX", "SEL", "OBS", "REP", "LIN"],
        input_hash="sha256:" + "0" * 64,
        output_hash="sha256:" + "1" * 64,
        replay_command_ref="scripts/replay_aex_admission.py --fixture x",
    )
    validate_artifact(evidence, "admission_evidence_record")
    assert evidence["lineage_refs"]["lineage_owner"] == "LIN"
    assert evidence["observability_refs"]["observability_owner"] == "OBS"
    assert evidence["replay_refs"]["replay_owner"] == "REP"
    assert "PQX" in evidence["downstream_refs"]


# ---------- Part D / E: SEL admission signal (enforcement INPUT, not authority) ----------

def test_sel_admission_signal_emits_consumable_observation() -> None:
    bundle = _admit()
    bar = bundle["build_admission_record"]
    nr = bundle["normalized_execution_request"]
    obs = build_sel_admission_input(
        admission_outcome="admitted",
        request_id=nr["request_id"],
        trace_id=nr["trace_id"],
        run_id=derive_run_id(request_id=nr["request_id"], trace_id=nr["trace_id"]),
        source_request_ref=f"codex_build_request:{nr['request_id']}",
        admission_artifact_ref=f"build_admission_record:{bar['admission_id']}",
        normalized_execution_request_ref=f"normalized_execution_request:{nr['request_id']}",
        reason_codes=bar["reason_codes"] or ["repo_write_signal_detected"],
        input_hash="sha256:" + "0" * 64,
        output_hash="sha256:" + "1" * 64,
        replay_command_ref="scripts/replay_aex_admission.py --fixture x",
    )
    validate_artifact(obs, "admission_policy_observation")
    assert obs["producer_authority"] == "AEX"
    assert "SEL" in obs["downstream_refs"]["consumer_systems"]
    assert "ENF" in obs["downstream_refs"]["consumer_systems"]
    # AEX must declare it does not enforce, promote, certify, control, etc.
    assert_no_enforcement_authority_claim(obs)


def test_sel_admission_signal_rejects_authority_claims() -> None:
    """Stripping any non-authority assertion must fail closed."""
    bundle = _admit()
    bar = bundle["build_admission_record"]
    nr = bundle["normalized_execution_request"]
    obs = build_sel_admission_input(
        admission_outcome="admitted",
        request_id=nr["request_id"],
        trace_id=nr["trace_id"],
        run_id=derive_run_id(request_id=nr["request_id"], trace_id=nr["trace_id"]),
        source_request_ref=f"codex_build_request:{nr['request_id']}",
        admission_artifact_ref=f"build_admission_record:{bar['admission_id']}",
        normalized_execution_request_ref=f"normalized_execution_request:{nr['request_id']}",
        reason_codes=["repo_write_signal_detected"],
        input_hash="sha256:" + "0" * 64,
        output_hash="sha256:" + "1" * 64,
        replay_command_ref="scripts/replay_aex_admission.py --fixture x",
    )
    obs["non_authority_assertions"] = [
        a for a in obs["non_authority_assertions"]
        if a != "aex_does_not_own_enforcement_authority"
    ]
    with pytest.raises(ValueError, match="non-authority assertions"):
        assert_no_enforcement_authority_claim(obs)


def test_sel_admission_signal_requires_reason_codes() -> None:
    with pytest.raises(ValueError, match="reason_codes"):
        build_sel_admission_input(
            admission_outcome="admitted",
            request_id="req-x",
            trace_id="trace-x",
            run_id="run-x" + "0" * 12,
            source_request_ref="codex_build_request:req-x",
            admission_artifact_ref="build_admission_record:adm-x",
            normalized_execution_request_ref="normalized_execution_request:req-x",
            reason_codes=[],
            input_hash="sha256:" + "0" * 64,
            output_hash="sha256:" + "1" * 64,
            replay_command_ref="scripts/replay_aex_admission.py",
        )


# ---------- Part D / F: replay support ----------

def test_admission_replay_is_deterministic_for_admit() -> None:
    record = replay_and_verify(ADMIT_FIXTURE)
    assert record["replay_status"] == "pass"
    assert record["deterministic"] is True
    assert record["replay_owner_ref"] == "REP"
    assert record["producer_authority"] == "AEX"
    assert record["replay_command"].startswith("python scripts/replay_aex_admission.py")


def test_admission_replay_is_deterministic_for_rejects() -> None:
    for fixture in (REJECT_MISSING_FIXTURE, REJECT_INDET_FIXTURE):
        record = replay_and_verify(fixture)
        assert record["replay_status"] == "pass"
        assert record["deterministic"] is True


def test_admission_replay_script_runs_and_emits_artifact(tmp_path: Path) -> None:
    out = tmp_path / "replay_record.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "replay_aex_admission.py"),
            "--fixture",
            str(ADMIT_FIXTURE),
            "--out",
            str(out),
        ],
        env={**__import__("os").environ},
        check=False,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr.decode()
    assert out.is_file()
    record = json.loads(out.read_text(encoding="utf-8"))
    assert record["artifact_type"] == "admission_replay_record"
    assert record["replay_status"] == "pass"


def test_admission_replay_missing_fixture_fails_closed(tmp_path: Path) -> None:
    bogus = tmp_path / "does_not_exist.json"
    with pytest.raises(AEXReplayError):
        replay_and_verify(bogus)


# ---------- Part D / E: lineage continuity request → admit → normalized → downstream ----------

def test_lineage_chain_request_to_admission_to_normalized_request_to_downstream() -> None:
    bundle = _admit()
    bar = bundle["build_admission_record"]
    nr = bundle["normalized_execution_request"]
    fixture = bundle["fixture"]

    # Request → admission record
    assert bar["request_id"] == fixture["request_id"]
    # Admission → normalized
    assert bar["normalized_execution_request_ref"] == f"normalized_execution_request:{nr['request_id']}"
    # Normalized → downstream PQX (AEX downstream per registry)
    evidence = build_admission_evidence_record(
        admission_outcome="admitted",
        request_id=nr["request_id"],
        trace_id=nr["trace_id"],
        admission_artifact_ref=f"build_admission_record:{bar['admission_id']}",
        normalized_execution_request_ref=f"normalized_execution_request:{nr['request_id']}",
        source_request_ref=f"codex_build_request:{fixture['request_id']}",
        downstream_refs=["PQX", "SEL", "OBS", "REP", "LIN"],
        input_hash="sha256:" + "0" * 64,
        output_hash="sha256:" + "1" * 64,
        replay_command_ref=DEFAULT_REPLAY_COMMAND.format(fixture_path=str(ADMIT_FIXTURE)),
    )
    assert "PQX" in evidence["downstream_refs"]
    assert evidence["lineage_refs"]["source_request_ref"] == f"codex_build_request:{fixture['request_id']}"


# ---------- Part D: AEX never owns SEL/ENF/GOV/REL/CDE authority ----------

@pytest.mark.parametrize(
    "owned_artifact",
    [
        "build_admission_record",
        "normalized_execution_request",
        "admission_rejection_record",
        "admission_policy_observation",
        "admission_evidence_record",
        "admission_trace_record",
    ],
)
def test_aex_artifacts_do_not_assert_downstream_authority(owned_artifact: str) -> None:
    """AEX-owned schemas must not include enforcement/control/closure/promotion
    state fields. Their presence would be an authority-shape regression."""
    schema = load_schema(owned_artifact)
    forbidden_fields = {
        "enforcement_action",
        "enforcement_decision",
        "enforcement_status",
        "control_decision",
        "closure_decision",
        "promotion_decision",
        "certification_decision",
        "policy_decision",
        "trust_policy_decision",
    }
    properties = set((schema.get("properties") or {}).keys())
    overlap = forbidden_fields & properties
    assert not overlap, (
        f"{owned_artifact} schema must not own downstream authority fields: {overlap}"
    )


def test_admission_records_never_emit_pqx_handoff_directly() -> None:
    """AEX hands off via build_admission_record + normalized_execution_request,
    not by emitting a PQX execution record. PQX retains execution authority."""
    bundle = _admit()
    bar = bundle["build_admission_record"]
    forbidden = {"pqx_slice_execution_record", "pqx_bundle_execution_record"}
    assert bar["artifact_type"] not in forbidden


# ---------- Part D: write artifacts to artifacts/aex/ for evidence attachment ----------

def test_observability_artifacts_can_be_written_under_artifacts_aex(tmp_path: Path) -> None:
    bundle = _admit()
    bar = bundle["build_admission_record"]
    nr = bundle["normalized_execution_request"]
    out_dir = tmp_path / "aex"
    paths = write_admission_observability_artifacts(
        admission_outcome="admitted",
        request_id=nr["request_id"],
        trace_id=nr["trace_id"],
        admission_artifact_ref=f"build_admission_record:{bar['admission_id']}",
        normalized_execution_request_ref=f"normalized_execution_request:{nr['request_id']}",
        source_request_ref=f"codex_build_request:{nr['request_id']}",
        downstream_refs=["PQX", "SEL", "OBS", "REP", "LIN"],
        input_hash="sha256:" + "0" * 64,
        output_hash="sha256:" + "1" * 64,
        replay_command_ref="scripts/replay_aex_admission.py --fixture x",
        out_dir=out_dir,
    )
    assert paths["trace"].is_file()
    assert paths["evidence"].is_file()
    trace = json.loads(paths["trace"].read_text(encoding="utf-8"))
    evidence = json.loads(paths["evidence"].read_text(encoding="utf-8"))
    validate_artifact(trace, "admission_trace_record")
    validate_artifact(evidence, "admission_evidence_record")
