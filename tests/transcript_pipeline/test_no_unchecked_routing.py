"""
Guardrail tests — tests/transcript_pipeline/test_no_unchecked_routing.py

Enforces that route_with_gate_evidence is the ONLY public routing entrypoint
exported from tlc_router and that the unchecked internal function is not
accessible as a public symbol.

FAIL IF:
- route_artifact is still a public attribute of the module
- _route_artifact_unchecked appears in __all__
- route_with_gate_evidence is absent from __all__
- the bypass guard fails to flag external use of _route_artifact_unchecked
- routing without structurally valid gate evidence is allowed
"""
from __future__ import annotations

from pathlib import Path

import pytest

from spectrum_systems.modules.orchestration import tlc_router
from spectrum_systems.modules.orchestration.tlc_router import (
    ArtifactRoutingError,
    route_with_gate_evidence,
)
from scripts.run_3ls_authority_preflight import (
    ROUTING_AUTHORITY_OWNER,
    ROUTING_BYPASS_GUARD_PROBES,
    detect_routing_bypass,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Public surface checks — route_with_gate_evidence is the sole entrypoint.
# ---------------------------------------------------------------------------


def test_route_artifact_not_public() -> None:
    assert not hasattr(tlc_router, "route_artifact"), (
        "route_artifact must not be a public attribute; use route_with_gate_evidence"
    )


def test_unchecked_not_in_all() -> None:
    assert "_route_artifact_unchecked" not in tlc_router.__all__


def test_route_with_gate_evidence_in_all() -> None:
    assert "route_with_gate_evidence" in tlc_router.__all__


def test_route_artifact_not_in_all() -> None:
    assert "route_artifact" not in tlc_router.__all__


def test_public_all_contains_only_governed_symbols() -> None:
    public = set(tlc_router.__all__)
    forbidden = {"route_artifact", "_route_artifact_unchecked"}
    assert forbidden.isdisjoint(public)


def test_route_with_gate_evidence_is_callable() -> None:
    assert callable(route_with_gate_evidence)


# ---------------------------------------------------------------------------
# Governed routing — gate evidence is required and structurally validated.
# ---------------------------------------------------------------------------


def test_governed_routing_accepts_valid_gate_evidence() -> None:
    result = route_with_gate_evidence(
        {"artifact_type": "transcript_artifact"},
        {"eval_summary_id": "guardrail-test-001", "gate_status": "passed_gate"},
    )
    assert result == "context_bundle"


def test_governed_routing_blocks_without_gate_evidence() -> None:
    with pytest.raises(ArtifactRoutingError) as exc_info:
        route_with_gate_evidence({"artifact_type": "transcript_artifact"}, None)  # type: ignore[arg-type]
    assert "MISSING_GATE_EVIDENCE" in exc_info.value.reason_codes


def test_governed_routing_blocks_string_gate_evidence() -> None:
    """Gate evidence must be a structured dict — bare strings are rejected."""
    with pytest.raises(ArtifactRoutingError) as exc_info:
        route_with_gate_evidence(
            {"artifact_type": "transcript_artifact"},
            "passed_gate",  # type: ignore[arg-type]
        )
    assert "MISSING_GATE_EVIDENCE" in exc_info.value.reason_codes


def test_governed_routing_blocks_empty_eval_summary_id() -> None:
    with pytest.raises(ArtifactRoutingError) as exc_info:
        route_with_gate_evidence(
            {"artifact_type": "transcript_artifact"},
            {"eval_summary_id": "   ", "gate_status": "passed_gate"},
        )
    assert "INVALID_EVAL_SUMMARY_ID" in exc_info.value.reason_codes


def test_governed_routing_blocks_non_string_gate_status() -> None:
    with pytest.raises(ArtifactRoutingError) as exc_info:
        route_with_gate_evidence(
            {"artifact_type": "transcript_artifact"},
            {"eval_summary_id": "guard-001", "gate_status": True},
        )
    assert "INVALID_GATE_STATUS_TYPE" in exc_info.value.reason_codes


def test_governed_routing_blocks_non_dict_artifact() -> None:
    with pytest.raises(ArtifactRoutingError) as exc_info:
        route_with_gate_evidence(
            "transcript_artifact",  # type: ignore[arg-type]
            {"eval_summary_id": "guard-002", "gate_status": "passed_gate"},
        )
    assert "INVALID_ARTIFACT_ENVELOPE" in exc_info.value.reason_codes


def test_governed_routing_blocks_failed_gate() -> None:
    with pytest.raises(ArtifactRoutingError) as exc_info:
        route_with_gate_evidence(
            {"artifact_type": "transcript_artifact"},
            {"eval_summary_id": "guardrail-test-002", "gate_status": "failed_gate"},
        )
    assert "GATE_EVIDENCE_NOT_ROUTABLE" in exc_info.value.reason_codes


def test_governed_routing_blocks_missing_gate() -> None:
    with pytest.raises(ArtifactRoutingError) as exc_info:
        route_with_gate_evidence(
            {"artifact_type": "transcript_artifact"},
            {"eval_summary_id": "guardrail-test-003", "gate_status": "missing_gate"},
        )
    assert "GATE_EVIDENCE_NOT_ROUTABLE" in exc_info.value.reason_codes


def test_governed_routing_blocks_conditional_gate_by_default() -> None:
    with pytest.raises(ArtifactRoutingError) as exc_info:
        route_with_gate_evidence(
            {"artifact_type": "transcript_artifact"},
            {"eval_summary_id": "guardrail-test-004", "gate_status": "conditional_gate"},
        )
    assert (
        "GATE_EVIDENCE_CONDITIONAL_ROUTING_NOT_ENABLED"
        in exc_info.value.reason_codes
    )


def test_governed_routing_blocks_target_artifact_id_mismatch() -> None:
    with pytest.raises(ArtifactRoutingError) as exc_info:
        route_with_gate_evidence(
            {"artifact_type": "transcript_artifact", "artifact_id": "TXA-A"},
            {
                "eval_summary_id": "guardrail-test-005",
                "gate_status": "passed_gate",
                "target_artifact_id": "TXA-B",
            },
        )
    assert "ARTIFACT_ID_MISMATCH" in exc_info.value.reason_codes


# ---------------------------------------------------------------------------
# Routing-bypass guard — preflight detection of indirect bypass paths.
# ---------------------------------------------------------------------------


def _write(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


def test_bypass_guard_flags_direct_unchecked_call(tmp_path: Path) -> None:
    rel = "scratch_bypass_direct.py"
    full = tmp_path / rel
    full.write_text(
        "from spectrum_systems.modules.orchestration.tlc_router import "
        "_route_artifact_unchecked\n"
        "_route_artifact_unchecked('transcript_artifact')\n",
        encoding="utf-8",
    )
    findings = detect_routing_bypass(rel, tmp_path)
    assert findings, "expected a ROUTING_BYPASS_ATTEMPT finding"
    assert all(f["reason_code"] == "ROUTING_BYPASS_ATTEMPT" for f in findings)


def test_bypass_guard_flags_wrapper_helper(tmp_path: Path) -> None:
    rel = "scratch_bypass_wrapper.py"
    body = (
        "from spectrum_systems.modules.orchestration.tlc_router import "
        "_route_artifact_unchecked as _ru\n"
        "def my_router(t):\n    return _ru(t)\n"
    )
    full = tmp_path / rel
    full.write_text(body, encoding="utf-8")
    findings = detect_routing_bypass(rel, tmp_path)
    # Even with alias rename, the import itself is flagged.
    assert any(
        "imports" in f["description"] or "from-imports" in f["description"]
        for f in findings
    )


def test_bypass_guard_flags_public_route_artifact_alias(tmp_path: Path) -> None:
    rel = "scratch_bypass_alias.py"
    full = tmp_path / rel
    full.write_text(
        "from spectrum_systems.modules.orchestration import tlc_router\n"
        "route_artifact = tlc_router._route_artifact_unchecked\n",
        encoding="utf-8",
    )
    findings = detect_routing_bypass(rel, tmp_path)
    assert findings


def test_bypass_guard_flags_public_route_artifact_function(tmp_path: Path) -> None:
    rel = "scratch_bypass_function.py"
    full = tmp_path / rel
    full.write_text(
        "def route_artifact(artifact_type):\n    return artifact_type\n",
        encoding="utf-8",
    )
    findings = detect_routing_bypass(rel, tmp_path)
    assert findings


def test_bypass_guard_ignores_owner_module() -> None:
    findings = detect_routing_bypass(ROUTING_AUTHORITY_OWNER, REPO_ROOT)
    assert findings == []


def test_bypass_guard_probe_allowlist_is_minimal() -> None:
    """The probe allowlist must be exactly the guard implementation and the
    two routing test modules. Adding to this list is a governance event."""
    assert ROUTING_BYPASS_GUARD_PROBES == frozenset(
        {
            "scripts/run_3ls_authority_preflight.py",
            "tests/transcript_pipeline/test_no_unchecked_routing.py",
            "tests/transcript_pipeline/test_replay_integrity_h01.py",
        }
    )


def test_bypass_guard_ignores_clean_consumer(tmp_path: Path) -> None:
    rel = "scratch_clean_consumer.py"
    full = tmp_path / rel
    full.write_text(
        "from spectrum_systems.modules.orchestration.tlc_router import "
        "route_with_gate_evidence\n"
        "next_type = route_with_gate_evidence(\n"
        "    {'artifact_type': 'transcript_artifact'},\n"
        "    {'eval_summary_id': 'x', 'gate_status': 'passed_gate'},\n"
        ")\n",
        encoding="utf-8",
    )
    findings = detect_routing_bypass(rel, tmp_path)
    assert findings == []


def test_bypass_guard_ignores_comment_only_mention(tmp_path: Path) -> None:
    rel = "scratch_comment_only.py"
    full = tmp_path / rel
    full.write_text(
        "# Do not call _route_artifact_unchecked from here.\n"
        "x = 1\n",
        encoding="utf-8",
    )
    findings = detect_routing_bypass(rel, tmp_path)
    assert findings == []
