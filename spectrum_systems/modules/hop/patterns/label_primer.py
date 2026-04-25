"""Label-space primer and contrastive examples pattern."""

from __future__ import annotations

from typing import Any, Mapping

from spectrum_systems.modules.hop.artifacts import finalize_artifact, make_trace
from spectrum_systems.modules.hop.schemas import validate_hop_artifact


def build_label_primer(
    *,
    workflow_id: str,
    label_examples: Mapping[str, Mapping[str, str]],
    contrastive_pairs: list[Mapping[str, str]],
    trace_id: str = "hop_label_primer",
) -> dict[str, Any]:
    labels = sorted(label_examples.keys())
    examples: list[dict[str, Any]] = []
    for label in labels:
        sample = label_examples[label]
        examples.append({"label": label, "input": sample["input"], "rationale": sample["rationale"]})

    payload: dict[str, Any] = {
        "artifact_type": "hop_harness_pattern_label_primer",
        "schema_ref": "hop/harness_pattern_label_primer.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(primary=trace_id),
        "pattern_id": f"label_primer_{workflow_id}",
        "workflow_id": workflow_id,
        "labels": labels,
        "coverage_examples": examples,
        "contrastive_pairs": [
            {
                "left_label": pair["left_label"],
                "right_label": pair["right_label"],
                "left_input": pair["left_input"],
                "right_input": pair["right_input"],
            }
            for pair in contrastive_pairs
        ],
    }
    finalize_artifact(payload, id_prefix="hop_pattern_")
    validate_hop_artifact(payload, "hop_harness_pattern_label_primer")
    return payload
