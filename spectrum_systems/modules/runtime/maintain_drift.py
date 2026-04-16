from __future__ import annotations
from typing import Dict
from spectrum_systems.modules.runtime.bne_utils import ensure_contract


def build_maintain_drift_reports(*, trace_id: str, stale_assumptions: int, registry_divergence: int, stale_eval_slices: int) -> Dict[str, Dict[str, any]]:
    maintain = ensure_contract({"artifact_type":"maintain_drift_report","schema_version":"1.0.0","trace_id":trace_id,"outputs":{"stale_assumptions":stale_assumptions,"registry_divergence":registry_divergence,"stale_eval_slices":stale_eval_slices,"severe": registry_divergence>0}}, "maintain_drift_report")
    stale = ensure_contract({"artifact_type":"stale_assumption_report","schema_version":"1.0.0","trace_id":trace_id,"outputs":{"count":stale_assumptions}}, "stale_assumption_report")
    div = ensure_contract({"artifact_type":"registry_divergence_report","schema_version":"1.0.0","trace_id":trace_id,"outputs":{"count":registry_divergence}}, "registry_divergence_report")
    return {"maintain":maintain,"stale":stale,"divergence":div}
