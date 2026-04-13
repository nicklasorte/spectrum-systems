import pytest

from spectrum_systems.modules.runtime.dag_runtime import build_dependency_graph, detect_cycles, DAGRuntimeError
from spectrum_systems.modules.runtime.ext_runtime import build_runtime_provenance, enforce_constraints, EXTRuntimeError
from spectrum_systems.modules.runtime.jdx_runtime import create_judgment_record, evaluate_judgment, run_jdx_redteam, JDXRuntimeError
from spectrum_systems.modules.runtime.mnt_enforcement_runtime import audit_promotion_entrypoints, consistency_check
from spectrum_systems.modules.runtime.rel_runtime import build_canary_metrics, build_release_record, freeze_on_budget
from spectrum_systems.modules.runtime.rux_runtime import create_reuse_record, enforce_reuse_boundary, RUXRuntimeError
from spectrum_systems.modules.runtime.xpl_runtime import create_artifact_card, XPLRuntimeError


CREATED = "2026-04-13T00:00:00Z"


def test_jdx_fail_closed_without_evidence() -> None:
    with pytest.raises(JDXRuntimeError):
        create_judgment_record(
            evidence_refs=[],
            policy_ref="JDX-POL-1",
            rationale="r",
            contradiction_refs=[],
            uncertainty_flags=[],
            lineage_ref="lin:1",
            created_at=CREATED,
        )


def test_jdx_eval_and_redteam_exploit_signal() -> None:
    rec = create_judgment_record(
        evidence_refs=["ev:1"],
        policy_ref="JDX-POL-1",
        rationale="r",
        contradiction_refs=[],
        uncertainty_flags=["u1"],
        lineage_ref="lin:1",
        created_at=CREATED,
    )
    result = evaluate_judgment(judgment_record=rec, policy_rules=["require_evidence", "require_contradictions"], created_at=CREATED)
    assert result["status"] == "fail"
    rt = run_jdx_redteam(judgment_record=rec, replay_payload={**rec, "rationale": "changed"})
    assert "contradiction_suppression" in rt["findings"]
    assert "non_replayable_judgment" in rt["findings"]


def test_rux_enforcement_and_fail_closed() -> None:
    with pytest.raises(RUXRuntimeError):
        create_reuse_record(asset_ref="a", asset_type="prompt", justification="", scope="s", freshness_hours=1, lineage_ref="lin", active_set_valid=True, created_at=CREATED)
    rec = create_reuse_record(asset_ref="a", asset_type="prompt", justification="valid", scope="s", freshness_hours=24, lineage_ref="lin", active_set_valid=False, created_at=CREATED)
    boundary, report = enforce_reuse_boundary(reuse_record=rec, allowed_scopes={"x"}, freshness_limit_hours=8)
    assert boundary["status"] == "fail"
    assert report["freshness_ok"] is False


def test_xpl_cards_require_limitations() -> None:
    with pytest.raises(XPLRuntimeError):
        create_artifact_card(artifact_family="jdx", generator="g", intended_use="i", limitations=[], evaluation_status="passing", known_risks=["r"], created_at=CREATED)


def test_rel_freeze_and_release_block() -> None:
    canary = build_canary_metrics(sli_name="failure", control_value=0.01, canary_value=0.03, error_budget_remaining=0.0, created_at=CREATED)
    freeze = freeze_on_budget(error_budget_remaining=0.0, created_at=CREATED)
    rel = build_release_record(change_type="schema", canary_metrics=canary, freeze_record=freeze, evidence_refs=["ev:1"], certification_ref="mnt:1", created_at=CREATED)
    assert rel["status"] == "block"


def test_dag_cycle_detection() -> None:
    graph = build_dependency_graph(nodes=["A", "B"], edges=[{"from": "A", "to": "B"}, {"from": "B", "to": "A"}], created_at=CREATED)
    cycle = detect_cycles(graph_record=graph)
    assert cycle["has_cycle"] is True
    with pytest.raises(DAGRuntimeError):
        build_dependency_graph(nodes=["A"], edges=[{"from": "A", "to": "B"}], created_at=CREATED)


def test_ext_constraints_enforced() -> None:
    prov = build_runtime_provenance(runtime_name="sim", runtime_version="1", environment={"a": 1}, inputs={"x": 1}, outputs={"y": 2}, cpu_seconds=10, memory_mb=10, created_at=CREATED)
    enforce = enforce_constraints(provenance=prov, observed_cpu_seconds=12, observed_memory_mb=8)
    assert enforce["status"] == "fail"
    with pytest.raises(EXTRuntimeError):
        build_runtime_provenance(runtime_name="sim", runtime_version="", environment={}, inputs={}, outputs={}, cpu_seconds=0, memory_mb=1, created_at=CREATED)


def test_mnt_coverage_and_consistency() -> None:
    coverage = audit_promotion_entrypoints(observed_entrypoints={"promotion_gate", "release_gate"}, created_at=CREATED)
    assert coverage["status"] == "fail"
    consistency = consistency_check(gate_results={"g1": "pass", "g2": "weird"}, created_at=CREATED)
    assert consistency["status"] == "fail"
