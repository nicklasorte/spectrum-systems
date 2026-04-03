from __future__ import annotations

from typing import Any, Dict, List


def build_eval_dataset_record(dataset_id: str, dataset_version: str, records: List[Dict[str, Any]], created_at: str) -> Dict[str, Any]:
    if not records:
        raise ValueError("eval dataset records must be non-empty")
    return {
        "artifact_type": "eval_dataset_record",
        "schema_version": "1.0.0",
        "dataset_id": dataset_id,
        "dataset_version": dataset_version,
        "records": records,
        "created_at": created_at,
    }
