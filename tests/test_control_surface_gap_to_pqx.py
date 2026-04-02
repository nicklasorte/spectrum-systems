from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.control_surface_gap_to_pqx import (
    ControlSurfaceGapToPQXError,
    convert_gap_packet_to_pqx_work_items,
    sort_packet_gaps,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_gap_packet() -> dict:
    return json.loads((_REPO_ROOT / "contracts" / "examples" / "control_surface_gap_packet.json").read_text(encoding="utf-8"))


def test_valid_packet_consumes_without_inference_when_empty() -> None:
    gap_packet = _load_gap_packet()
    assert gap_packet["overall_decision"] == "ALLOW"
    assert gap_packet["gaps"] == []

    work_items = convert_gap_packet_to_pqx_work_items(gap_packet)

    assert work_items == []


def test_block_packet_gaps_drive_work_items() -> None:
    gap_packet = _load_gap_packet()
    gap_packet["overall_decision"] = "BLOCK"
    gap_packet["gap_count"] = 2
    gap_packet["blocking_gap_count"] = 1
    gap_packet["summary"] = "Detected blocking control-surface gaps."
    gap_packet["gaps"] = [
        {
            "gap_id": "csg-aaaaaaaaaaaaaaaaaaaaaaaa",
            "surface_name": "control_surface_manifest",
            "gap_category": "missing_manifest_surface",
            "severity": "critical",
            "blocking": True,
            "observed_condition": "surface missing",
            "expected_condition": "surface declared",
            "evidence_ref": "contracts/examples/control_surface_manifest.json",
            "source_artifact_type": "control_surface_manifest",
            "source_artifact_ref": "contracts/examples/control_surface_manifest.json",
            "suggested_action": "fix_manifest_declaration",
            "deterministic_identity": "csg-aaaaaaaaaaaaaaaaaaaaaaaa",
        },
        {
            "gap_id": "csg-bbbbbbbbbbbbbbbbbbbbbbbb",
            "surface_name": "trust_spine_evidence_cohesion",
            "gap_category": "insufficient_runtime_evidence",
            "severity": "medium",
            "blocking": False,
            "observed_condition": "missing evidence",
            "expected_condition": "evidence complete",
            "evidence_ref": "contracts/examples/trust_spine_evidence_cohesion_result.json",
            "source_artifact_type": "trust_spine_evidence_cohesion_result",
            "source_artifact_ref": "contracts/examples/trust_spine_evidence_cohesion_result.json",
            "suggested_action": "add_runtime_evidence",
            "deterministic_identity": "csg-bbbbbbbbbbbbbbbbbbbbbbbb",
        },
    ]
    gap_packet["evidence_refs"] = sorted({entry["evidence_ref"] for entry in gap_packet["gaps"]})
    gap_packet["next_governance_actions"] = sorted({entry["suggested_action"] for entry in gap_packet["gaps"]})

    work_items = convert_gap_packet_to_pqx_work_items(gap_packet)

    assert [item["gap_id"] for item in work_items] == [
        "csg-aaaaaaaaaaaaaaaaaaaaaaaa",
        "csg-bbbbbbbbbbbbbbbbbbbbbbbb",
    ]


def test_deterministic_ordering_block_then_surface_then_gap_id() -> None:
    gaps = [
        {"gap_id": "csg-cccccccccccccccccccccccc", "surface_name": "unknown_surface", "blocking": False},
        {"gap_id": "csg-aaaaaaaaaaaaaaaaaaaaaaaa", "surface_name": "trust_spine_evidence_cohesion", "blocking": True},
        {"gap_id": "csg-bbbbbbbbbbbbbbbbbbbbbbbb", "surface_name": "control_surface_manifest", "blocking": True},
    ]

    ordered = sort_packet_gaps(gaps)

    assert [gap["gap_id"] for gap in ordered] == [
        "csg-bbbbbbbbbbbbbbbbbbbbbbbb",
        "csg-aaaaaaaaaaaaaaaaaaaaaaaa",
        "csg-cccccccccccccccccccccccc",
    ]


def test_fail_closed_on_malformed_gap_packet() -> None:
    gap_packet = _load_gap_packet()
    gap_packet.pop("artifact_id")

    with pytest.raises(ControlSurfaceGapToPQXError, match="schema validation"):
        convert_gap_packet_to_pqx_work_items(gap_packet)
