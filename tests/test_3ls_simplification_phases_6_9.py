"""Phase 6-9 validation tests: Event filtering, operator training artifacts,
backward compatibility, and final integration.

Covers:
  Phase 6: EventAnalysis, EventFilter views, RCAWithFiltering
  Phase 7: Runbook and training file existence + content checks
  Phase 8: DeprecationLayer, MigrationTimeline
  Phase 9: End-to-end metrics and zero-regression checks
"""

import os
import json
import warnings
import pytest


# ---------------------------------------------------------------------------
# Phase 6: Event Log Optimization
# ---------------------------------------------------------------------------


class TestEventAnalysis:
    def setup_method(self):
        from spectrum_systems.observability.event_analysis import EventAnalysis
        self.analysis = EventAnalysis()

    def test_taxonomy_has_all_required_categories(self):
        taxonomy = self.analysis.get_taxonomy()
        categories = {v["category"] for v in taxonomy.values()}
        assert "EXECUTION" in categories
        assert "EVAL" in categories
        assert "CONTROL" in categories
        assert "ENFORCE" in categories
        assert "DEBUG" in categories

    def test_all_events_have_required_fields(self):
        taxonomy = self.analysis.get_taxonomy()
        required = {"category", "purpose", "debug", "monitoring", "importance",
                    "filter_by_default", "show_in_rca"}
        for event_type, meta in taxonomy.items():
            missing = required - set(meta.keys())
            assert not missing, f"{event_type} missing fields: {missing}"

    def test_importance_values_in_valid_range(self):
        taxonomy = self.analysis.get_taxonomy()
        for event_type, meta in taxonomy.items():
            imp = meta["importance"]
            assert 1 <= imp <= 5, f"{event_type} has importance={imp}, must be 1-5"

    def test_usefulness_report_target_met(self):
        report = self.analysis.usefulness_report()
        assert report["target_met"] is True
        assert report["improved_usefulness"] >= 0.90
        assert report["baseline_usefulness"] == 0.65
        assert report["improvement_delta"] > 0

    def test_usefulness_report_has_all_fields(self):
        report = self.analysis.usefulness_report()
        for field in ("baseline_usefulness", "total_event_types", "filtered_by_default",
                      "retained_in_operator_view", "filter_percentage",
                      "improved_usefulness", "improvement_delta", "target_met"):
            assert field in report, f"usefulness_report missing field: {field}"

    def test_events_for_rca_subset_of_taxonomy(self):
        all_events = set(self.analysis.get_taxonomy().keys())
        rca_events = set(self.analysis.events_for_rca().keys())
        assert rca_events.issubset(all_events)

    def test_events_by_category_covers_all(self):
        taxonomy = self.analysis.get_taxonomy()
        by_cat = self.analysis.events_by_category()
        all_from_cats = [e for events in by_cat.values() for e in events]
        assert set(all_from_cats) == set(taxonomy.keys())

    def test_debug_events_not_shown_in_rca(self):
        rca_events = self.analysis.events_for_rca()
        taxonomy = self.analysis.get_taxonomy()
        for et, meta in taxonomy.items():
            if meta["category"] == "DEBUG":
                assert et not in rca_events, \
                    f"DEBUG event {et!r} should not appear in RCA events"

    def test_high_importance_events_not_filtered_by_default(self):
        taxonomy = self.analysis.get_taxonomy()
        for et, meta in taxonomy.items():
            if meta["importance"] == 5:
                assert not meta["filter_by_default"], \
                    f"importance=5 event {et!r} should not be filtered by default"


class TestEventFilter:
    def _make_events(self):
        return [
            {"event_type": "execution_start",  "trace_id": "T1", "data": {}},
            {"event_type": "execution_end",    "trace_id": "T1", "data": {}},
            {"event_type": "execution_error",  "trace_id": "T1", "data": {}},
            {"event_type": "eval_gate",        "trace_id": "T1", "data": {"decision": "block"}},
            {"event_type": "failure",          "trace_id": "T1", "data": {}},
            {"event_type": "eval_gate_pass",   "trace_id": "T1", "data": {}},
            {"event_type": "debug_context",    "trace_id": "T1", "data": {}},
            {"event_type": "debug_trace",      "trace_id": "T1", "data": {}},
            {"event_type": "lifecycle_transition", "trace_id": "T1", "data": {}},
        ]

    def test_debug_view_returns_all_events(self):
        from spectrum_systems.observability.event_filter import EventFilter
        events = self._make_events()
        result = EventFilter.debug_view(events)
        assert len(result) == len(events)

    def test_operator_view_excludes_low_importance(self):
        from spectrum_systems.observability.event_filter import EventFilter
        events = self._make_events()
        result = EventFilter.operator_view(events)
        types = {e["event_type"] for e in result}
        assert "debug_context" not in types
        assert "debug_trace" not in types
        assert "eval_gate_pass" not in types

    def test_operator_view_includes_high_importance(self):
        from spectrum_systems.observability.event_filter import EventFilter
        events = self._make_events()
        result = EventFilter.operator_view(events)
        types = {e["event_type"] for e in result}
        assert "execution_error" in types
        assert "eval_gate" in types
        assert "failure" in types

    def test_monitoring_view_only_monitoring_flagged(self):
        from spectrum_systems.observability.event_filter import EventFilter, EVENT_CATALOG
        events = self._make_events()
        result = EventFilter.monitoring_view(events)
        for e in result:
            et = e["event_type"]
            assert EVENT_CATALOG.get(et, {}).get("monitoring", False), \
                f"{et} in monitoring_view but monitoring=False in catalog"

    def test_failure_view_includes_failures(self):
        from spectrum_systems.observability.event_filter import EventFilter
        events = self._make_events()
        result = EventFilter.failure_view(events)
        types = {e["event_type"] for e in result}
        assert "failure" in types

    def test_failure_view_includes_blocked_gates(self):
        from spectrum_systems.observability.event_filter import EventFilter
        events = self._make_events()
        result = EventFilter.failure_view(events)
        # eval_gate with decision=block should appear
        gate_events = [e for e in result if e["event_type"] == "eval_gate"]
        assert len(gate_events) == 1

    def test_performance_view_includes_execution_events(self):
        from spectrum_systems.observability.event_filter import EventFilter
        events = self._make_events()
        result = EventFilter.performance_view(events)
        types = {e["event_type"] for e in result}
        assert "execution_start" in types
        assert "execution_end" in types
        assert "execution_error" in types

    def test_performance_view_excludes_debug(self):
        from spectrum_systems.observability.event_filter import EventFilter
        events = self._make_events()
        result = EventFilter.performance_view(events)
        types = {e["event_type"] for e in result}
        assert "debug_context" not in types
        assert "debug_trace" not in types

    def test_event_importance_returns_int_in_range(self):
        from spectrum_systems.observability.event_filter import EventFilter, EVENT_CATALOG
        for et in EVENT_CATALOG:
            imp = EventFilter.event_importance(et)
            assert 1 <= imp <= 5

    def test_event_importance_unknown_type_defaults_to_3(self):
        from spectrum_systems.observability.event_filter import EventFilter
        assert EventFilter.event_importance("nonexistent_event") == 3

    def test_catalog_summary_structure(self):
        from spectrum_systems.observability.event_filter import EventFilter
        summary = EventFilter.catalog_summary()
        assert "total_event_types" in summary
        assert "monitoring_events" in summary
        assert "debug_only_events" in summary
        assert "high_importance_events" in summary
        assert summary["total_event_types"] > 0

    def test_debug_view_does_not_mutate_input(self):
        from spectrum_systems.observability.event_filter import EventFilter
        events = self._make_events()
        original_len = len(events)
        EventFilter.debug_view(events)
        assert len(events) == original_len

    def test_all_views_are_subsets_of_debug_view(self):
        from spectrum_systems.observability.event_filter import EventFilter
        events = self._make_events()
        debug = EventFilter.debug_view(events)
        for view_fn in (EventFilter.operator_view, EventFilter.monitoring_view,
                        EventFilter.failure_view, EventFilter.performance_view):
            result = view_fn(events)
            for e in result:
                assert e in debug, f"View returned event not in debug_view: {e}"


class TestRCAWithFiltering:
    def _make_trace_events(self):
        return [
            {"event_type": "execution_start",  "trace_id": "TRC-001", "data": {}},
            {"event_type": "execution_error",  "trace_id": "TRC-001", "data": {}},
            {"event_type": "eval_gate_fail",   "trace_id": "TRC-001", "data": {}},
            {"event_type": "debug_context",    "trace_id": "TRC-001", "data": {}},
            {"event_type": "execution_start",  "trace_id": "TRC-002", "data": {}},
            {"event_type": "execution_end",    "trace_id": "TRC-002", "data": {}},
        ]

    def test_events_for_trace_scopes_correctly(self):
        from spectrum_systems.observability.event_filter import RCAWithFiltering
        events = self._make_trace_events()
        result = RCAWithFiltering.events_for_trace("TRC-001", events)
        for e in result["full_view"]:
            assert e["trace_id"] == "TRC-001"

    def test_events_for_trace_different_trace_excluded(self):
        from spectrum_systems.observability.event_filter import RCAWithFiltering
        events = self._make_trace_events()
        result = RCAWithFiltering.events_for_trace("TRC-001", events)
        trc2 = [e for e in result["full_view"] if e["trace_id"] == "TRC-002"]
        assert len(trc2) == 0

    def test_default_view_is_subset_of_full_view(self):
        from spectrum_systems.observability.event_filter import RCAWithFiltering
        events = self._make_trace_events()
        result = RCAWithFiltering.events_for_trace("TRC-001", events)
        for e in result["default_view"]:
            assert e in result["full_view"]

    def test_counts_match_lists(self):
        from spectrum_systems.observability.event_filter import RCAWithFiltering
        events = self._make_trace_events()
        result = RCAWithFiltering.events_for_trace("TRC-001", events)
        assert result["default_count"] == len(result["default_view"])
        assert result["total_count"] == len(result["full_view"])

    def test_rca_for_failure_surfaces_failure_events(self):
        from spectrum_systems.observability.event_filter import RCAWithFiltering
        events = self._make_trace_events()
        failure = {"artifact_id": "FAIL-001", "trace_id": "TRC-001"}
        result = RCAWithFiltering.rca_for_failure(failure, events)
        assert result["trace_id"] == "TRC-001"
        failure_types = {e["event_type"] for e in result["failure_events"]}
        assert "execution_error" in failure_types or "eval_gate_fail" in failure_types

    def test_rca_for_failure_has_all_required_keys(self):
        from spectrum_systems.observability.event_filter import RCAWithFiltering
        events = self._make_trace_events()
        failure = {"artifact_id": "FAIL-001", "trace_id": "TRC-001"}
        result = RCAWithFiltering.rca_for_failure(failure, events)
        for key in ("failure_id", "trace_id", "failure_events",
                    "recommended_view", "full_view_available", "summary"):
            assert key in result


# ---------------------------------------------------------------------------
# Phase 7: Operator Training — artifact existence checks
# ---------------------------------------------------------------------------


class TestOperatorTrainingArtifacts:
    BASE = os.path.dirname(os.path.dirname(__file__))

    def _path(self, *parts):
        return os.path.join(self.BASE, *parts)

    def test_simplified_architecture_runbook_exists(self):
        path = self._path("docs", "operations", "3ls_simplified_architecture_runbook.md")
        assert os.path.exists(path), f"Missing: {path}"

    def test_training_guide_exists(self):
        path = self._path("docs", "training", "3ls_training_guide.md")
        assert os.path.exists(path), f"Missing: {path}"

    def test_runbook_covers_canonical_systems(self):
        path = self._path("docs", "operations", "3ls_simplified_architecture_runbook.md")
        content = open(path).read()
        # Consolidated 3LS systems + canonical unchanged owners (GOV, AEX)
        for system in ("EXEC", "GOVERN", "EVAL", "GOV", "AEX"):
            assert system in content, f"Runbook missing system: {system}"

    def test_runbook_covers_failure_scenarios(self):
        path = self._path("docs", "operations", "3ls_simplified_architecture_runbook.md")
        content = open(path).read()
        assert "Scenario" in content
        assert "BLOCK" in content or "block" in content

    def test_training_guide_has_all_modules(self):
        path = self._path("docs", "training", "3ls_training_guide.md")
        content = open(path).read()
        for i in range(1, 6):
            assert f"Module {i}" in content, f"Training guide missing Module {i}"

    def test_training_guide_covers_rca_cases(self):
        path = self._path("docs", "training", "3ls_training_guide.md")
        content = open(path).read()
        for case in ("EXEC_001", "EXEC_002", "GOV_001", "GOV_003", "EVAL_001", "EVAL_002"):
            assert case in content, f"Training guide missing RCA case: {case}"

    def test_training_guide_covers_event_filtering(self):
        path = self._path("docs", "training", "3ls_training_guide.md")
        content = open(path).read()
        for view in ("debug_view", "operator_view", "monitoring_view", "performance_view"):
            assert view in content, f"Training guide missing event view: {view}"

    def test_event_catalog_json_valid(self):
        path = self._path("docs", "events", "event_catalog.json")
        assert os.path.exists(path), f"Missing: {path}"
        with open(path) as f:
            catalog = json.load(f)
        assert "events" in catalog
        assert len(catalog["events"]) >= 10
        assert "views" in catalog

    def test_event_catalog_has_usefulness_metrics(self):
        path = self._path("docs", "events", "event_catalog.json")
        with open(path) as f:
            catalog = json.load(f)
        metrics = catalog.get("usefulness_metrics", {})
        assert metrics.get("baseline") == 0.65
        assert metrics.get("achieved", 0) >= 0.90

    def test_event_catalog_all_events_have_importance(self):
        path = self._path("docs", "events", "event_catalog.json")
        with open(path) as f:
            catalog = json.load(f)
        for et, meta in catalog["events"].items():
            assert "importance" in meta, f"event_catalog event {et!r} missing importance"
            assert 1 <= meta["importance"] <= 5


# ---------------------------------------------------------------------------
# Phase 8: Backward Compatibility
# ---------------------------------------------------------------------------


class TestDeprecationLayer:
    def _make_artifact(self):
        return {
            "artifact_type": "context_bundle",
            "trace_id": "TRC-DEP-001",
        }

    def test_tpa_check_emits_deprecation_warning(self):
        from spectrum_systems.compat.deprecation_layer import DeprecationLayer
        compat = DeprecationLayer()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            compat.tpa_check(self._make_artifact())
        assert any(issubclass(x.category, DeprecationWarning) for x in w)

    def test_gov_policy_emits_deprecation_warning(self):
        from spectrum_systems.compat.deprecation_layer import DeprecationLayer
        compat = DeprecationLayer()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            compat.gov_policy(self._make_artifact())
        assert any(issubclass(x.category, DeprecationWarning) for x in w)

    def test_tlc_route_emits_deprecation_warning(self):
        from spectrum_systems.compat.deprecation_layer import DeprecationLayer
        compat = DeprecationLayer()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            compat.tlc_route(self._make_artifact())
        assert any(issubclass(x.category, DeprecationWarning) for x in w)

    def test_wpg_gate_emits_deprecation_warning(self):
        from spectrum_systems.compat.deprecation_layer import DeprecationLayer
        compat = DeprecationLayer()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            compat.wpg_gate(self._make_artifact())
        assert any(issubclass(x.category, DeprecationWarning) for x in w)

    def test_tpa_check_delegates_to_exec(self):
        from spectrum_systems.compat.deprecation_layer import DeprecationLayer
        compat = DeprecationLayer()
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            allowed, reason = compat.tpa_check(self._make_artifact())
        # Should produce same result as EXECSystem.exec_check
        from spectrum_systems.exec_system.exec_system import EXECSystem
        allowed2, reason2 = EXECSystem().exec_check(self._make_artifact())
        assert allowed == allowed2

    def test_gov_policy_delegates_to_govern(self):
        from spectrum_systems.compat.deprecation_layer import DeprecationLayer
        compat = DeprecationLayer()
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            passed, _ = compat.gov_policy(self._make_artifact())
        from spectrum_systems.govern.govern import GOVERNSystem
        passed2, _ = GOVERNSystem().policy_check(self._make_artifact())
        assert passed == passed2

    def test_all_deprecated_methods_exist(self):
        from spectrum_systems.compat.deprecation_layer import DeprecationLayer
        expected = [
            "tpa_check", "tpa_lineage", "tpa_scope",
            "prg_roadmap", "prg_priority_report",
            "tlc_route", "tlc_lifecycle",
            "gov_policy", "gov_drift",
            "wpg_gate", "wkg_provenance",
            "chk_batch", "chk_umbrella",
        ]
        compat = DeprecationLayer()
        for method in expected:
            assert hasattr(compat, method), f"DeprecationLayer missing method: {method}"

    def test_chk_batch_delegates_to_eval(self):
        from spectrum_systems.compat.deprecation_layer import DeprecationLayer
        compat = DeprecationLayer()
        batch = {"batch_id": "B1", "trace_id": "TRC-001", "slice_count": 3}
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            ok, reason = compat.chk_batch(batch)
        from spectrum_systems.eval_system.eval_system import EVALSystem
        ok2, reason2 = EVALSystem().batch_constraint_check(batch)
        assert ok == ok2


class TestMigrationTimeline:
    def test_week_1_phase_is_warnings(self):
        from spectrum_systems.compat.deprecation_layer import MigrationTimeline
        assert MigrationTimeline.current_phase(1) == MigrationTimeline.WEEK_1_2

    def test_week_2_phase_is_warnings(self):
        from spectrum_systems.compat.deprecation_layer import MigrationTimeline
        assert MigrationTimeline.current_phase(2) == MigrationTimeline.WEEK_1_2

    def test_week_3_phase_is_errors(self):
        from spectrum_systems.compat.deprecation_layer import MigrationTimeline
        assert MigrationTimeline.current_phase(3) == MigrationTimeline.WEEK_3

    def test_week_4_phase_is_removed(self):
        from spectrum_systems.compat.deprecation_layer import MigrationTimeline
        assert MigrationTimeline.current_phase(4) == MigrationTimeline.WEEK_4_PLUS

    def test_migration_status_has_required_keys(self):
        from spectrum_systems.compat.deprecation_layer import MigrationTimeline
        status = MigrationTimeline.migration_status()
        for key in ("deadline", "current_phase", "old_to_new", "steps", "rollback_plan"):
            assert key in status

    def test_migration_status_covers_all_old_systems(self):
        from spectrum_systems.compat.deprecation_layer import MigrationTimeline
        status = MigrationTimeline.migration_status()
        old_to_new = status["old_to_new"]
        for old in ("tpa_check", "gov_policy", "tlc_route", "wpg_gate", "chk_batch"):
            assert old in old_to_new, f"Migration map missing entry for: {old}"

    def test_migration_steps_have_module_info(self):
        from spectrum_systems.compat.deprecation_layer import MigrationTimeline
        for method, info in MigrationTimeline.MIGRATION_STEPS.items():
            assert "old" in info
            assert "new" in info
            assert "module" in info
            assert "class" in info

    def test_migration_guide_doc_exists(self):
        base = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(base, "docs", "migration", "3ls_migration_guide.md")
        assert os.path.exists(path), f"Missing migration guide: {path}"

    def test_migration_guide_covers_all_old_systems(self):
        base = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(base, "docs", "migration", "3ls_migration_guide.md")
        content = open(path).read()
        for system in ("TPA", "PRG", "GOV", "TLC", "WPG", "CHK"):
            assert system in content, f"Migration guide missing old system: {system}"

    def test_migration_guide_covers_new_systems(self):
        base = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(base, "docs", "migration", "3ls_migration_guide.md")
        content = open(path).read()
        for system in ("EXEC", "GOVERN", "EVAL"):
            assert system in content, f"Migration guide missing new system: {system}"


# ---------------------------------------------------------------------------
# Phase 9: Final Integration Validation
# ---------------------------------------------------------------------------


class TestConsolidatedSystemsIntegration:
    """Verify all three consolidated systems work end-to-end."""

    def _artifact(self, **extra):
        base = {"artifact_type": "context_bundle", "trace_id": "TRC-FINAL-001"}
        base.update(extra)
        return base

    def test_exec_admits_valid_artifact(self):
        from spectrum_systems.exec_system.exec_system import EXECSystem
        ok, reason = EXECSystem().exec_check(self._artifact())
        assert ok
        assert "PASS" in reason

    def test_exec_blocks_missing_trace_id(self):
        from spectrum_systems.exec_system.exec_system import EXECSystem
        ok, reason = EXECSystem().exec_check({"artifact_type": "context_bundle"})
        assert not ok
        assert "trace_id" in reason

    def test_exec_blocks_trust_blocked(self):
        from spectrum_systems.exec_system.exec_system import EXECSystem
        ok, reason = EXECSystem().exec_check(self._artifact(trust_blocked=True))
        assert not ok

    def test_govern_passes_valid_artifact(self):
        from spectrum_systems.govern.govern import GOVERNSystem
        ok, reason = GOVERNSystem().policy_check(self._artifact())
        assert ok
        assert "PASS" in reason

    def test_govern_blocks_missing_artifact_type(self):
        from spectrum_systems.govern.govern import GOVERNSystem
        ok, reason = GOVERNSystem().policy_check({"trace_id": "TRC-001"})
        assert not ok

    def test_govern_blocks_unauthorized(self):
        from spectrum_systems.govern.govern import GOVERNSystem
        ok, reason = GOVERNSystem().policy_check(
            self._artifact(authorization_level="unauthorized")
        )
        assert not ok

    def test_govern_lifecycle_valid_transition(self):
        from spectrum_systems.govern.govern import GOVERNSystem
        artifact = self._artifact(
            artifact_id="ART-001",
            lifecycle_state="admitted",
        )
        ok, reason = GOVERNSystem().lifecycle_check(artifact, "executing_slice_1")
        assert ok

    def test_govern_lifecycle_blocks_invalid_transition(self):
        from spectrum_systems.govern.govern import GOVERNSystem
        artifact = self._artifact(
            artifact_id="ART-001",
            lifecycle_state="admitted",
        )
        ok, reason = GOVERNSystem().lifecycle_check(artifact, "promoted")
        assert not ok

    def test_eval_gate_allows_valid_artifact(self):
        from spectrum_systems.eval_system.eval_system import EVALSystem
        decision = EVALSystem().eval_gate(self._artifact())
        assert decision["decision"] == "allow"

    def test_eval_gate_blocks_missing_provenance(self):
        from spectrum_systems.eval_system.eval_system import EVALSystem
        artifact = {
            "artifact_type": "context_bundle",
            "execution_without_provenance": True,
        }
        decision = EVALSystem().eval_gate(artifact)
        assert decision["decision"] == "block"

    def test_eval_gate_blocks_low_pass_rate(self):
        from spectrum_systems.eval_system.eval_system import EVALSystem
        decision = EVALSystem().eval_gate(
            self._artifact(),
            eval_results={"passed": 80, "total": 100, "threshold": 0.95},
        )
        assert decision["decision"] == "block"

    def test_full_pipeline_happy_path(self):
        """Full pipeline: admit → policy → lifecycle → eval → promote."""
        from spectrum_systems.exec_system.exec_system import EXECSystem
        from spectrum_systems.govern.govern import GOVERNSystem
        from spectrum_systems.eval_system.eval_system import EVALSystem

        artifact = {
            "artifact_id": "ART-FINAL",
            "artifact_type": "context_bundle",
            "trace_id": "TRC-FINAL-HAPPY",
            "lifecycle_state": "admitted",
        }

        # 1. Admission
        ok, msg = EXECSystem().exec_check(artifact)
        assert ok, f"Admission failed: {msg}"

        # 2. Policy check
        ok, msg = GOVERNSystem().policy_check(artifact)
        assert ok, f"Policy failed: {msg}"

        # 3. Lifecycle transition to execution
        ok, msg = GOVERNSystem().lifecycle_check(artifact, "executing_slice_1")
        assert ok, f"Lifecycle failed: {msg}"

        # 4. Eval gate
        artifact["lifecycle_state"] = "executing_slice_3"
        decision = EVALSystem().eval_gate(
            artifact,
            eval_results={"passed": 97, "total": 100, "threshold": 0.95},
        )
        assert decision["decision"] == "allow", f"Eval gate blocked: {decision}"


class TestSystemRegistryGuardCompliance:
    """Hardening: run the system registry guard locally against our changed docs.

    This catches SHADOW_OWNERSHIP_OVERLAP, PROTECTED_AUTHORITY_VIOLATION, and
    DIRECT_OWNERSHIP_OVERLAP violations before they reach CI.
    """

    DOCS = [
        "docs/events/event_catalog.json",
        "docs/migration/3ls_migration_guide.md",
        "docs/operations/3ls_simplified_architecture_runbook.md",
        "docs/training/3ls_training_guide.md",
        "spectrum_systems/compat/deprecation_layer.py",
        "spectrum_systems/observability/event_analysis.py",
        "spectrum_systems/observability/event_filter.py",
    ]

    def _guard_result(self):
        import sys
        from pathlib import Path
        repo_root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(repo_root))
        from spectrum_systems.modules.governance.system_registry_guard import (
            evaluate_system_registry_guard,
            load_guard_policy,
            parse_system_registry,
        )
        policy = load_guard_policy(
            repo_root / "contracts" / "governance" / "system_registry_guard_policy.json"
        )
        registry = parse_system_registry(
            repo_root / "docs" / "architecture" / "system_registry.md"
        )
        return evaluate_system_registry_guard(
            repo_root=repo_root,
            changed_files=self.DOCS,
            policy=policy,
            registry_model=registry,
        )

    def test_guard_passes_on_our_docs(self):
        """The registry guard must pass on all Phase 6-9 docs and source files."""
        result = self._guard_result()
        diagnostics = result.get("diagnostics") or []
        violations = [d for d in diagnostics if d.get("reason_code") in {
            "SHADOW_OWNERSHIP_OVERLAP",
            "PROTECTED_AUTHORITY_VIOLATION",
            "DIRECT_OWNERSHIP_OVERLAP",
        }]
        assert result["status"] == "pass", (
            f"Registry guard failed with {len(violations)} violation(s):\n"
            + "\n".join(
                f"  {v['reason_code']} file={v['file']} line={v['line']} "
                f"symbol={v['symbol']} canonical_owner={v.get('canonical_owner')}"
                for v in violations
            )
        )

    def test_guard_no_shadow_ownership(self):
        result = self._guard_result()
        violations = [
            d for d in (result.get("diagnostics") or [])
            if d.get("reason_code") == "SHADOW_OWNERSHIP_OVERLAP"
        ]
        assert not violations, (
            "SHADOW_OWNERSHIP_OVERLAP in docs:\n"
            + "\n".join(f"  {v['file']}:{v['line']} symbol={v['symbol']}" for v in violations)
        )

    def test_guard_no_protected_authority_violations(self):
        result = self._guard_result()
        violations = [
            d for d in (result.get("diagnostics") or [])
            if d.get("reason_code") == "PROTECTED_AUTHORITY_VIOLATION"
        ]
        assert not violations, (
            "PROTECTED_AUTHORITY_VIOLATION in docs:\n"
            + "\n".join(f"  {v['file']}:{v['line']} symbol={v['symbol']}" for v in violations)
        )

    def test_guard_no_direct_ownership_overlap(self):
        result = self._guard_result()
        violations = [
            d for d in (result.get("diagnostics") or [])
            if d.get("reason_code") == "DIRECT_OWNERSHIP_OVERLAP"
        ]
        assert not violations, (
            "DIRECT_OWNERSHIP_OVERLAP in docs:\n"
            + "\n".join(f"  {v['file']}:{v['line']} symbol={v['symbol']}" for v in violations)
        )


class TestMetricsVerification:
    """Verify all Phase 1-9 metrics are met."""

    def test_event_usefulness_target_met(self):
        from spectrum_systems.observability.event_analysis import EventAnalysis
        report = EventAnalysis().usefulness_report()
        assert report["improved_usefulness"] >= 0.90, (
            f"Event usefulness {report['improved_usefulness']:.1%} < 90% target"
        )

    def test_event_filter_has_four_views(self):
        from spectrum_systems.observability.event_filter import EventFilter
        events = [{"event_type": "execution_end", "trace_id": "T1"}]
        assert EventFilter.debug_view(events) is not None
        assert EventFilter.operator_view(events) is not None
        assert EventFilter.monitoring_view(events) is not None
        assert EventFilter.performance_view(events) is not None

    def test_consolidated_systems_exist(self):
        """Verify the 3 consolidated system modules can be imported."""
        from spectrum_systems.exec_system.exec_system import EXECSystem
        from spectrum_systems.govern.govern import GOVERNSystem
        from spectrum_systems.eval_system.eval_system import EVALSystem
        assert EXECSystem
        assert GOVERNSystem
        assert EVALSystem

    def test_deprecation_layer_provides_zero_breaking_changes(self):
        """All deprecated methods work without raising (only emit warnings)."""
        from spectrum_systems.compat.deprecation_layer import DeprecationLayer
        artifact = {"artifact_type": "context_bundle", "trace_id": "TRC-COMPAT"}
        compat = DeprecationLayer()
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            # These should not raise — only warn
            compat.tpa_check(artifact)
            compat.gov_policy(artifact)
            compat.tlc_route(artifact)

    def test_migration_timeline_has_three_week_path(self):
        from spectrum_systems.compat.deprecation_layer import MigrationTimeline
        phases = {MigrationTimeline.current_phase(w) for w in range(1, 5)}
        assert MigrationTimeline.WEEK_1_2 in phases
        assert MigrationTimeline.WEEK_3 in phases
        assert MigrationTimeline.WEEK_4_PLUS in phases

    def test_all_phase_docs_exist(self):
        base = os.path.dirname(os.path.dirname(__file__))
        docs = [
            ("docs", "events", "event_catalog.json"),
            ("docs", "operations", "3ls_simplified_architecture_runbook.md"),
            ("docs", "training", "3ls_training_guide.md"),
            ("docs", "migration", "3ls_migration_guide.md"),
        ]
        for parts in docs:
            path = os.path.join(base, *parts)
            assert os.path.exists(path), f"Required doc missing: {path}"

    def test_zero_regressions_exec_system(self):
        """EXECSystem blocks and passes match spec — no regressions."""
        from spectrum_systems.exec_system.exec_system import EXECSystem
        sys = EXECSystem()
        # Must block on missing fields
        ok, _ = sys.exec_check({})
        assert not ok
        # Must pass on valid artifact
        ok, _ = sys.exec_check({"artifact_type": "x", "trace_id": "T"})
        assert ok

    def test_zero_regressions_govern_system(self):
        """GOVERNSystem blocks and passes match spec — no regressions."""
        from spectrum_systems.govern.govern import GOVERNSystem
        gov = GOVERNSystem()
        ok, _ = gov.policy_check({})
        assert not ok
        ok, _ = gov.policy_check({"artifact_type": "context_bundle", "trace_id": "T"})
        assert ok

    def test_zero_regressions_eval_system(self):
        """EVALSystem blocks and passes match spec — no regressions."""
        from spectrum_systems.eval_system.eval_system import EVALSystem
        ev = EVALSystem()
        ok, _ = ev.validate_provenance({"artifact_id": "A", "trace_id": "T"})
        assert ok
        ok, _ = ev.validate_provenance({"artifact_id": "A"})
        assert not ok
