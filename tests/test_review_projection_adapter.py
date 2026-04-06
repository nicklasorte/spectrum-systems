from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.review_projection_adapter import (
    ReviewProjectionAdapterError,
    build_review_projection_bundle,
)


@pytest.fixture
def base_review_integration_packet_artifact() -> dict:
    return json.loads(Path("contracts/examples/review_integration_packet_artifact.json").read_text(encoding="utf-8"))


def test_roadmap_projection_preserves_items_and_summary(base_review_integration_packet_artifact: dict) -> None:
    bundle = build_review_projection_bundle(base_review_integration_packet_artifact)
    roadmap_projection = bundle["roadmap_projection"]

    assert roadmap_projection["item_count"] == len(base_review_integration_packet_artifact["roadmap_inputs"])
    assert roadmap_projection["highest_priority"] == base_review_integration_packet_artifact["highest_priority"]
    assert roadmap_projection["blocker_present"] is base_review_integration_packet_artifact["blocker_present"]

    source_input_ids = {item["input_id"] for item in base_review_integration_packet_artifact["roadmap_inputs"]}
    for projected in roadmap_projection["projected_roadmap_items"]:
        assert projected["source_input_id"] in source_input_ids
        assert projected["trace_refs"]


def test_control_loop_projection_preserves_blocker_escalation_and_read_only_shape(
    base_review_integration_packet_artifact: dict,
) -> None:
    bundle = build_review_projection_bundle(base_review_integration_packet_artifact)
    control_projection = bundle["control_loop_projection"]

    assert control_projection["blocker_present"] is True
    assert control_projection["escalation_present"] is True
    assert control_projection["item_count"] == len(control_projection["control_queue_items"])

    queue_item = control_projection["control_queue_items"][0]
    assert set(queue_item.keys()) == {
        "queue_item_id",
        "source_input_id",
        "intake_type",
        "priority",
        "severity",
        "blocker_related",
        "rationale",
        "trace_refs",
    }


def test_readiness_projection_aggregate_counts_and_provenance(base_review_integration_packet_artifact: dict) -> None:
    bundle = build_review_projection_bundle(base_review_integration_packet_artifact)
    readiness_projection = bundle["readiness_projection"]

    expected_by_severity = {"critical": 0, "high": 0, "medium": 0}
    expected_by_type: dict[str, int] = {}
    for item in base_review_integration_packet_artifact["readiness_inputs"]:
        expected_by_severity[item["severity"]] += 1
        expected_by_type[item["input_type"]] = expected_by_type.get(item["input_type"], 0) + 1

    assert readiness_projection["counts_by_severity"] == expected_by_severity
    assert readiness_projection["counts_by_type"] == expected_by_type
    assert readiness_projection["item_count"] == len(base_review_integration_packet_artifact["readiness_inputs"])

    source_input_ids = {item["input_id"] for item in base_review_integration_packet_artifact["readiness_inputs"]}
    for readiness_item in readiness_projection["readiness_items"]:
        assert readiness_item["source_input_id"] in source_input_ids
        assert readiness_item["trace_refs"]


def test_bundle_references_all_three_projections(base_review_integration_packet_artifact: dict) -> None:
    bundle = build_review_projection_bundle(base_review_integration_packet_artifact)

    assert bundle["roadmap_projection_ref"] == bundle["roadmap_projection"]["roadmap_review_projection_id"]
    assert bundle["control_loop_projection_ref"] == bundle["control_loop_projection"]["control_loop_review_intake_id"]
    assert bundle["readiness_projection_ref"] == bundle["readiness_projection"]["readiness_review_projection_id"]

    validate_artifact(bundle["roadmap_projection"], "roadmap_review_projection_artifact")
    validate_artifact(bundle["control_loop_projection"], "control_loop_review_intake_artifact")
    validate_artifact(bundle["readiness_projection"], "readiness_review_projection_artifact")
    validate_artifact(bundle, "review_projection_bundle_artifact")


def test_projection_adapter_is_deterministic(base_review_integration_packet_artifact: dict) -> None:
    first = build_review_projection_bundle(base_review_integration_packet_artifact)
    second = build_review_projection_bundle(base_review_integration_packet_artifact)

    assert first == second


def test_fail_closed_on_malformed_integration_packet(base_review_integration_packet_artifact: dict) -> None:
    malformed = copy.deepcopy(base_review_integration_packet_artifact)
    malformed["roadmap_inputs"][0]["input_id"] = ""

    with pytest.raises(ReviewProjectionAdapterError, match="schema validation"):
        build_review_projection_bundle(malformed)


def test_fail_closed_on_missing_trace_refs(base_review_integration_packet_artifact: dict) -> None:
    malformed = copy.deepcopy(base_review_integration_packet_artifact)
    malformed["control_loop_inputs"][0]["trace_refs"] = []

    with pytest.raises(ReviewProjectionAdapterError, match="schema validation"):
        build_review_projection_bundle(malformed)


def test_fail_closed_on_mismatched_counts(base_review_integration_packet_artifact: dict) -> None:
    malformed = copy.deepcopy(base_review_integration_packet_artifact)
    malformed["counts_by_type"]["escalation_intake"] += 1

    with pytest.raises(ReviewProjectionAdapterError, match="counts_by_type"):
        build_review_projection_bundle(malformed)


def test_provenance_continuity_to_source_inputs(base_review_integration_packet_artifact: dict) -> None:
    bundle = build_review_projection_bundle(base_review_integration_packet_artifact)

    all_source_input_ids = {
        item["input_id"]
        for channel in ("control_loop_inputs", "roadmap_inputs", "readiness_inputs")
        for item in base_review_integration_packet_artifact[channel]
    }

    for projected in bundle["roadmap_projection"]["projected_roadmap_items"]:
        assert projected["source_input_id"] in all_source_input_ids
    for projected in bundle["control_loop_projection"]["control_queue_items"]:
        assert projected["source_input_id"] in all_source_input_ids
    for projected in bundle["readiness_projection"]["readiness_items"]:
        assert projected["source_input_id"] in all_source_input_ids

    assert bundle["source_review_path"] == base_review_integration_packet_artifact["source_review_path"]
    assert bundle["source_review_integration_packet_ref"] == base_review_integration_packet_artifact["review_integration_packet_id"]


def test_projection_bundle_rejects_malformed_nested_projection_type(base_review_integration_packet_artifact: dict) -> None:
    bundle = build_review_projection_bundle(base_review_integration_packet_artifact)
    malformed = copy.deepcopy(bundle)
    malformed["roadmap_projection"]["artifact_type"] = "wrong_projection_artifact"

    with pytest.raises(Exception):
        validate_artifact(malformed, "review_projection_bundle_artifact")
