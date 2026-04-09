from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.lineage_authenticity import issue_authenticity
from spectrum_systems.modules.runtime.pqx_sequence_runner import PQXSequenceRunnerError, execute_sequence_run
from spectrum_systems.modules.runtime.repo_write_lineage_guard import RepoWriteLineageGuardError, validate_repo_write_lineage


def _slice_requests() -> list[dict[str, str]]:
    return [{"slice_id": "fix-step:plan", "trace_id": "trace-repo-write"}]


def _base_lineage() -> dict[str, object]:
    return {
        "build_admission_record": {
            "artifact_type": "build_admission_record",
            "admission_id": "adm-1",
            "request_id": "req-1",
            "execution_type": "repo_write",
            "admission_status": "accepted",
            "normalized_execution_request_ref": "normalized_execution_request:req-1",
            "trace_id": "trace-repo-write",
            "created_at": "2026-04-08T00:00:00Z",
            "produced_by": "AEXEngine",
            "reason_codes": [],
            "target_scope": {"repo": "spectrum-systems", "paths": ["x"]},
        },
        "normalized_execution_request": {
            "artifact_type": "normalized_execution_request",
            "request_id": "req-1",
            "prompt_text": "modify repo",
            "execution_type": "repo_write",
            "repo_mutation_requested": True,
            "target_paths": ["x"],
            "requested_outputs": ["patch"],
            "source_prompt_kind": "codex_build_request",
            "trace_id": "trace-repo-write",
            "created_at": "2026-04-08T00:00:00Z",
            "produced_by": "AEXEngine",
        },
        "tlc_handoff_record": {
            "artifact_type": "tlc_handoff_record",
            "handoff_id": "tlc-handoff-1",
            "request_id": "req-1",
            "trace_id": "trace-repo-write",
            "created_at": "2026-04-08T00:00:00Z",
            "produced_by": "TLC",
            "build_admission_record_ref": "build_admission_record:adm-1",
            "normalized_execution_request_ref": "normalized_execution_request:req-1",
            "handoff_status": "accepted",
            "target_subsystems": ["TPA", "PQX"],
            "execution_type": "repo_write",
            "repo_mutation_requested": True,
            "reason_codes": [],
            "tlc_run_context": {
                "run_id": "tlc-aex-check",
                "branch_ref": "refs/heads/main",
                "objective": "repo mutation",
                "entry_boundary": "aex_to_tlc",
            },
            "lineage": {
                "upstream_refs": ["build_admission_record:adm-1", "normalized_execution_request:req-1"],
                "intended_path": ["TLC", "TPA", "PQX"],
            },
        },
    }


def _lineage() -> dict[str, object]:
    lineage = deepcopy(_base_lineage())
    lineage["build_admission_record"]["authenticity"] = issue_authenticity(artifact=lineage["build_admission_record"], issuer="AEX")
    lineage["normalized_execution_request"]["authenticity"] = issue_authenticity(
        artifact=lineage["normalized_execution_request"], issuer="AEX"
    )
    lineage["tlc_handoff_record"]["authenticity"] = issue_authenticity(artifact=lineage["tlc_handoff_record"], issuer="TLC")
    return lineage


def test_pqx_rejects_repo_write_without_aex_tlc_lineage(tmp_path: Path) -> None:
    with pytest.raises(PQXSequenceRunnerError, match="direct_pqx_repo_write_forbidden"):
        execute_sequence_run(
            slice_requests=_slice_requests(),
            state_path=tmp_path / "state.json",
            queue_run_id="queue-1",
            run_id="run-1",
            trace_id="trace-repo-write",
            max_slices=1,
            execution_class="repo_write",
        )


def test_pqx_rejects_repo_write_missing_trace_id(tmp_path: Path) -> None:
    lineage = _lineage()
    lineage["build_admission_record"]["trace_id"] = ""

    with pytest.raises(PQXSequenceRunnerError, match="direct_pqx_repo_write_forbidden"):
        execute_sequence_run(
            slice_requests=_slice_requests(),
            state_path=tmp_path / "state.json",
            queue_run_id="queue-1",
            run_id="run-1",
            trace_id="trace-repo-write",
            max_slices=1,
            execution_class="repo_write",
            repo_write_lineage=lineage,
        )


def test_pqx_rejects_repo_write_with_missing_authenticity(tmp_path: Path) -> None:
    lineage = _lineage()
    lineage["build_admission_record"].pop("authenticity", None)
    with pytest.raises(PQXSequenceRunnerError, match="direct_pqx_repo_write_forbidden"):
        execute_sequence_run(
            slice_requests=_slice_requests(),
            state_path=tmp_path / "state.json",
            queue_run_id="queue-1",
            run_id="run-1",
            trace_id="trace-repo-write",
            max_slices=1,
            execution_class="repo_write",
            repo_write_lineage=lineage,
        )


def test_repo_write_lineage_rejects_default_or_missing_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    lineage = _lineage()
    monkeypatch.delenv("SPECTRUM_LINEAGE_AUTH_SECRET_AEX", raising=False)
    monkeypatch.delenv("SPECTRUM_LINEAGE_AUTH_SECRET_TLC", raising=False)

    with pytest.raises(RepoWriteLineageGuardError, match="authenticity_secret_missing_for_issuer"):
        validate_repo_write_lineage(
            build_admission_record=lineage["build_admission_record"],
            normalized_execution_request=lineage["normalized_execution_request"],
            tlc_handoff_record=lineage["tlc_handoff_record"],
            expected_trace_id="trace-repo-write",
        )


def test_repo_write_lineage_rejects_wrong_issuer_key_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    lineage = _lineage()
    tampered = deepcopy(lineage)
    tampered["build_admission_record"]["authenticity"]["key_id"] = "tlc-hs256-v1"
    with pytest.raises(RepoWriteLineageGuardError, match="authenticity_issuer_key_binding_mismatch"):
        validate_repo_write_lineage(
            build_admission_record=tampered["build_admission_record"],
            normalized_execution_request=tampered["normalized_execution_request"],
            tlc_handoff_record=tampered["tlc_handoff_record"],
            expected_trace_id="trace-repo-write",
        )


def test_repo_write_lineage_rejects_forged_lineage_with_old_default_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    forged = deepcopy(_base_lineage())
    legacy_auth = {
        "issuer": "AEX",
        "key_id": "local-system-v1",
        "payload_digest": "sha256:" + ("0" * 64),
        "attestation": "0" * 64,
    }
    forged["build_admission_record"]["authenticity"] = dict(legacy_auth)
    forged["normalized_execution_request"]["authenticity"] = dict(legacy_auth)
    forged["tlc_handoff_record"]["authenticity"] = {**legacy_auth, "issuer": "TLC"}
    monkeypatch.setenv("SPECTRUM_LINEAGE_AUTH_SECRET", "spectrum-lineage-auth-secret-v1")

    with pytest.raises(RepoWriteLineageGuardError, match="schema_invalid|authenticity_issuer_key_binding_mismatch|authenticity_audience_invalid"):
        validate_repo_write_lineage(
            build_admission_record=forged["build_admission_record"],
            normalized_execution_request=forged["normalized_execution_request"],
            tlc_handoff_record=forged["tlc_handoff_record"],
            expected_trace_id="trace-repo-write",
        )


def test_repo_write_lineage_rejects_replay() -> None:
    lineage = _lineage()
    validate_repo_write_lineage(
        build_admission_record=lineage["build_admission_record"],
        normalized_execution_request=lineage["normalized_execution_request"],
        tlc_handoff_record=lineage["tlc_handoff_record"],
        expected_trace_id="trace-repo-write",
    )
    with pytest.raises(RepoWriteLineageGuardError, match="lineage_replay_detected"):
        validate_repo_write_lineage(
            build_admission_record=lineage["build_admission_record"],
            normalized_execution_request=lineage["normalized_execution_request"],
            tlc_handoff_record=lineage["tlc_handoff_record"],
            expected_trace_id="trace-repo-write",
        )


def test_repo_write_lineage_rejects_stale_or_wrong_audience(monkeypatch: pytest.MonkeyPatch) -> None:
    wrong_audience = _lineage()
    wrong_audience["build_admission_record"]["authenticity"]["audience"] = "not_pqx"
    with pytest.raises(RepoWriteLineageGuardError, match="schema_invalid|authenticity_audience_invalid"):
        validate_repo_write_lineage(
            build_admission_record=wrong_audience["build_admission_record"],
            normalized_execution_request=wrong_audience["normalized_execution_request"],
            tlc_handoff_record=wrong_audience["tlc_handoff_record"],
            expected_trace_id="trace-repo-write",
        )

    stale = _lineage()
    stale["build_admission_record"]["authenticity"]["issued_at"] = "2020-01-01T00:00:00Z"
    stale["build_admission_record"]["authenticity"]["expires_at"] = "2030-01-01T00:00:00Z"
    monkeypatch.setenv("SPECTRUM_LINEAGE_AUTH_MAX_AGE_SECONDS", "1")
    with pytest.raises(RepoWriteLineageGuardError, match="authenticity_stale|authenticity_attestation_mismatch"):
        validate_repo_write_lineage(
            build_admission_record=stale["build_admission_record"],
            normalized_execution_request=stale["normalized_execution_request"],
            tlc_handoff_record=stale["tlc_handoff_record"],
            expected_trace_id="trace-repo-write",
        )


def test_repo_write_lineage_accepts_valid_fresh_authentic_lineage() -> None:
    lineage = _lineage()
    validated = validate_repo_write_lineage(
        build_admission_record=lineage["build_admission_record"],
        normalized_execution_request=lineage["normalized_execution_request"],
        tlc_handoff_record=lineage["tlc_handoff_record"],
        expected_trace_id="trace-repo-write",
    )
    assert validated["trace_id"] == "trace-repo-write"
    assert validated["request_id"] == "req-1"


def test_pqx_boundary_rejects_repo_write_with_forged_lineage(tmp_path: Path) -> None:
    lineage = _lineage()
    lineage["build_admission_record"]["authenticity"]["scope"] = "repo_write_lineage:build_admission_record:req-1:forged"
    with pytest.raises(PQXSequenceRunnerError, match="direct_pqx_repo_write_forbidden"):
        execute_sequence_run(
            slice_requests=_slice_requests(),
            state_path=tmp_path / "state.json",
            queue_run_id="queue-1",
            run_id="run-1",
            trace_id="trace-repo-write",
            max_slices=1,
            execution_class="repo_write",
            repo_write_lineage=lineage,
        )


def test_pqx_allows_valid_repo_write_lineage(tmp_path: Path) -> None:
    state = execute_sequence_run(
        slice_requests=_slice_requests(),
        state_path=tmp_path / "state.json",
        queue_run_id="queue-1",
        run_id="run-1",
        trace_id="trace-repo-write",
        max_slices=1,
        execution_class="repo_write",
        repo_write_lineage=_lineage(),
    )
    assert state["status"] in {"completed", "blocked", "failed"}
