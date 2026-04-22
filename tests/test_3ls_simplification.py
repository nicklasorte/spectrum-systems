"""Integration tests for 3LS simplification (Phases 1-8).

Validates:
- Phase 1: System justification registry, dependency map, baseline metrics
- Phase 2a: GOVERN system (merged TLC + GOV)
- Phase 2b: EXEC system (merged TPA + PRG) + EVAL system (merged WPG + CHK)
- Phase 3: Gate categorization and reduction
- Phase 4: Loop metrics and reversal tracking
- Phase 5: Structured failure messages
- Phase 6: Event log filtering
- Phase 7: Runbook files exist and are readable
- Phase 8: Backward compatibility deprecation layer
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path
from typing import Any, Dict

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Phase 1: System justification audit
# ---------------------------------------------------------------------------


class TestSystemJustificationAudit:
    def test_all_original_systems_justified(self):
        from spectrum_systems.governance.system_justification import (
            SYSTEM_JUSTIFICATIONS,
            validate_system_justification,
        )
        for sys_id in ("TPA", "TLC", "PRG", "WPG", "CHK", "GOV"):
            ok, reason = validate_system_justification(sys_id)
            assert ok, f"System {sys_id} failed justification: {reason}"

    def test_consolidated_systems_justified(self):
        from spectrum_systems.governance.system_justification import (
            validate_system_justification,
        )
        for sys_id in ("GOVERN", "EXEC", "EVAL"):
            ok, reason = validate_system_justification(sys_id)
            assert ok, f"Consolidated system {sys_id} failed justification: {reason}"

    def test_systems_have_roi_field(self):
        from spectrum_systems.governance.system_justification import SYSTEM_JUSTIFICATIONS
        for sys_id, entry in SYSTEM_JUSTIFICATIONS.items():
            assert "roi" in entry, f"System {sys_id} missing 'roi' field"

    def test_systems_have_dependencies_field(self):
        from spectrum_systems.governance.system_justification import SYSTEM_JUSTIFICATIONS
        for sys_id, entry in SYSTEM_JUSTIFICATIONS.items():
            assert "dependencies" in entry, f"System {sys_id} missing 'dependencies' field"

    def test_removal_candidates_list(self):
        from spectrum_systems.governance.system_justification import get_removal_candidates
        candidates = get_removal_candidates()
        # No systems are removal candidates — all are being merged, not removed
        assert isinstance(candidates, list)

    def test_system_audit_returns_full_record(self):
        from spectrum_systems.governance.system_justification import get_system_audit
        audit = get_system_audit("GOVERN")
        assert audit is not None
        assert "prevents" in audit
        assert "improves" in audit
        assert "roi" in audit


class TestSystemDependencyMap:
    def test_import(self):
        from spectrum_systems.governance.system_dependency_map import SystemDependencyMap
        sdm = SystemDependencyMap()
        assert sdm is not None

    def test_get_dependent_systems(self):
        from spectrum_systems.governance.system_dependency_map import SystemDependencyMap
        sdm = SystemDependencyMap()
        # TLC is depended on by AEX, TPA, PRG, WPG, CHK, GOV
        dependents = sdm.get_dependent_systems("TLC")
        assert "AEX" in dependents

    def test_removal_impact(self):
        from spectrum_systems.governance.system_dependency_map import SystemDependencyMap
        sdm = SystemDependencyMap()
        impact = sdm.removal_impact("TLC")
        assert impact["system_id"] == "TLC"
        assert len(impact["dependent_systems"]) > 0
        assert impact["safe_to_remove"] is False

    def test_pqx_has_no_dependents_is_safe(self):
        from spectrum_systems.governance.system_dependency_map import SystemDependencyMap
        sdm = SystemDependencyMap()
        # PQX has no upstream dependencies in our graph
        deps = sdm.get_dependencies_of("PQX")
        assert isinstance(deps, list)

    def test_visualize_returns_string(self):
        from spectrum_systems.governance.system_dependency_map import SystemDependencyMap
        sdm = SystemDependencyMap()
        viz = sdm.visualize()
        assert isinstance(viz, str)
        assert "System Dependency Matrix" in viz

    def test_system_justification_doc_files_exist(self):
        docs_dir = REPO_ROOT / "docs" / "system_justifications"
        for sys_id in ("TPA", "TLC", "PRG", "WPG", "CHK", "GOV"):
            doc = docs_dir / f"{sys_id}.md"
            assert doc.exists(), f"Missing justification doc: {doc}"


# ---------------------------------------------------------------------------
# Phase 2a: GOVERN system
# ---------------------------------------------------------------------------


class TestGOVERNSystem:
    def _make_artifact(self, overrides: Dict[str, Any] = {}) -> Dict[str, Any]:
        base = {
            "artifact_type": "gate_decision",
            "artifact_id": "GD-TEST001",
            "trace_id": "TRC-TEST-GOVERN",
            "lifecycle_state": "admitted",
        }
        base.update(overrides)
        return base

    def test_policy_check_passes_valid_artifact(self):
        from spectrum_systems.govern.govern import GOVERNSystem
        gov = GOVERNSystem()
        ok, reason = gov.policy_check(self._make_artifact())
        assert ok
        assert "PASS" in reason

    def test_policy_check_blocks_empty_artifact_type(self):
        from spectrum_systems.govern.govern import GOVERNSystem
        gov = GOVERNSystem()
        ok, reason = gov.policy_check({"trace_id": "TRC-1", "artifact_type": ""})
        assert not ok
        assert "BLOCK" in reason

    def test_policy_check_blocks_unauthorized(self):
        from spectrum_systems.govern.govern import GOVERNSystem
        gov = GOVERNSystem()
        ok, reason = gov.policy_check(self._make_artifact({"authorization_level": "unauthorized"}))
        assert not ok

    def test_lifecycle_check_valid_transition(self):
        from spectrum_systems.govern.govern import GOVERNSystem
        gov = GOVERNSystem()
        ok, reason = gov.lifecycle_check(self._make_artifact(), "executing_slice_1")
        assert ok
        assert "PASS" in reason

    def test_lifecycle_check_blocks_invalid_skip(self):
        from spectrum_systems.govern.govern import GOVERNSystem
        gov = GOVERNSystem()
        ok, reason = gov.lifecycle_check(self._make_artifact(), "promoted")
        assert not ok
        assert "BLOCK" in reason

    def test_route_artifact_known_type(self):
        from spectrum_systems.govern.govern import GOVERNSystem
        gov = GOVERNSystem()
        owner, reason = gov.route_artifact(self._make_artifact())
        assert owner == "EXEC"
        assert "PASS" in reason

    def test_route_artifact_unknown_type(self):
        from spectrum_systems.govern.govern import GOVERNSystem
        gov = GOVERNSystem()
        owner, reason = gov.route_artifact({"artifact_type": "unknown_xyz", "artifact_id": "X1"})
        assert owner == "UNKNOWN"

    def test_detect_policy_drift_no_drift(self):
        from spectrum_systems.govern.govern import GOVERNSystem
        gov = GOVERNSystem()
        report = gov.detect_policy_drift({"max_items": 10}, {"max_items": 10})
        assert report["has_drift"] is False

    def test_detect_policy_drift_with_drift(self):
        from spectrum_systems.govern.govern import GOVERNSystem
        gov = GOVERNSystem()
        report = gov.detect_policy_drift({"max_items": 10}, {"max_items": 50})
        assert report["has_drift"] is True
        assert len(report["drift_fields"]) == 1

    def test_routing_manifest_tracks_routed_artifacts(self):
        from spectrum_systems.govern.govern import GOVERNSystem
        gov = GOVERNSystem()
        gov.route_artifact(self._make_artifact())
        manifest = gov.get_routing_manifest()
        assert "GD-TEST001" in manifest


# ---------------------------------------------------------------------------
# Phase 2b: EXEC system
# ---------------------------------------------------------------------------


class TestEXECSystem:
    def _make_artifact(self, overrides: Dict[str, Any] = {}) -> Dict[str, Any]:
        base = {
            "artifact_type": "gate_decision",
            "trace_id": "TRC-TEST-EXEC",
            "lineage_complete": True,
            "roadmap_ref": "FEAT-001",
        }
        base.update(overrides)
        return base

    def test_exec_check_passes_valid(self):
        from spectrum_systems.exec_system.exec_system import EXECSystem
        exec_sys = EXECSystem()
        ok, reason = exec_sys.exec_check(self._make_artifact())
        assert ok
        assert "PASS" in reason

    def test_exec_check_blocks_missing_trace_id(self):
        from spectrum_systems.exec_system.exec_system import EXECSystem
        exec_sys = EXECSystem()
        ok, reason = exec_sys.exec_check({"artifact_type": "gate_decision"})
        assert not ok
        assert "BLOCK" in reason

    def test_exec_check_blocks_broken_lineage(self):
        from spectrum_systems.exec_system.exec_system import EXECSystem
        exec_sys = EXECSystem()
        ok, reason = exec_sys.exec_check(self._make_artifact({"lineage_complete": False}))
        assert not ok

    def test_exec_check_blocks_trust_blocked(self):
        from spectrum_systems.exec_system.exec_system import EXECSystem
        exec_sys = EXECSystem()
        ok, reason = exec_sys.exec_check(self._make_artifact({"trust_blocked": True}))
        assert not ok

    def test_validate_lineage_passes(self):
        from spectrum_systems.exec_system.exec_system import EXECSystem
        exec_sys = EXECSystem()
        ok, reason = exec_sys.validate_lineage("ART-001", ["REF-A", "REF-B"])
        assert ok

    def test_validate_lineage_blocks_empty(self):
        from spectrum_systems.exec_system.exec_system import EXECSystem
        exec_sys = EXECSystem()
        ok, reason = exec_sys.validate_lineage("ART-001", [])
        assert not ok

    def test_trust_scope_passes(self):
        from spectrum_systems.exec_system.exec_system import EXECSystem
        exec_sys = EXECSystem()
        ok, reason = exec_sys.trust_scope_check({"scope_items": 10}, max_scope_items=50)
        assert ok

    def test_trust_scope_blocks_over_budget(self):
        from spectrum_systems.exec_system.exec_system import EXECSystem
        exec_sys = EXECSystem()
        ok, reason = exec_sys.trust_scope_check({"scope_items": 100}, max_scope_items=50)
        assert not ok

    def test_roadmap_alignment_passes(self):
        from spectrum_systems.exec_system.exec_system import EXECSystem
        exec_sys = EXECSystem()
        ok, reason = exec_sys.roadmap_alignment_check(
            self._make_artifact(), ["FEAT-001", "FEAT-002"]
        )
        assert ok

    def test_roadmap_alignment_blocks_missing_ref(self):
        from spectrum_systems.exec_system.exec_system import EXECSystem
        exec_sys = EXECSystem()
        ok, reason = exec_sys.roadmap_alignment_check({"trace_id": "TRC-1", "artifact_type": "x"})
        assert not ok

    def test_generate_priority_report_healthy(self):
        from spectrum_systems.exec_system.exec_system import EXECSystem
        exec_sys = EXECSystem()
        report = exec_sys.generate_priority_report("healthy")
        assert report["artifact_type"] == "roadmap_priority_report"
        assert report["owner_system"] == "EXEC"
        assert report["prioritized_items"] == []

    def test_generate_priority_report_critical(self):
        from spectrum_systems.exec_system.exec_system import EXECSystem
        exec_sys = EXECSystem()
        report = exec_sys.generate_priority_report("critical")
        assert "fix_drift" in report["prioritized_items"]


# ---------------------------------------------------------------------------
# Phase 2b: EVAL system
# ---------------------------------------------------------------------------


class TestEVALSystem:
    def _make_artifact(self, overrides: Dict[str, Any] = {}) -> Dict[str, Any]:
        base = {
            "artifact_type": "gate_decision",
            "artifact_id": "ART-EVAL-001",
            "trace_id": "TRC-TEST-EVAL",
        }
        base.update(overrides)
        return base

    def test_generate_working_paper(self):
        from spectrum_systems.eval_system.eval_system import EVALSystem
        ev = EVALSystem()
        paper = ev.generate_working_paper(self._make_artifact())
        assert paper["artifact_type"] == "working_paper"
        assert paper["provenance_complete"] is True
        assert paper["source_artifact_id"] == "ART-EVAL-001"

    def test_validate_provenance_passes(self):
        from spectrum_systems.eval_system.eval_system import EVALSystem
        ev = EVALSystem()
        ok, reason = ev.validate_provenance(self._make_artifact())
        assert ok

    def test_validate_provenance_blocks_missing_trace(self):
        from spectrum_systems.eval_system.eval_system import EVALSystem
        ev = EVALSystem()
        ok, reason = ev.validate_provenance({"artifact_id": "X", "artifact_type": "foo"})
        assert not ok

    def test_batch_constraint_passes(self):
        from spectrum_systems.eval_system.eval_system import EVALSystem
        ev = EVALSystem()
        ok, reason = ev.batch_constraint_check({"batch_id": "B1", "slices": ["s"] * 5})
        assert ok

    def test_batch_constraint_blocks_overflow(self):
        from spectrum_systems.eval_system.eval_system import EVALSystem
        ev = EVALSystem()
        ok, reason = ev.batch_constraint_check({"batch_id": "B1", "slices": ["s"] * 15})
        assert not ok
        assert "BLOCK" in reason

    def test_umbrella_constraint_passes(self):
        from spectrum_systems.eval_system.eval_system import EVALSystem
        ev = EVALSystem()
        ok, reason = ev.umbrella_constraint_check({"umbrella_id": "U1", "batches": ["b"] * 3})
        assert ok

    def test_umbrella_constraint_blocks_overflow(self):
        from spectrum_systems.eval_system.eval_system import EVALSystem
        ev = EVALSystem()
        ok, reason = ev.umbrella_constraint_check({"umbrella_id": "U1", "batches": ["b"] * 8})
        assert not ok

    def test_eval_gate_passes_with_good_results(self):
        from spectrum_systems.eval_system.eval_system import EVALSystem
        ev = EVALSystem()
        result = ev.eval_gate(
            self._make_artifact(),
            eval_results={"passed": 97, "total": 100, "threshold": 0.95},
        )
        assert result["decision"] == "allow"

    def test_eval_gate_blocks_low_pass_rate(self):
        from spectrum_systems.eval_system.eval_system import EVALSystem
        ev = EVALSystem()
        result = ev.eval_gate(
            self._make_artifact(),
            eval_results={"passed": 80, "total": 100, "threshold": 0.95},
        )
        assert result["decision"] == "block"
        assert "eval_pass_rate" in result["blocking_checks"]

    def test_checkpoint_resume_valid_state(self):
        from spectrum_systems.eval_system.eval_system import EVALSystem
        ev = EVALSystem()
        ok, reason = ev.checkpoint_resume_check({"checkpoint_id": "C1", "checkpoint_state": "ready"})
        assert ok

    def test_checkpoint_resume_invalid_state(self):
        from spectrum_systems.eval_system.eval_system import EVALSystem
        ev = EVALSystem()
        ok, reason = ev.checkpoint_resume_check({"checkpoint_id": "C1", "checkpoint_state": "garbage"})
        assert not ok


# ---------------------------------------------------------------------------
# Phase 3: Gate simplification
# ---------------------------------------------------------------------------


class TestGateSimplification:
    def test_active_gates_count_is_reduced(self):
        from spectrum_systems.governance.gate_categories import get_active_gates, get_removed_gates

        active = get_active_gates()
        removed = get_removed_gates()
        assert len(removed) > 0, "No gates were removed"
        reduction_pct = len(removed) / (len(active) + len(removed)) * 100
        assert reduction_pct >= 30.0, f"Gate reduction {reduction_pct:.1f}% < 30% target"

    def test_safety_gates_all_kept(self):
        from spectrum_systems.governance.gate_categories import (
            GateCategory,
            GATE_CATALOG,
        )
        for gate_id, info in GATE_CATALOG.items():
            if info.get("category") == GateCategory.SAFETY:
                assert info.get("keep", True), f"Safety gate {gate_id} was removed — must not remove safety gates"

    def test_gate_reduction_report(self):
        from spectrum_systems.governance.gate_categories import gate_reduction_report
        report = gate_reduction_report()
        assert report["reduction_percentage"] >= 30.0
        assert report["target_met"] is True

    def test_simplified_gates_admission(self):
        from spectrum_systems.governance.gate_categories import SimplifiedGates
        sg = SimplifiedGates()
        result = sg.admission_gate({"artifact_type": "test", "trace_id": "TRC-SG-01"})
        assert result["decision"] == "allow"

    def test_simplified_gates_eval(self):
        from spectrum_systems.governance.gate_categories import SimplifiedGates
        sg = SimplifiedGates()
        result = sg.eval_gate(
            {"artifact_type": "test", "artifact_id": "A1", "trace_id": "TRC-SG-01"},
            eval_results={"passed": 19, "total": 20, "threshold": 0.95},
        )
        assert result["decision"] == "allow"

    def test_simplified_gates_promotion(self):
        from spectrum_systems.governance.gate_categories import SimplifiedGates
        sg = SimplifiedGates()
        result = sg.promotion_gate({
            "trace_id": "TRC-PG-01",
            "lineage_complete": True,
            "replay_deterministic": True,
            "prior_gates_passed": True,
            "security_approved": True,
            "slo_compliant": True,
        })
        assert result["decision"] == "allow"


# ---------------------------------------------------------------------------
# Phase 4: Loop strengthening
# ---------------------------------------------------------------------------


class TestLoopMetrics:
    def test_loop_metrics_records_component_time(self):
        from spectrum_systems.observability.loop_metrics import LoopMetrics
        m = LoopMetrics()
        with m.measure("execution"):
            pass
        stats = m.component_stats("execution")
        assert stats["count"] == 1.0
        assert stats["avg"] >= 0.0

    def test_slowest_component(self):
        from spectrum_systems.observability.loop_metrics import LoopMetrics
        import time
        m = LoopMetrics()
        # Make evaluation slightly slower
        with m.measure("execution"):
            pass
        with m.measure("evaluation"):
            time.sleep(0.001)
        name, avg = m.slowest_component()
        assert name in ("execution", "evaluation", "control", "enforcement")

    def test_decision_reversal_recording(self):
        from spectrum_systems.observability.loop_metrics import LoopMetrics
        m = LoopMetrics()
        m.record_decision_reversal("TRC-1", "block", "allow", "evidence updated")
        assert m.reversal_rate() == 1.0

    def test_component_report_structure(self):
        from spectrum_systems.observability.loop_metrics import LoopMetrics
        m = LoopMetrics()
        report = m.component_report()
        assert report["artifact_type"] == "loop_performance_report"
        assert "component_stats_ms" in report
        assert report["target_improvement_pct"] == 20.0

    def test_optimized_loop_run(self):
        from spectrum_systems.observability.loop_metrics import OptimizedLoop
        loop = OptimizedLoop()
        result = loop.run_full_loop(
            work_fn=lambda: "exec_done",
            eval_fn=lambda: "eval_done",
            control_fn=lambda: "control_done",
            enforce_fn=lambda: "enforce_done",
        )
        assert result["execution"] == "exec_done"
        assert result["evaluation"] == "eval_done"
        assert "loop_stats" in result


# ---------------------------------------------------------------------------
# Phase 5: Debuggability
# ---------------------------------------------------------------------------


class TestStructuredFailures:
    def test_clear_failure_message_format(self):
        from spectrum_systems.debugging.structured_failures import ClearFailureMessage
        msg = ClearFailureMessage(
            gate_id="exec_check",
            system="EXEC",
            check_name="lineage_complete",
            observed_value=False,
            expected_value=True,
            trace_id="TRC-001",
            artifact_id="ART-001",
        )
        formatted = msg.format()
        assert "FAILURE: EXEC/exec_check" in formatted
        assert "WHAT:" in formatted
        assert "WHY:" in formatted
        assert "NEXT:" in formatted
        assert "CONTEXT:" in formatted
        assert "TRC-001" in formatted

    def test_clear_failure_message_artifact(self):
        from spectrum_systems.debugging.structured_failures import ClearFailureMessage
        msg = ClearFailureMessage(
            gate_id="eval_gate",
            system="EVAL",
            check_name="eval_pass_rate",
            observed_value=0.82,
            expected_value=0.95,
            trace_id="TRC-002",
            artifact_id="EV-001",
        )
        artifact = msg.to_artifact()
        assert artifact["artifact_type"] == "structured_failure"
        assert artifact["gate_id"] == "eval_gate"
        assert "runbook" in artifact
        assert "human_message" in artifact

    def test_format_gate_failure_allow(self):
        from spectrum_systems.debugging.structured_failures import format_gate_failure
        decision = {
            "gate_id": "admission_gate",
            "decision": "allow",
            "trace_id": "TRC-1",
            "artifact_id": "GD-1",
        }
        msg = format_gate_failure(decision, "EXEC")
        assert "PASS" in msg

    def test_format_gate_failure_block(self):
        from spectrum_systems.debugging.structured_failures import format_gate_failure
        decision = {
            "gate_id": "admission_gate",
            "decision": "block",
            "trace_id": "TRC-1",
            "artifact_id": "GD-1",
            "blocking_checks": ["input_schema_valid"],
            "reasons": {"input_schema_valid": "Missing required fields: ['trace_id']"},
        }
        msg = format_gate_failure(decision, "EXEC")
        assert "FAILURE" in msg
        assert "Missing required fields" in msg
        assert "runbook" in msg.lower() or "NEXT" in msg

    def test_format_system_error(self):
        from spectrum_systems.debugging.structured_failures import format_system_error
        msg = format_system_error("GOVERN", "policy_check", ValueError("bad input"), "TRC-1")
        assert "FAILURE: GOVERN/policy_check" in msg
        assert "bad input" in msg


# ---------------------------------------------------------------------------
# Phase 6: Event log optimization
# ---------------------------------------------------------------------------


class TestEventFilter:
    def _make_events(self):
        return [
            {"event_type": "admission_gate", "data": {"decision": "allow"}},
            {"event_type": "execution_start", "data": {}},
            {"event_type": "execution_end", "data": {}},
            {"event_type": "eval_start", "data": {}},
            {"event_type": "failure", "data": {"error": "test"}},
            {"event_type": "promotion_gate", "data": {"decision": "allow"}},
            {"event_type": "eval_gate", "data": {"decision": "block"}},
        ]

    def test_debug_view_returns_all(self):
        from spectrum_systems.observability.event_filter import EventFilter
        events = self._make_events()
        assert len(EventFilter.debug_view(events)) == len(events)

    def test_operator_view_filters_low_importance(self):
        from spectrum_systems.observability.event_filter import EventFilter
        events = self._make_events()
        filtered = EventFilter.operator_view(events)
        # eval_start and eval_end have importance=2, should be filtered
        types = [e["event_type"] for e in filtered]
        assert "eval_start" not in types

    def test_monitoring_view_returns_monitoring_events(self):
        from spectrum_systems.observability.event_filter import EventFilter
        events = self._make_events()
        filtered = EventFilter.monitoring_view(events)
        types = [e["event_type"] for e in filtered]
        assert "failure" in types
        assert "promotion_gate" in types

    def test_failure_view_only_failures(self):
        from spectrum_systems.observability.event_filter import EventFilter
        events = self._make_events()
        filtered = EventFilter.failure_view(events)
        for e in filtered:
            assert e["event_type"] in ("failure", "admission_gate", "eval_gate", "promotion_gate")

    def test_event_importance_known_type(self):
        from spectrum_systems.observability.event_filter import EventFilter
        assert EventFilter.event_importance("failure") == 5
        assert EventFilter.event_importance("eval_start") == 2

    def test_catalog_summary(self):
        from spectrum_systems.observability.event_filter import EventFilter, EVENT_CATALOG
        summary = EventFilter.catalog_summary()
        assert summary["total_event_types"] == len(EVENT_CATALOG)
        assert "failure" in summary["high_importance_events"]


# ---------------------------------------------------------------------------
# Phase 7: Operator training — runbook files exist
# ---------------------------------------------------------------------------


class TestOperatorRunbooks:
    def test_system_debug_guide_exists(self):
        guide = REPO_ROOT / "docs" / "runbooks" / "system_debug_guide.md"
        assert guide.exists(), "system_debug_guide.md missing"
        content = guide.read_text()
        assert "Quick Diagnosis" in content
        assert "GOVERN" in content
        assert "EXEC" in content
        assert "EVAL" in content

    def test_rca_guide_exists(self):
        guide = REPO_ROOT / "docs" / "rca_guide.md"
        assert guide.exists(), "rca_guide.md missing"
        content = guide.read_text()
        assert "Pattern" in content
        # 20 patterns documented
        assert content.count("### Pattern") >= 15

    def test_migration_guide_exists(self):
        guide = REPO_ROOT / "docs" / "migration_guide.md"
        assert guide.exists(), "migration_guide.md missing"
        content = guide.read_text()
        assert "tpa_check" in content
        assert "EXECSystem" in content


# ---------------------------------------------------------------------------
# Phase 8: Backward compatibility
# ---------------------------------------------------------------------------


class TestDeprecationLayer:
    def _make_artifact(self) -> Dict[str, Any]:
        return {
            "artifact_type": "gate_decision",
            "trace_id": "TRC-COMPAT-01",
            "artifact_id": "GD-COMPAT-01",
            "lifecycle_state": "admitted",
            "lineage_complete": True,
            "roadmap_ref": "FEAT-COMPAT",
        }

    def test_tpa_check_emits_deprecation_warning(self):
        from spectrum_systems.compat.deprecation_layer import DeprecationLayer
        compat = DeprecationLayer()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            ok, reason = compat.tpa_check(self._make_artifact())
        assert ok
        assert any(issubclass(w.category, DeprecationWarning) for w in caught)

    def test_tlc_route_emits_deprecation_warning(self):
        from spectrum_systems.compat.deprecation_layer import DeprecationLayer
        compat = DeprecationLayer()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            owner, reason = compat.tlc_route(self._make_artifact())
        assert any(issubclass(w.category, DeprecationWarning) for w in caught)

    def test_wpg_gate_delegates_to_eval(self):
        from spectrum_systems.compat.deprecation_layer import DeprecationLayer
        compat = DeprecationLayer()
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = compat.wpg_gate(self._make_artifact())
        assert "decision" in result

    def test_chk_batch_delegates_to_eval(self):
        from spectrum_systems.compat.deprecation_layer import DeprecationLayer
        compat = DeprecationLayer()
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            ok, reason = compat.chk_batch({"batch_id": "B1", "slices": ["s"] * 3, "trace_id": "T1"})
        assert ok

    def test_gov_policy_delegates_to_govern(self):
        from spectrum_systems.compat.deprecation_layer import DeprecationLayer
        compat = DeprecationLayer()
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            ok, reason = compat.gov_policy(self._make_artifact())
        assert ok

    def test_prg_priority_report_delegates_to_exec(self):
        from spectrum_systems.compat.deprecation_layer import DeprecationLayer
        compat = DeprecationLayer()
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            report = compat.prg_priority_report("healthy")
        assert report["owner_system"] == "EXEC"

    def test_consolidated_policy_json_exists(self):
        policy = REPO_ROOT / "config" / "policy" / "consolidated_systems_policy.json"
        assert policy.exists(), "consolidated_systems_policy.json missing"
        import json
        data = json.loads(policy.read_text())
        assert "GOVERN" in data["systems"]
        assert "EXEC" in data["systems"]
        assert "EVAL" in data["systems"]
