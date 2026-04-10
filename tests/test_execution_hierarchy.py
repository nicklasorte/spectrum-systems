from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.execution_hierarchy import (
    ExecutionHierarchyError,
    validate_execution_hierarchy,
)


def test_invalid_single_slice_batch_fails() -> None:
    payload = {
        "batches": [
            {
                "batch_id": "BATCH-ONE",
                "slice_ids": ["SLICE-1"],
            }
        ]
    }
    with pytest.raises(ExecutionHierarchyError, match="invalid batch cardinality"):
        validate_execution_hierarchy(payload, label="batch_manifest")


def test_invalid_single_batch_umbrella_fails() -> None:
    payload = {
        "umbrellas": [
            {
                "umbrella_id": "UMB-A",
                "batch_ids": ["BATCH-A"],
            }
        ]
    }
    with pytest.raises(ExecutionHierarchyError, match="invalid umbrella cardinality"):
        validate_execution_hierarchy(payload, label="roadmap_manifest")


def test_invalid_single_batch_umbrella_using_embedded_batches_fails() -> None:
    payload = {
        "umbrellas": [
            {
                "umbrella_id": "UMB-B",
                "batches": [{"batch_id": "BATCH-A"}],
            }
        ]
    }
    with pytest.raises(ExecutionHierarchyError, match="invalid umbrella cardinality"):
        validate_execution_hierarchy(payload, label="roadmap_manifest")


def test_valid_multi_slice_batch_passes() -> None:
    payload = {
        "batches": [
            {
                "batch_id": "BATCH-OK",
                "slice_ids": ["SLICE-1", "SLICE-2"],
            }
        ]
    }
    validate_execution_hierarchy(payload, label="batch_manifest")


def test_valid_multi_batch_umbrella_passes() -> None:
    payload = {
        "batches": [
            {"batch_id": "BATCH-A", "slice_ids": ["SLICE-1", "SLICE-2"]},
            {"batch_id": "BATCH-B", "slice_ids": ["SLICE-3", "SLICE-4"]},
        ],
        "umbrellas": [
            {
                "umbrella_id": "UMB-OK",
                "batch_ids": ["BATCH-A", "BATCH-B"],
            }
        ],
    }
    validate_execution_hierarchy(payload, label="roadmap_manifest")
