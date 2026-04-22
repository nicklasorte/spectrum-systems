"""LIN: End-to-end lineage verifier.

Every promoted artifact must have a traceable chain back to an input artifact.
Artifacts with missing upstream links or orphaned references are blocked.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

INPUT_ARTIFACT_TYPES = frozenset({
    "transcript_artifact",
    "input_bundle",
    "codex_build_request",
    "admission_bundle",
})


def verify_lineage_completeness(
    artifact_id: str,
    artifact_store: Optional[Dict] = None,
) -> Tuple[bool, List[str]]:
    """Verify that artifact_id has complete lineage back to an input artifact.

    Parameters
    ----------
    artifact_id:
        The ID of the artifact to verify.
    artifact_store:
        Optional dict mapping artifact_id → artifact dict.
        When None, returns an error (store unavailable = fail-closed).

    Returns
    -------
    (is_complete, errors)
    """
    if artifact_store is None:
        return False, [f"{artifact_id}: artifact store unavailable (fail-closed)"]

    visited: set = set()
    queue = [artifact_id]
    errors: List[str] = []

    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)

        artifact = artifact_store.get(current)
        if artifact is None:
            errors.append(f"{current}: artifact not found in store")
            continue

        upstream = artifact.get("upstream_artifacts", [])

        if not upstream:
            # Must be a valid input type to have no upstream
            if artifact.get("artifact_type") not in INPUT_ARTIFACT_TYPES:
                errors.append(
                    f"{current}: no upstream artifacts but artifact_type "
                    f"'{artifact.get('artifact_type')}' is not a recognised input type"
                )
        else:
            for up_id in upstream:
                if up_id not in artifact_store:
                    errors.append(
                        f"{current}: references upstream artifact '{up_id}' which is missing"
                    )
                else:
                    queue.append(up_id)

    return len(errors) == 0, errors
