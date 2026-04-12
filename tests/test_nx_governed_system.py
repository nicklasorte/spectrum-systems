from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.nx_governed_intelligence import (
    build_artifact_intelligence_index,
    compute_trust_score,
    evolve_policy_candidates,
    fuse_signals,
    mine_patterns,
)
from spectrum_systems.modules.runtime.nx_governed_system import (
    NXGovernedSystemError,
    cde_consume_nx_preparatory,
    integrate_rqx_review_cycle,
    load_nx_artifact,
    persist_nx_artifact,
    persist_prg_roadmap_candidates,
    sel_enforce_with_authority,
    tlc_route_nx_flow,
    tpa_consume_nx_candidates,
)


def _trace(artifact: dict[str, object], trace: str = "trace-nx") -> dict[str, object]:
    out = dict(artifact)
    out.setdefault("schema_version", "1.0.0")
    out.setdefault("trace_id", trace)
    if out.get("artifact_type") != "artifact_intelligence_index":
        out.setdefault("lineage", {"trace_id": trace, "producer": "RIL"})
    return out


def test_persist_and_load_nx_artifact_round_trip(tmp_path: Path) -> None:
    index = _trace(build_artifact_intelligence_index([{"artifact_id": "a1", "artifact_type": "x", "schema_version": "1", "trace_id": "t", "reason_codes": []}]))
    path = persist_nx_artifact(artifact=index, store_root=tmp_path / "store", trace_id="trace-nx")
    loaded = load_nx_artifact(path)
    assert loaded["artifact_type"] == "artifact_intelligence_index"
    assert loaded["trace_id"] == {"t": ["a1"]}


def test_tlc_routes_nx_flow_without_subsuming_execution(tmp_path: Path) -> None:
    def ril_exec(_: dict[str, object]) -> list[dict[str, object]]:
        pattern = _trace(mine_patterns([{"category": "failure", "motif": "x"}, {"category": "failure", "motif": "x"}]))
        return [pattern]

    handoff = tlc_route_nx_flow(
        run_id="run-1",
        trace_id="trace-1",
        nx_request={"input": True},
        ril_executor=ril_exec,
        store_root=tmp_path / "nx",
    )
    assert handoff["authority_owner"] == "TLC"
    assert handoff["routed_only"] is True
    assert handoff["handoff_to"] == "RIL"


def test_cde_tpa_sel_authority_boundaries_are_fail_closed() -> None:
    fused = _trace(
        fuse_signals(
            {
                "preflight": {"ok": True},
                "eval_summary": {"pass_rate": 1.0},
                "runtime_observability": {"latency": 1},
                "judgment_eval": {"all_required_passed": True},
                "replay_drift": {"drift": False},
                "certification_state": {"certified": True},
            }
        )
    )
    cde_input = cde_consume_nx_preparatory(fused_signal=fused, closure_context={"closure_state": "pending"})
    assert cde_input["requires_cde_decision"] is True

    pattern = _trace(mine_patterns([{"category": "override", "motif": "manual"}, {"category": "override", "motif": "manual"}]))
    candidates = _trace(evolve_policy_candidates(pattern_report=pattern, overrides=[{"trace_id": "t-1"}], precedents=[]))
    tpa_input = tpa_consume_nx_candidates(policy_candidates=candidates, policy_context={"policy": "v1"})
    assert tpa_input["requires_tpa_authority"] is True

    trust = _trace(compute_trust_score({"eval_pass_rate": 0.9, "replay_consistency": 1, "drift": 0.1, "judgment_calibration": 0.9, "certification": 1, "blocker_trend": 0.1}))
    blocked = sel_enforce_with_authority(nx_trust=trust, cde_authority=None, tpa_authority=tpa_input)
    assert blocked["enforcement_allowed"] is False

    allowed = sel_enforce_with_authority(nx_trust=trust, cde_authority=cde_input, tpa_authority=tpa_input)
    assert allowed["enforcement_allowed"] is True


def test_rqx_integration_and_prg_candidate_persistence(tmp_path: Path) -> None:
    review_cycle = {
        "authority_owner": "RQX",
        "trace_id": "trace-rqx",
        "cycle_id": "rqx-001",
        "completed_reviews": [{"review_id": "r1", "finding": "policy drift"}],
    }

    link = integrate_rqx_review_cycle(
        review_cycle=review_cycle,
        ril_interpreter=lambda rows: {
            "pattern_support": [{"pattern": "drift"}],
            "trust_inputs": [{"signal": "stable"}],
            "judgment_support": [{"item": "hold"}],
            "roadmap_candidates": [{"candidate_id": "c1"}],
        },
    )
    assert link["artifact_type"] == "nx_review_intelligence_link_artifact"

    out_path = persist_prg_roadmap_candidates(
        trace_id="trace-prg",
        run_id="run-prg",
        candidates=link["roadmap_candidates"],
        output_path=tmp_path / "prg" / "nx_roadmap_candidate_artifact.json",
    )
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["authority_scope"] == "recommendation_only"
    assert payload["admission_required"] is True


def test_unregistered_artifact_type_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(NXGovernedSystemError, match="unregistered nx artifact_type"):
        persist_nx_artifact(
            artifact={"artifact_type": "unknown_artifact", "schema_version": "1.0.0", "trace_id": "t", "lineage": {"trace_id": "t", "producer": "RIL"}},
            store_root=tmp_path,
            trace_id="t",
        )
