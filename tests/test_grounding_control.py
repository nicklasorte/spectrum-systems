from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.grounding_control import (  # noqa: E402
    build_grounding_control_decision,
)


def _base_eval() -> Dict[str, Any]:
    return {
        "artifact_type": "grounding_factcheck_eval",
        "schema_version": "1.0.0",
        "eval_id": "gfe-5c8f2f0e7c4b9a11",
        "created_at": "2026-03-24T12:00:00Z",
        "claim_results": [
            {
                "claim_id": "ebc-1111111111111111",
                "claim_classification_from_binding": "directly_supported",
                "rationale_code": "ok_supported",
            }
        ],
        "trace_linkage": {
            "run_id": "agent-run-example-001",
            "trace_id": "trace-example-001",
            "parent_multi_pass_record_id": "mpg-6a0f4b8c9d1e2f30",
            "final_pass_output_ref": "multi-pass://agent-run-example-001/final",
        },
    }


def test_clean_pass() -> None:
    decision = build_grounding_control_decision(_base_eval(), policy={"policy_id": "grounding-control-v1", "generated_by_version": "hs-20.1.0"})
    assert decision["status"] == "pass"
    assert decision["enforcement_action"] == "allow"
    assert decision["failure_summary"]["unsupported_claims"] == 0
    assert decision["failure_summary"]["invalid_evidence_refs"] == 0


def test_unsupported_claim_warn() -> None:
    artifact = _base_eval()
    artifact["claim_results"].append(
        {
            "claim_id": "ebc-2222222222222222",
            "claim_classification_from_binding": "unsupported",
            "rationale_code": "unsupported_disallowed_by_policy",
        }
    )
    decision = build_grounding_control_decision(artifact)
    assert decision["status"] == "warn"
    assert decision["enforcement_action"] == "flag"
    assert decision["failure_summary"]["unsupported_claims"] == 1


def test_invalid_evidence_ref_blocks() -> None:
    artifact = _base_eval()
    artifact["claim_results"] = [
        {
            "claim_id": "ebc-1111111111111111",
            "claim_classification_from_binding": "directly_supported",
            "rationale_code": "direct_invalid_evidence_ref",
        }
    ]
    decision = build_grounding_control_decision(artifact)
    assert decision["status"] == "block"
    assert decision["enforcement_action"] == "block_execution"
    assert decision["failure_summary"]["invalid_evidence_refs"] == 1


def test_malformed_eval_fail_closed() -> None:
    decision = build_grounding_control_decision({"bad": "input"})
    assert decision["status"] == "block"
    assert decision["enforcement_action"] == "block_execution"
    assert "malformed_eval_input" in decision["triggered_rules"]
    assert decision["timestamp"].endswith("Z")


def test_deterministic_output_for_same_input() -> None:
    artifact = _base_eval()
    d1 = build_grounding_control_decision(artifact)
    d2 = build_grounding_control_decision(artifact)
    assert d1 == d2
