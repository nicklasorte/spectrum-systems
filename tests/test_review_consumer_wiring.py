from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.review_consumer_wiring import (
    ReviewConsumerWiringError,
    build_review_consumer_outputs,
)


@pytest.fixture
def projection_inputs() -> dict[str, dict]:
    base = Path("contracts/examples")
    return {
        "bundle": json.loads((base / "review_projection_bundle_artifact.json").read_text(encoding="utf-8")),
        "roadmap": json.loads((base / "roadmap_review_projection_artifact.json").read_text(encoding="utf-8")),
        "control": json.loads((base / "control_loop_review_intake_artifact.json").read_text(encoding="utf-8")),
        "readiness": json.loads((base / "readiness_review_projection_artifact.json").read_text(encoding="utf-8")),
    }


def _build(inputs: dict[str, dict]) -> dict:
    return build_review_consumer_outputs(
        inputs["bundle"],
        inputs["roadmap"],
        inputs["control"],
        inputs["readiness"],
    )


def test_roadmap_consumer_output_derived_from_roadmap_projection_only(projection_inputs: dict[str, dict]) -> None:
    output = _build(projection_inputs)
    roadmap_view = output["roadmap_review_view_artifact"]

    assert roadmap_view["source_roadmap_projection_ref"] == projection_inputs["roadmap"]["roadmap_review_projection_id"]
    assert roadmap_view["source_review_projection_bundle_ref"] == projection_inputs["bundle"]["review_projection_bundle_id"]
    assert roadmap_view["item_count"] == len(roadmap_view["roadmap_view_items"])

    projected_item_ids = {item["projection_item_id"] for item in projection_inputs["roadmap"]["projected_roadmap_items"]}
    for view_item in roadmap_view["roadmap_view_items"]:
        assert view_item["source_projection_item_id"] in projected_item_ids
        assert view_item["trace_refs"]


def test_control_loop_queue_output_passthrough_preserves_read_only_shape(projection_inputs: dict[str, dict]) -> None:
    output = _build(projection_inputs)
    queue_record = output["control_loop_review_queue_record_artifact"]

    assert queue_record["blocker_present"] is projection_inputs["control"]["blocker_present"]
    assert queue_record["escalation_present"] is projection_inputs["control"]["escalation_present"]
    assert queue_record["item_count"] == len(queue_record["queue_records"])

    first = queue_record["queue_records"][0]
    assert set(first.keys()) == {
        "queue_record_id",
        "source_queue_item_id",
        "intake_type",
        "priority",
        "severity",
        "blocker_related",
        "rationale",
        "trace_refs",
    }


def test_readiness_dashboard_derived_only_from_readiness_projection_and_counts_preserved(
    projection_inputs: dict[str, dict]
) -> None:
    output = _build(projection_inputs)
    dashboard = output["readiness_review_dashboard_artifact"]

    assert dashboard["source_readiness_projection_ref"] == projection_inputs["readiness"]["readiness_review_projection_id"]
    assert dashboard["counts_by_severity"] == projection_inputs["readiness"]["counts_by_severity"]
    assert dashboard["counts_by_type"] == projection_inputs["readiness"]["counts_by_type"]
    assert dashboard["item_count"] == len(dashboard["dashboard_items"])


def test_consumption_validation_proves_projection_only_read_only_intake(projection_inputs: dict[str, dict]) -> None:
    output = _build(projection_inputs)
    validation = output["review_consumption_validation_artifact"]

    assert validation["intake_boundary_valid"] is True
    assert validation["read_only_consumption_valid"] is True
    assert validation["raw_review_access_detected"] is False
    assert validation["earlier_ril_artifact_access_detected"] is False
    assert validation["validation_findings"]


def test_invalid_intake_boundary_fails_closed(projection_inputs: dict[str, dict]) -> None:
    malformed = copy.deepcopy(projection_inputs)
    malformed["bundle"]["roadmap_projection_ref"] = "rrp-deadbeefdeadbeef"

    with pytest.raises(ReviewConsumerWiringError, match="reference mismatch"):
        _build(malformed)


def test_output_bundle_references_all_consumer_outputs_and_validation(projection_inputs: dict[str, dict]) -> None:
    output = _build(projection_inputs)

    assert output["roadmap_review_view_ref"] == output["roadmap_review_view_artifact"]["roadmap_review_view_id"]
    assert output["control_loop_review_queue_record_ref"] == output["control_loop_review_queue_record_artifact"]["control_loop_review_queue_record_id"]
    assert output["readiness_review_dashboard_ref"] == output["readiness_review_dashboard_artifact"]["readiness_review_dashboard_id"]
    assert output["review_consumption_validation_ref"] == output["review_consumption_validation_artifact"]["review_consumption_validation_id"]

    validate_artifact(output["roadmap_review_view_artifact"], "roadmap_review_view_artifact")
    validate_artifact(output["control_loop_review_queue_record_artifact"], "control_loop_review_queue_record_artifact")
    validate_artifact(output["readiness_review_dashboard_artifact"], "readiness_review_dashboard_artifact")
    validate_artifact(output["review_consumption_validation_artifact"], "review_consumption_validation_artifact")
    validate_artifact(output, "review_consumer_output_bundle_artifact")


def test_consumer_wiring_is_deterministic(projection_inputs: dict[str, dict]) -> None:
    first = _build(projection_inputs)
    second = _build(projection_inputs)

    assert first == second


def test_fail_closed_on_missing_trace_refs(projection_inputs: dict[str, dict]) -> None:
    malformed = copy.deepcopy(projection_inputs)
    malformed["readiness"]["readiness_items"][0]["trace_refs"] = []

    with pytest.raises(ReviewConsumerWiringError, match="schema validation"):
        _build(malformed)
