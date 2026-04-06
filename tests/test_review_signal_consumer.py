from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.review_signal_consumer import (
    ReviewSignalConsumptionError,
    build_review_integration_packet,
)


@pytest.fixture
def base_review_control_signal_artifact() -> dict:
    return json.loads(Path("contracts/examples/review_control_signal_artifact.json").read_text(encoding="utf-8"))


def _inputs_by_type(packet: dict, *, channel: str, input_type: str) -> list[dict]:
    channel_items = packet[f"{channel}_inputs"]
    return [item for item in channel_items if item["input_type"] == input_type]


def test_blocker_signal_routes_to_control_loop_and_readiness(base_review_control_signal_artifact: dict) -> None:
    packet = build_review_integration_packet(base_review_control_signal_artifact)

    control_blockers = _inputs_by_type(packet, channel="control_loop", input_type="blocker_intake")
    readiness_blockers = _inputs_by_type(packet, channel="readiness", input_type="blocker_intake")

    assert control_blockers
    assert readiness_blockers


def test_roadmap_priority_routes_to_roadmap_only(base_review_control_signal_artifact: dict) -> None:
    packet = build_review_integration_packet(base_review_control_signal_artifact)

    roadmap_priority_inputs = _inputs_by_type(packet, channel="roadmap", input_type="roadmap_priority_intake")
    control_priority_inputs = _inputs_by_type(packet, channel="control_loop", input_type="roadmap_priority_intake")
    readiness_priority_inputs = _inputs_by_type(packet, channel="readiness", input_type="roadmap_priority_intake")

    assert roadmap_priority_inputs
    assert not control_priority_inputs
    assert not readiness_priority_inputs


def test_drift_recovery_and_governance_routing_is_deterministic(base_review_control_signal_artifact: dict) -> None:
    packet = build_review_integration_packet(base_review_control_signal_artifact)

    assert _inputs_by_type(packet, channel="readiness", input_type="drift_watch_intake")
    assert _inputs_by_type(packet, channel="roadmap", input_type="recovery_followup_intake")
    assert _inputs_by_type(packet, channel="readiness", input_type="recovery_followup_intake")
    assert _inputs_by_type(packet, channel="readiness", input_type="governance_attention_intake")


def test_consumption_is_deterministic(base_review_control_signal_artifact: dict) -> None:
    first = build_review_integration_packet(base_review_control_signal_artifact)
    second = build_review_integration_packet(base_review_control_signal_artifact)
    assert first == second


def test_fail_closed_when_required_field_missing(base_review_control_signal_artifact: dict) -> None:
    artifact = copy.deepcopy(base_review_control_signal_artifact)
    artifact.pop("source_review_path")

    with pytest.raises(ReviewSignalConsumptionError, match="schema validation"):
        build_review_integration_packet(artifact)


def test_fail_closed_when_trace_refs_missing(base_review_control_signal_artifact: dict) -> None:
    artifact = copy.deepcopy(base_review_control_signal_artifact)
    artifact["classified_signals"][0]["trace_refs"] = []

    with pytest.raises(ReviewSignalConsumptionError, match="schema validation"):
        build_review_integration_packet(artifact)


def test_traceability_preserves_source_signal_linkage(base_review_control_signal_artifact: dict) -> None:
    packet = build_review_integration_packet(base_review_control_signal_artifact)
    validate_artifact(packet, "review_integration_packet_artifact")

    source_signal_ids = {signal["signal_id"] for signal in base_review_control_signal_artifact["classified_signals"]}
    for channel in ("control_loop", "roadmap", "readiness"):
        for item in packet[f"{channel}_inputs"]:
            assert item["source_signal_id"] in source_signal_ids
            assert item["trace_refs"]


def test_counts_and_summary_are_correct(base_review_control_signal_artifact: dict) -> None:
    packet = build_review_integration_packet(base_review_control_signal_artifact)

    assert packet["counts_by_channel"]["control_loop"] == len(packet["control_loop_inputs"])
    assert packet["counts_by_channel"]["roadmap"] == len(packet["roadmap_inputs"])
    assert packet["counts_by_channel"]["readiness"] == len(packet["readiness_inputs"])

    total_counted_types = sum(packet["counts_by_type"].values())
    total_inputs = len(packet["control_loop_inputs"]) + len(packet["roadmap_inputs"]) + len(packet["readiness_inputs"])
    assert total_counted_types == total_inputs
    assert packet["highest_priority"] in {"P0", "P1", "P2", "monitor"}
