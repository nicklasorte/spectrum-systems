from __future__ import annotations

from spectrum_systems.modules.wpg.judgment import retrieve_precedent


def test_precedent_retrieval_ranks_records() -> None:
    judgment = {"artifact_id": "j1", "rationale_summary": "a;b"}
    prior = [{"artifact_id": "j0", "rationale_summary": "a;c"}]
    out = retrieve_precedent(judgment_record=judgment, prior_records=prior, trace_id="t1")
    assert out["precedents"][0]["record_ref"] == "j0"
