"""Phase 3.4: Consistency Checker

Detect state corruption across runs.
Block promotion if inconsistency detected.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Tuple


class ConsistencyChecker:
    """Check consistency of artifacts across runs."""

    @staticmethod
    def _hash_artifact(artifact: Dict[str, Any]) -> str:
        """Hash artifact data deterministically."""
        serialised = json.dumps(artifact, sort_keys=True, default=str)
        return hashlib.sha256(serialised.encode()).hexdigest()

    def check_artifact_consistency(
        self,
        artifact_id: str,
        artifacts_across_runs: List[Dict[str, Any]],
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check if artifact is consistent (same hash) across multiple runs."""
        if not artifacts_across_runs:
            return False, {"reason": "No artifacts to check"}

        hashes = [self._hash_artifact(art) for art in artifacts_across_runs]
        unique_hashes = set(hashes)

        if len(unique_hashes) == 1:
            return True, {
                "artifact_id": artifact_id,
                "consistency": True,
                "runs_checked": len(artifacts_across_runs),
            }

        return False, {
            "artifact_id": artifact_id,
            "consistency": False,
            "reason": "Data inconsistency detected across runs",
            "unique_hashes": len(unique_hashes),
        }

    def check_lineage_integrity(
        self,
        artifact_id: str,
        lineage_chain: List[Dict[str, Any]],
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check if lineage chain is intact (no orphaned artifacts)."""
        if not lineage_chain:
            return False, {"reason": "Lineage chain empty"}

        for i in range(len(lineage_chain) - 1):
            current = lineage_chain[i]
            nxt = lineage_chain[i + 1]
            produced_from = nxt.get("produced_from", [])
            if current.get("artifact_id") not in produced_from:
                return False, {
                    "artifact_id": artifact_id,
                    "lineage_integrity": False,
                    "broken_link": (
                        current.get("artifact_id"),
                        nxt.get("artifact_id"),
                    ),
                }

        return True, {
            "artifact_id": artifact_id,
            "lineage_integrity": True,
            "chain_length": len(lineage_chain),
        }
