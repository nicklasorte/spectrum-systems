"""REP: Replay determinism gate.

Before promotion, execution slices are replayed and their output hashes compared.
Divergence (non-identical hashes) blocks promotion.
"""

from __future__ import annotations

from typing import Dict, List


def check_replay_determinism(artifact_id: str, hashes: List[str]) -> Dict:
    """Validate that all provided hashes are identical (deterministic replay).

    Parameters
    ----------
    artifact_id:
        The artifact being validated.
    hashes:
        List of output hashes from replay runs (including the original).

    Returns
    -------
    {deterministic, artifact_id, hash_variance, hashes}
    """
    if not hashes:
        return {
            "artifact_id": artifact_id,
            "deterministic": False,
            "hash_variance": 0,
            "hashes": [],
            "reason": "No hashes provided (fail-closed)",
        }

    unique = set(hashes)
    deterministic = len(unique) == 1

    return {
        "artifact_id": artifact_id,
        "deterministic": deterministic,
        "hash_variance": len(unique),
        "hashes": hashes,
        "reason": "All replays match" if deterministic else f"{len(unique)} distinct hashes detected",
    }
