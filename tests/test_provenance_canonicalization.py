"""Tier-1 canonical provenance hardening tests."""

from __future__ import annotations

import copy

import pytest

from spectrum_systems.modules.runtime.drift_detection_engine import DriftDetectionError, detect_drift
from spectrum_systems.modules.runtime.enforcement_engine import enforce_control_decision
from spectrum_systems.modules.runtime.provenance import validate_canonical_provenance
from spectrum_systems.modules.runtime.replay_engine import ReplayEngineError, run_replay
from spectrum_systems.modules.runtime.control_loop import run_control_loop
from spectrum_systems.modules.strategic_knowledge.validator import validate_strategic_knowledge_artifact


def _artifact() -> dict:
    return {
        "artifact_type": "eval_summary",
        "schema_version": "1.0.0",
        "trace_id": "44444444-4444-4444-8444-444444444444",
        "eval_run_id": "eval-run-20260322T000000Z",
        "pass_rate": 0.99,
        "failure_rate": 0.01,
        "drift_rate": 0.01,
        "reproducibility_score": 0.99,
        "system_status": "healthy",
    }


def _trace_context() -> dict:
    return {
        "trace_id": "44444444-4444-4444-8444-444444444444",
        "span_id": "span-replay-001",
        "parent_span_id": "parent-replay-001",
    }


def _sk_artifact() -> dict:
    return {
        "artifact_type": "book_intelligence_pack",
        "artifact_id": "ART-001",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "created_at": "2026-03-21T10:00:00Z",
        "source": {
            "source_id": "SRC-BOOK-001",
            "source_type": "book_pdf",
            "source_path": "strategic_knowledge/raw/books/book-a.pdf",
        },
        "provenance": {"extraction_run_id": "run-001", "extractor_version": "0.1.0"},
        "evidence_anchors": [{"anchor_type": "pdf", "page_number": 10}],
        "insights": ["Insight A"],
        "themes": ["Theme A"],
        "key_claims": ["Claim A"],
    }


def _sk_context() -> dict:
    return {
        "trace_id": "trace-sk-001",
        "span_id": "span-sk-001",
        "parent_span_id": "parent-sk-001",
        "run_id": "run-sk-001",
        "source_catalog": {"sources": [{"source_id": "SRC-BOOK-001", "source_status": "ready"}]},
    }


def test_runtime_emitters_use_canonical_provenance() -> None:
    decision = run_control_loop(_artifact(), _trace_context())["evaluation_control_decision"]
    enforcement = enforce_control_decision(decision)
    assert validate_canonical_provenance(enforcement["provenance"]) == []


def test_replay_emitters_use_canonical_provenance() -> None:
    decision = run_control_loop(_artifact(), _trace_context())["evaluation_control_decision"]
    enforcement = enforce_control_decision(decision)
    replay = run_replay(_artifact(), decision, enforcement, _trace_context())
    assert validate_canonical_provenance(replay["provenance"]) == []


def test_runtime_replay_provenance_parity() -> None:
    decision = run_control_loop(_artifact(), _trace_context())["evaluation_control_decision"]
    enforcement = enforce_control_decision(decision)
    replay = run_replay(_artifact(), decision, enforcement, _trace_context())
    assert set(replay["provenance"].keys()) == set(enforcement["provenance"].keys())


def test_missing_trace_context_fails_closed() -> None:
    decision = run_control_loop(_artifact(), _trace_context())["evaluation_control_decision"]
    enforcement = enforce_control_decision(decision)
    with pytest.raises(ReplayEngineError, match="REPLAY_MISSING_TRACE_CONTEXT"):
        run_replay(_artifact(), decision, enforcement, {"trace_id": "t-only"})


def test_sk_cannot_emit_synthetic_trace_context() -> None:
    with pytest.raises(ValueError, match="STRATEGIC_KNOWLEDGE_MISSING_TRACE_CONTEXT"):
        validate_strategic_knowledge_artifact(_sk_artifact(), {"source_catalog": _sk_context()["source_catalog"]})


def test_mutation_requires_revalidation() -> None:
    decision = run_control_loop(_artifact(), _trace_context())["evaluation_control_decision"]
    enforcement = enforce_control_decision(decision)
    replay = run_replay(_artifact(), decision, enforcement, _trace_context())
    tampered = copy.deepcopy(replay)
    tampered["provenance"]["trace_id"] = "unknown-trace"
    with pytest.raises(DriftDetectionError, match="provenance invalid"):
        detect_drift(tampered)
