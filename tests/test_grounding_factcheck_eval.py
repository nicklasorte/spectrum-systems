from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.grounding_factcheck_eval import (  # noqa: E402
    GroundingFactCheckEvalError,
    GroundingFactCheckPolicy,
    build_grounding_factcheck_eval,
)


def _context_bundle() -> dict:
    return {
        "context_items": [
            {
                "item_id": "ctxi-aaaaaaaaaaaaaaaa",
                "content": {"text": "Project completion is blocked by unresolved legal review."},
            },
            {
                "item_id": "ctxi-bbbbbbbbbbbbbbbb",
                "content": {"text": "Timeline is on hold until counsel signs off."},
            },
        ],
        "glossary_definitions": [
            {
                "glossary_entry_id": "gle-a2f8fbe34b21d991",
                "canonical_term": "legal review",
            }
        ],
        "glossary_canonicalization": {
            "selected_glossary_entry_ids": ["gle-a2f8fbe34b21d991"],
        },
    }


def _base_binding_claims() -> list[dict]:
    return [
        {
            "claim_id": "ebc-1111111111111111",
            "claim_path": "claims[0]",
            "claim_text": "Project completion is blocked by unresolved legal review.",
            "claim_classification": "directly_supported",
            "evidence_item_refs": ["ctxi-aaaaaaaaaaaaaaaa"],
        }
    ]


def _evidence_binding_record(claims: list[dict]) -> dict:
    return {
        "artifact_type": "evidence_binding_record",
        "record_id": "ebr-7b9f4a13c2d8e601",
        "trace_id": "trace-001",
        "claims": claims,
    }


def test_passing_directly_supported_claim() -> None:
    result = build_grounding_factcheck_eval(
        run_id="agent-run-001",
        trace_id="trace-001",
        source_artifact_id="agent-output://agent-run-001",
        final_artifact={"claims": [{"text": "Project completion is blocked by unresolved legal review."}]},
        evidence_binding_record=_evidence_binding_record(_base_binding_claims()),
        validated_context_bundle=_context_bundle(),
        parent_multi_pass_record_id="mpg-6a0f4b8c9d1e2f30",
        final_pass_output_ref="multi-pass://agent-run-001/final",
    )
    assert result["overall_status"] == "pass"
    assert result["claim_results"][0]["eval_status"] == "pass"


def test_evidence_mismatch_flagged() -> None:
    claims = _base_binding_claims()
    claims[0]["claim_text"] = "Revenue increased by 400 percent."
    result = build_grounding_factcheck_eval(
        run_id="agent-run-002",
        trace_id="trace-001",
        source_artifact_id="agent-output://agent-run-002",
        final_artifact={"claims": [{"text": "Revenue increased by 400 percent."}]},
        evidence_binding_record=_evidence_binding_record(claims),
        validated_context_bundle=_context_bundle(),
        parent_multi_pass_record_id="mpg-6a0f4b8c9d1e2f30",
        final_pass_output_ref="multi-pass://agent-run-002/final",
    )
    assert result["overall_status"] == "fail"
    assert "evidence_mismatch" in result["failure_classes"]
    assert "fact_check_fail" in result["failure_classes"]


def test_unsupported_grounded_claim_flagged() -> None:
    claims = [
        {
            "claim_id": "ebc-2222222222222222",
            "claim_path": "claims[0]",
            "claim_text": "Escalate review priority this week.",
            "claim_classification": "unsupported",
            "evidence_item_refs": [],
        }
    ]
    result = build_grounding_factcheck_eval(
        run_id="agent-run-003",
        trace_id="trace-001",
        source_artifact_id="agent-output://agent-run-003",
        final_artifact={"claims": [{"text": "Escalate review priority this week."}]},
        evidence_binding_record=_evidence_binding_record(claims),
        validated_context_bundle=_context_bundle(),
        parent_multi_pass_record_id="mpg-6a0f4b8c9d1e2f30",
        final_pass_output_ref="multi-pass://agent-run-003/final",
    )
    assert "unsupported_grounded_claim" in result["failure_classes"]


def test_inferred_claim_stays_inferred_and_disallowed_by_policy() -> None:
    claims = [
        {
            "claim_id": "ebc-3333333333333333",
            "claim_path": "claims[0]",
            "claim_text": "Escalation should happen this week.",
            "claim_classification": "inferred",
            "evidence_item_refs": [],
        }
    ]
    result = build_grounding_factcheck_eval(
        run_id="agent-run-004",
        trace_id="trace-001",
        source_artifact_id="agent-output://agent-run-004",
        final_artifact={"claims": [{"text": "Escalation should happen this week."}]},
        evidence_binding_record=_evidence_binding_record(claims),
        validated_context_bundle=_context_bundle(),
        parent_multi_pass_record_id="mpg-6a0f4b8c9d1e2f30",
        final_pass_output_ref="multi-pass://agent-run-004/final",
        policy=GroundingFactCheckPolicy(allow_inferred_claims=False),
    )
    assert result["claim_results"][0]["claim_classification_from_binding"] == "inferred"
    assert result["claim_results"][0]["eval_status"] == "fail"


def test_required_eval_missing_binding_fails_closed() -> None:
    with pytest.raises(GroundingFactCheckEvalError, match="artifact_type"):
        build_grounding_factcheck_eval(
            run_id="agent-run-005",
            trace_id="trace-001",
            source_artifact_id="agent-output://agent-run-005",
            final_artifact={"claims": []},
            evidence_binding_record={"artifact_type": "bad", "trace_id": "trace-001", "claims": []},
            validated_context_bundle=_context_bundle(),
            parent_multi_pass_record_id="mpg-6a0f4b8c9d1e2f30",
            final_pass_output_ref="multi-pass://agent-run-005/final",
        )


def test_deterministic_repeated_eval_and_trace_linkage() -> None:
    kwargs = dict(
        run_id="agent-run-006",
        trace_id="trace-001",
        source_artifact_id="agent-output://agent-run-006",
        final_artifact={"claims": [{"text": "Project completion is blocked by unresolved legal review."}]},
        evidence_binding_record=_evidence_binding_record(_base_binding_claims()),
        validated_context_bundle=_context_bundle(),
        parent_multi_pass_record_id="mpg-6a0f4b8c9d1e2f30",
        final_pass_output_ref="multi-pass://agent-run-006/final",
    )
    r1 = build_grounding_factcheck_eval(**kwargs)
    r2 = build_grounding_factcheck_eval(**kwargs)
    assert r1 == r2
    assert r1["trace_linkage"]["trace_id"] == "trace-001"
    assert r1["trace_linkage"]["final_pass_output_ref"] == "multi-pass://agent-run-006/final"
