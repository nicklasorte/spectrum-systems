"""Phase 3.3: Replay Verifier

Verify execution determinism by replaying N times.
Block promotion if any divergence detected.
"""

from __future__ import annotations

import hashlib
import json
import random
from typing import Any, Callable, Dict, List, Tuple


class ReplayVerifier:
    """Verify execution determinism across multiple replays."""

    def __init__(self) -> None:
        self.run_hashes: List[str] = []

    @staticmethod
    def _hash_output(output: Any) -> str:
        """Compute SHA-256 hash of serialised output."""
        serialised = json.dumps(output, sort_keys=True, default=str)
        return hashlib.sha256(serialised.encode()).hexdigest()

    def verify_determinism(
        self,
        artifact_id: str,
        execution_fn: Callable[[], Any],
        num_replays: int = 5,
        seed: int = 42,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Replay execution *num_replays* times; all outputs must hash identically."""
        hashes: List[str] = []

        for run_num in range(num_replays):
            random.seed(seed)
            try:
                output = execution_fn()
                hashes.append(self._hash_output(output))
            except Exception as exc:
                return False, {
                    "artifact_id": artifact_id,
                    "determinism": False,
                    "reason": f"Execution failed on run {run_num}: {exc}",
                }

        self.run_hashes = hashes
        unique_hashes = set(hashes)

        if len(unique_hashes) == 1:
            return True, {
                "artifact_id": artifact_id,
                "determinism": True,
                "hash": hashes[0],
                "replays": num_replays,
            }

        return False, {
            "artifact_id": artifact_id,
            "determinism": False,
            "reason": "Output divergence detected across replays",
            "unique_hashes": len(unique_hashes),
            "hashes": hashes,
        }
