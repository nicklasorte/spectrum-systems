from __future__ import annotations
from typing import Dict, List
from spectrum_systems.modules.runtime.bne_utils import ensure_contract


def evaluate_precedent_ranking(*, trace_id: str, ranked: List[Dict[str, any]]) -> Dict[str, any]:
    score = round(sum(float(r.get("score", 0.0)) for r in ranked) / max(len(ranked), 1), 3)
    return ensure_contract({"artifact_type": "precedent_ranking_evaluation_record", "schema_version": "1.0.0", "trace_id": trace_id, "outputs": {"quality_score": score, "decision": "BLOCK" if score < 0.5 else "ALLOW"}}, "precedent_ranking_evaluation_record")
