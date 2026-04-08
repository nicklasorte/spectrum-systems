from __future__ import annotations

from spectrum_systems.aex.engine import AEXEngine


def test_ambiguous_request_that_might_mutate_repo_is_rejected() -> None:
    request = {
        "request_id": "req-aex-ambiguous",
        "prompt_text": "Please handle this request",
        "trace_id": "trace-aex-ambiguous",
        "created_at": "2026-04-08T00:00:00Z",
        "produced_by": "codex",
        "target_paths": ["spectrum_systems/modules/runtime/top_level_conductor.py"],
        "requested_outputs": ["response"],
    }
    result = AEXEngine().admit_codex_request(request)
    assert result.accepted is False
    assert result.admission_rejection_record is not None
    assert "unknown_execution_type" in result.admission_rejection_record["rejection_reason_codes"]
    assert result.admission_rejection_record["trace_id"] == "trace-aex-ambiguous"


def test_unknown_without_required_fields_fails_closed() -> None:
    result = AEXEngine().admit_codex_request({"trace_id": "trace-1"})
    assert result.accepted is False
    assert result.admission_rejection_record is not None
    assert result.admission_rejection_record["trace_id"] == "trace-1"
