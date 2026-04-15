from __future__ import annotations

from spectrum_systems.modules.wpg.judgment import evaluate_judgment


def test_judgment_eval_blocks_on_missing_precedent() -> None:
    judgment = {"artifact_id": "j1", "rationale_summary": "r"}
    precedent = {"precedents": []}
    out = evaluate_judgment(judgment_record=judgment, precedent_retrieval=precedent, trace_id="t1")
    assert out["evaluation_refs"]["control_decision"]["decision"] == "BLOCK"
