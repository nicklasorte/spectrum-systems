from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.evidence_binding import (  # noqa: E402
    EvidenceBindingError,
    EvidenceBindingPolicy,
    build_evidence_binding_record,
)


def _context_bundle() -> dict:
    return {
        "context_items": [
            {"item_id": "ctxi-aaaaaaaaaaaaaaaa"},
            {"item_id": "ctxi-bbbbbbbbbbbbbbbb"},
        ],
        "retrieved_context": [{"artifact_id": "ART-001"}],
        "prior_artifacts": [{"artifact_id": "ART-002"}],
        "metadata": {"source_artifact_ids": ["ART-003"]},
    }


def test_directly_supported_claim_gets_valid_evidence_refs() -> None:
    record = build_evidence_binding_record(
        run_id="agent-run-001",
        trace_id="trace-001",
        final_artifact={
            "claims": [
                {
                    "text": "Grounded claim",
                    "supporting_evidence_refs": ["ctxi-aaaaaaaaaaaaaaaa"],
                    "source_artifact_refs": ["ART-001"],
                }
            ]
        },
        validated_context_bundle=_context_bundle(),
        parent_multi_pass_record_id="mpg-1111111111111111",
        policy=EvidenceBindingPolicy(mode="required_grounded"),
    )
    claim = record["claims"][0]
    assert claim["claim_classification"] == "directly_supported"
    assert claim["evidence_item_refs"] == ["ctxi-aaaaaaaaaaaaaaaa"]


def test_inferred_claim_marked_inferred() -> None:
    inferred = build_evidence_binding_record(
        run_id="agent-run-003",
        trace_id="trace-003",
        final_artifact={"claims": [{"text": "Inference", "inferred": True}]},
        validated_context_bundle=_context_bundle(),
        parent_multi_pass_record_id="mpg-3333333333333333",
        policy=EvidenceBindingPolicy(mode="allow_inferred"),
    )
    assert inferred["claims"][0]["claim_classification"] == "inferred"


def test_required_grounded_mode_fails_on_unsupported_claims() -> None:
    with pytest.raises(EvidenceBindingError, match="required-grounded mode"):
        build_evidence_binding_record(
            run_id="agent-run-004",
            trace_id="trace-004",
            final_artifact={"summary": "Claim with no refs"},
            validated_context_bundle=_context_bundle(),
            parent_multi_pass_record_id="mpg-4444444444444444",
            policy=EvidenceBindingPolicy(mode="required_grounded"),
        )


def test_invalid_evidence_refs_fail_closed() -> None:
    with pytest.raises(EvidenceBindingError, match="non-existent context items"):
        build_evidence_binding_record(
            run_id="agent-run-005",
            trace_id="trace-005",
            final_artifact={"claims": [{"text": "bad ref", "supporting_evidence_refs": ["ctxi-cccccccccccccccc"]}]},
            validated_context_bundle=_context_bundle(),
            parent_multi_pass_record_id="mpg-5555555555555555",
            policy=EvidenceBindingPolicy(mode="required_grounded"),
        )


def test_deterministic_repeated_binding() -> None:
    kwargs = {
        "run_id": "agent-run-006",
        "trace_id": "trace-006",
        "final_artifact": {
            "claims": [
                {
                    "text": "Grounded",
                    "supporting_evidence_refs": ["ctxi-aaaaaaaaaaaaaaaa"],
                    "source_artifact_refs": ["ART-001"],
                }
            ]
        },
        "validated_context_bundle": _context_bundle(),
        "parent_multi_pass_record_id": "mpg-6666666666666666",
        "policy": EvidenceBindingPolicy(mode="required_grounded"),
    }
    r1 = build_evidence_binding_record(**kwargs)
    r2 = build_evidence_binding_record(**kwargs)
    assert r1 == r2
