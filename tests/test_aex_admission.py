from __future__ import annotations

from spectrum_systems.aex.engine import AEXEngine


def _base_request() -> dict[str, object]:
    return {
        "request_id": "req-aex-01",
        "prompt_text": "Modify docs/architecture/system_registry.md and commit changes",
        "trace_id": "trace-aex-01",
        "created_at": "2026-04-08T00:00:00Z",
        "produced_by": "codex",
        "target_paths": ["docs/architecture/system_registry.md"],
        "requested_outputs": ["patch", "tests"],
        "source_prompt_kind": "codex_build_request",
    }


def test_valid_repo_write_request_emits_admission_record() -> None:
    result = AEXEngine().admit_codex_request(_base_request())
    assert result.accepted is True
    assert result.build_admission_record is not None
    assert result.build_admission_record["admission_status"] == "accepted"
    assert result.build_admission_record["execution_type"] == "repo_write"
    assert result.build_admission_record["trace_id"] == "trace-aex-01"
    assert result.normalized_execution_request is not None
    assert result.normalized_execution_request["trace_id"] == "trace-aex-01"


def test_invalid_repo_write_request_emits_rejection_record() -> None:
    bad = _base_request()
    bad.pop("prompt_text")
    result = AEXEngine().admit_codex_request(bad)
    assert result.accepted is False
    assert result.admission_rejection_record is not None
    assert "missing_required_field" in result.admission_rejection_record["rejection_reason_codes"]


def test_normalized_request_exists_before_tlc_handoff() -> None:
    called: dict[str, object] = {}

    def _tlc_runner(payload: dict[str, object]) -> dict[str, object]:
        called.update(payload)
        return {"ok": True}

    from spectrum_systems.aex.engine import admit_and_handoff_to_tlc

    out = admit_and_handoff_to_tlc(_base_request(), tlc_runner=_tlc_runner, tlc_request={"objective": "x", "branch_ref": "refs/heads/main", "retry_budget": 0, "require_review": False, "require_recovery": False})
    assert out["ok"] is True
    assert isinstance(called.get("normalized_execution_request"), dict)
    assert isinstance(called.get("build_admission_record"), dict)
