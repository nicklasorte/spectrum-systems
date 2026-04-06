from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.review_signal_classifier import (
    ReviewSignalClassificationError,
    classify_review_signal,
)


@pytest.fixture
def base_review_signal_artifact() -> dict:
    return json.loads(Path("contracts/examples/review_signal_artifact.json").read_text(encoding="utf-8"))


def _signals_for_item(control_signal: dict, item_id: str) -> list[dict]:
    return [signal for signal in control_signal["classified_signals"] if signal["source_item_id"] == item_id]


def test_critical_blocker_item_maps_to_block_and_escalation(base_review_signal_artifact: dict) -> None:
    control_signal = classify_review_signal(base_review_signal_artifact)
    cr1_signals = _signals_for_item(control_signal, "CR-1")

    classes = {signal["signal_class"] for signal in cr1_signals}
    assert "enforcement_block" in classes
    assert "control_escalation" in classes
    assert {signal["signal_priority"] for signal in cr1_signals if signal["signal_class"] == "enforcement_block"} == {"P0"}


def test_high_priority_non_blocking_maps_to_roadmap_or_governance(base_review_signal_artifact: dict) -> None:
    review_signal = copy.deepcopy(base_review_signal_artifact)
    review_signal["blocker_ids"] = ["CR-1", "CR-2"]
    control_signal = classify_review_signal(review_signal)

    hi1_classes = {signal["signal_class"] for signal in _signals_for_item(control_signal, "HI-1")}
    assert "roadmap_priority" in hi1_classes
    assert "governance_attention" in hi1_classes


def test_medium_item_maps_to_drift_watch_or_governance(base_review_signal_artifact: dict) -> None:
    control_signal = classify_review_signal(base_review_signal_artifact)
    mi1_classes = {signal["signal_class"] for signal in _signals_for_item(control_signal, "MI-1")}
    assert "drift_watch" in mi1_classes or "governance_attention" in mi1_classes


def test_fre_recovery_item_maps_to_recovery_followup(base_review_signal_artifact: dict) -> None:
    review_signal = copy.deepcopy(base_review_signal_artifact)
    review_signal["high_priority_items"].append(
        {
            "id": "HI-REC-1",
            "description": "FRE recurrence shows recovery loop regression",
            "severity": "high",
            "recommended_action": "Run recovery remediation checklist",
            "status": "open",
            "trace": {
                "source_path": "docs/review-actions/fre.md",
                "line_number": 42,
                "source_excerpt": "FRE recurrence recovery loop regression",
            },
        }
    )
    review_signal["action_items"].append(copy.deepcopy(review_signal["high_priority_items"][-1]))
    review_signal["severity_counts"]["high"] += 1

    control_signal = classify_review_signal(review_signal)
    classes = {signal["signal_class"] for signal in _signals_for_item(control_signal, "HI-REC-1")}
    assert "recovery_followup" in classes


def test_classification_is_deterministic(base_review_signal_artifact: dict) -> None:
    first = classify_review_signal(base_review_signal_artifact)
    second = classify_review_signal(base_review_signal_artifact)
    assert first == second


def test_fail_closed_when_required_field_missing(base_review_signal_artifact: dict) -> None:
    review_signal = copy.deepcopy(base_review_signal_artifact)
    review_signal.pop("source_action_tracker_path")

    with pytest.raises(ReviewSignalClassificationError, match="missing required field"):
        classify_review_signal(review_signal)


def test_fail_closed_when_item_id_missing_from_action_items(base_review_signal_artifact: dict) -> None:
    review_signal = copy.deepcopy(base_review_signal_artifact)
    review_signal["action_items"] = [item for item in review_signal["action_items"] if item["id"] != "CR-1"]

    with pytest.raises(ReviewSignalClassificationError, match="missing from action_items"):
        classify_review_signal(review_signal)


def test_traceability_preserves_source_item_linkage(base_review_signal_artifact: dict) -> None:
    control_signal = classify_review_signal(base_review_signal_artifact)
    validate_artifact(control_signal, "review_control_signal_artifact")

    assert control_signal["source_review_signal_ref"] == base_review_signal_artifact["review_signal_id"]
    for signal in control_signal["classified_signals"]:
        assert signal["source_item_id"]
        assert signal["trace_refs"]
        assert signal["trace_refs"][0]["source_path"]
