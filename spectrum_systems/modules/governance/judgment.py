"""JDX: Judgment evidence sufficiency enforcement.

Every judgment must reference ≥2 evidence artifacts.
Single-evidence judgments are blocked at creation.
"""

from __future__ import annotations

from typing import Dict, Tuple


MIN_EVIDENCE_COUNT = 2


def validate_judgment_evidence(judgment: Dict) -> Tuple[bool, str]:
    """Validate that a judgment references at least MIN_EVIDENCE_COUNT evidence artifacts.

    Returns (valid, reason).
    """
    evidence = judgment.get("evidence_artifacts", [])
    if len(evidence) < MIN_EVIDENCE_COUNT:
        return (
            False,
            f"Judgment {judgment.get('id', '?')}: {len(evidence)} evidence artifact(s), "
            f"need ≥{MIN_EVIDENCE_COUNT}",
        )
    return True, "Evidence sufficiency satisfied"
