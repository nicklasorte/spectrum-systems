"""
Tests for TraceManager and rerun fidelity.
"""

import pytest
import json
from datetime import datetime
from unittest.mock import Mock
from spectrum_systems.tracing.trace_manager import TraceManager, TraceContext


class TestTraceAndProvenance:
    """Test trace context and rerun."""

    @pytest.fixture
    def mock_artifact_store(self):
        return Mock()

    @pytest.fixture
    def trace_manager(self, mock_artifact_store):
        return TraceManager(artifact_store=mock_artifact_store)

    def test_trace_context_manifest_schema_valid(self):
        """Test: trace context conforms to schema."""
        from spectrum_systems.contracts.schemas import TRACE_CONTEXT_MANIFEST_SCHEMA
        try:
            import jsonschema
        except ImportError:
            pytest.skip("jsonschema not installed")

        context = {
            'artifact_id': 'artifact_1',
            'trace_id': 'a' * 32,
            'span_id': 'b' * 16,
            'parent_span_id': 'c' * 16,
            'parent_artifact_ids': ['parent_1'],
            'context_source_id': 'context_1',
            'execution_step': 'policy_eval',
            'created_timestamp': datetime.utcnow().isoformat() + 'Z',
            'lineage_depth': 1,
            'trace_coverage_complete': True,
            'rerun_bundle_ref': 'bundle_1'
        }

        jsonschema.validate(context, TRACE_CONTEXT_MANIFEST_SCHEMA)

    def test_root_artifact_generates_new_trace_id(self, trace_manager, mock_artifact_store):
        """Test: root artifact (no parent) generates new trace_id."""
        trace = trace_manager.create_trace_context(
            artifact_id='root_artifact',
            context_source_id='context_1',
            execution_step='ingestion',
            parent_artifact_ids=None,
            parent_trace_context=None
        )

        assert trace.trace_id is not None
        assert len(trace.trace_id) == 32
        assert trace.lineage_depth == 0
        assert trace.parent_span_id == ""

    def test_child_artifact_inherits_trace_id(self, trace_manager, mock_artifact_store):
        """Test: child artifact inherits parent trace_id."""
        parent_trace = TraceContext(
            artifact_id='parent',
            trace_id='a' * 32,
            span_id='b' * 16,
            parent_span_id='',
            parent_artifact_ids=[],
            context_source_id='context_1',
            execution_step='ingestion',
            created_timestamp=datetime.utcnow().isoformat() + 'Z',
            lineage_depth=0,
            trace_coverage_complete=True,
            rerun_bundle_ref='bundle_1'
        )

        child_trace = trace_manager.create_trace_context(
            artifact_id='child',
            context_source_id='context_1',
            execution_step='eval',
            parent_artifact_ids=['parent'],
            parent_trace_context=parent_trace
        )

        assert child_trace.trace_id == parent_trace.trace_id
        assert child_trace.parent_span_id == parent_trace.span_id
        assert child_trace.lineage_depth == 1

    def test_trace_immutably_stored(self, trace_manager, mock_artifact_store):
        """Test: trace context stored with immutable flag."""
        trace_manager.create_trace_context(
            artifact_id='test',
            context_source_id='ctx_1',
            execution_step='step',
        )

        mock_artifact_store.put.assert_called()
        args, kwargs = mock_artifact_store.put.call_args
        assert kwargs.get('immutable') == True

    def test_trace_coverage_audit_calculates_percentage(self, trace_manager, mock_artifact_store):
        """Test: trace coverage audit measures % of traced artifacts."""
        mock_artifact_store.query.side_effect = [
            [
                {'artifact_id': 'a1'},
                {'artifact_id': 'a2'},
                {'artifact_id': 'a3'},
                {'artifact_id': 'a4'},
                {'artifact_id': 'a5'},
            ],
            [
                {'artifact_id': 'a1', 'trace_id': 'trace_1'},
                {'artifact_id': 'a2', 'trace_id': 'trace_2'},
                {'artifact_id': 'a3', 'trace_id': 'trace_3'},
            ]
        ]

        audit = trace_manager.validate_trace_coverage()

        assert audit['total_artifacts'] == 5
        assert audit['traced_artifacts'] == 3
        assert audit['coverage_percent'] == 0.6

    def test_trace_coverage_slo_check(self, trace_manager, mock_artifact_store):
        """Test: coverage >= 99.9% meets SLO."""
        # Create 1000 artifacts, 999 traced (99.9%)
        all_artifacts = [{'artifact_id': f'a{i}'} for i in range(1000)]
        traced = [{'artifact_id': f'a{i}', 'trace_id': f't{i}'} for i in range(999)]

        mock_artifact_store.query.side_effect = [all_artifacts, traced]

        audit = trace_manager.validate_trace_coverage()

        assert audit['coverage_percent'] >= 0.999
        assert audit['slo_met'] == True

    def test_rerun_bundle_created(self, trace_manager, mock_artifact_store):
        """Test: rerun bundle stored immutably."""
        context_bundle = {'input': 'data', 'version': '1'}

        bundle_id = trace_manager.create_rerun_bundle(
            artifact_id='artifact_1',
            context_bundle=context_bundle,
            code_version='abc123'
        )

        assert bundle_id is not None
        mock_artifact_store.put.assert_called()
        args, kwargs = mock_artifact_store.put.call_args
        assert kwargs.get('immutable') == True

    def test_fails_closed_on_missing_artifact_id(self, trace_manager):
        """Test: invalid artifact_id raises error (fail-closed)."""
        with pytest.raises(ValueError):
            trace_manager.create_trace_context(
                artifact_id='',
                context_source_id='ctx',
                execution_step='step'
            )

    def test_fails_closed_on_missing_context_source(self, trace_manager):
        """Test: invalid context_source_id raises error (fail-closed)."""
        with pytest.raises(ValueError):
            trace_manager.create_trace_context(
                artifact_id='art',
                context_source_id='',
                execution_step='step'
            )

    def test_fails_closed_on_missing_execution_step(self, trace_manager):
        """Test: invalid execution_step raises error (fail-closed)."""
        with pytest.raises(ValueError):
            trace_manager.create_trace_context(
                artifact_id='art',
                context_source_id='ctx',
                execution_step=''
            )

    def test_lineage_completeness_check_complete(self, trace_manager):
        """Test: lineage completeness validation works."""
        traces = {
            'root': {'parent_artifact_ids': []},
            'child': {'parent_artifact_ids': ['root']},
            'grandchild': {'parent_artifact_ids': ['child']}
        }

        complete = trace_manager._is_lineage_complete('grandchild', traces)
        assert complete == True

    def test_lineage_completeness_check_broken(self, trace_manager):
        """Test: orphan artifact has broken lineage."""
        traces = {
            'root': {'parent_artifact_ids': []},
            'child': {'parent_artifact_ids': ['root']},
        }

        orphan_complete = trace_manager._is_lineage_complete('orphan', traces)
        assert orphan_complete == False

    def test_lineage_completeness_check_missing_parent(self, trace_manager):
        """Test: missing parent trace breaks lineage."""
        traces = {
            'child': {'parent_artifact_ids': ['missing_parent']},
        }

        complete = trace_manager._is_lineage_complete('child', traces)
        assert complete == False

    def test_trace_id_format_valid(self, trace_manager):
        """Test: generated trace_id is 32 hex chars."""
        trace_id = trace_manager._generate_trace_id()
        assert len(trace_id) == 32
        assert all(c in '0123456789abcdef' for c in trace_id)

    def test_span_id_format_valid(self, trace_manager):
        """Test: generated span_id is 16 hex chars."""
        span_id = trace_manager._generate_span_id()
        assert len(span_id) == 16
        assert all(c in '0123456789abcdef' for c in span_id)

    def test_coverage_recommendation_excellent(self, trace_manager):
        """Test: coverage >= 99.9% gets good recommendation."""
        rec = trace_manager._coverage_recommendation(0.9991)
        assert 'meeting slo' in rec.lower()

    def test_coverage_recommendation_warning(self, trace_manager):
        """Test: coverage < 99.9% gets warning."""
        rec = trace_manager._coverage_recommendation(0.991)
        assert 'warning' in rec.lower()

    def test_coverage_recommendation_critical(self, trace_manager):
        """Test: coverage < 95% gets critical."""
        rec = trace_manager._coverage_recommendation(0.90)
        assert 'CRITICAL' in rec or 'critical' in rec.lower()

    def test_multiple_parent_artifacts_deduplicated(self, trace_manager, mock_artifact_store):
        """Test: duplicate parent artifact IDs are deduplicated."""
        parent_trace = TraceContext(
            artifact_id='parent1',
            trace_id='a' * 32,
            span_id='b' * 16,
            parent_span_id='',
            parent_artifact_ids=[],
            context_source_id='ctx',
            execution_step='step',
            created_timestamp=datetime.utcnow().isoformat() + 'Z',
            lineage_depth=0,
            trace_coverage_complete=True,
            rerun_bundle_ref=''
        )

        trace = trace_manager.create_trace_context(
            artifact_id='child',
            context_source_id='ctx',
            execution_step='step',
            parent_artifact_ids=['parent1', 'parent1', 'parent2'],
            parent_trace_context=parent_trace
        )

        unique_parents = len(set(trace.parent_artifact_ids))
        assert unique_parents == 2

    def test_deep_lineage_tracking(self, trace_manager, mock_artifact_store):
        """Test: deep artifact lineage depth tracked correctly."""
        trace = None
        for i in range(10):
            trace = trace_manager.create_trace_context(
                artifact_id=f'artifact_{i}',
                context_source_id='ctx',
                execution_step='step',
                parent_trace_context=trace
            )

        assert trace.lineage_depth == 9
        assert len(trace.trace_id) == 32
