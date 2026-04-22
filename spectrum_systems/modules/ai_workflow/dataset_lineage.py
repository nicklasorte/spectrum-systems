"""DAT: Dataset lineage enforcement.

Every eval dataset must have provenance fields before execution is permitted.
Required fields: source_url, version, content_hash, created_at.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

REQUIRED_LINEAGE_FIELDS: List[str] = ["source_url", "version", "content_hash", "created_at"]


def validate_dataset_lineage(dataset: Dict) -> Tuple[bool, str]:
    """Validate that a dataset artifact has all required provenance fields.

    Returns (valid, reason).
    """
    missing = [f for f in REQUIRED_LINEAGE_FIELDS if not dataset.get(f)]
    if missing:
        return False, f"Dataset missing required lineage fields: {missing}"
    return True, "Lineage complete"


def validate_eval_coverage(artifact_family: str, eval_cases: List[Dict], min_cases: int = 3) -> Tuple[bool, List[str]]:
    """Validate that an artifact family has at least min_cases eval cases."""
    matched = [
        c for c in eval_cases
        if c.get("artifact_type") == artifact_family
        or artifact_family in c.get("tags", [])
    ]
    if len(matched) < min_cases:
        return False, [
            f"{artifact_family}: {len(matched)} eval cases found, need ≥{min_cases}"
        ]
    return True, []
