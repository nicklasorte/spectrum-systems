from __future__ import annotations

from spectrum_systems.modules.hop.patterns.domain_router import route_input
from spectrum_systems.modules.hop.patterns.draft_verify import run_pattern
from spectrum_systems.modules.hop.patterns.label_primer import build_label_primer
from spectrum_systems.modules.hop.bootstrap import build_bootstrap_snapshot
from spectrum_systems.modules.hop.schemas import validate_hop_artifact


def test_domain_router_deterministic():
    transcript = {
        "transcript_id": "t1",
        "utterances": [
            {"text": "What is the refund policy?"},
            {"text": "The policy changed last week."},
        ],
    }
    a = route_input(transcript)
    b = route_input(transcript)
    assert a["decisions"] == b["decisions"]
    validate_hop_artifact(a, "hop_harness_routing_decision")


def test_draft_verify_schema_bound():
    payload = run_pattern(
        transcript={"transcript_id": "t2"},
        draft_items=[{"question": "Q", "answer": "A"}],
        supporting_evidence=[{"question": "Q", "evidence": "line 1"}],
        contradicting_evidence=[],
    )
    validate_hop_artifact(payload, "hop_harness_pattern_draft_verify")


def test_label_primer_schema_bound():
    payload = build_label_primer(
        workflow_id="transcript_to_faq",
        label_examples={
            "question": {"input": "What is this?", "rationale": "question mark"},
            "statement": {"input": "This is a statement.", "rationale": "declarative"},
        },
        contrastive_pairs=[
            {
                "left_label": "question",
                "right_label": "statement",
                "left_input": "How does it work?",
                "right_input": "It works this way.",
            }
        ],
    )
    validate_hop_artifact(payload, "hop_harness_pattern_label_primer")


def test_bootstrap_snapshot_schema_bound():
    payload = build_bootstrap_snapshot(
        repo_root=".",
        workflow_id="transcript_to_faq",
        max_entries=5,
    )
    validate_hop_artifact(payload, "hop_harness_bootstrap_snapshot")
