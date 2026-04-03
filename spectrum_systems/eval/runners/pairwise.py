from __future__ import annotations

from typing import Any, Dict


def run_pairwise_eval(champion: Dict[str, Any], challenger: Dict[str, Any]) -> Dict[str, Any]:
    champion_score = float(champion.get("score", 0.0))
    challenger_score = float(challenger.get("score", 0.0))
    winner = "tie"
    if challenger_score > champion_score:
        winner = "challenger"
    elif champion_score > challenger_score:
        winner = "champion"
    return {
        "artifact_type": "model_route_comparison_record",
        "schema_version": "1.0.0",
        "comparison_id": "mrc-" + f"{abs(hash((champion_score, challenger_score))) & ((1<<64)-1):016x}",
        "route_key": str(champion.get("route_key", "default.route")),
        "champion_model_id": str(champion.get("model_id", "unknown")),
        "challenger_model_id": str(challenger.get("model_id", "unknown")),
        "winner": winner,
        "metrics": {"champion_score": champion_score, "challenger_score": challenger_score},
    }
