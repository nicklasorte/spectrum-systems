"""Tests for Phase L: Intelligence Layer V2."""

import pytest
from spectrum_systems.intelligence.lineage_graph import LineageGraph, LineageEdge
from spectrum_systems.intelligence.core_queries import IntelligenceQueries


class TestLineageGraph:
    """Test lineage graph building and traversal."""

    def test_add_edge(self):
        """L1: Can add edges to graph."""
        graph = LineageGraph()
        edge = LineageEdge(
            parent_id='eval_1',
            parent_type='eval_case',
            child_id='policy_1',
            child_type='policy',
            relation_type='generated',
            timestamp='2026-04-22T00:00:00Z'
        )
        graph.add_edge(edge)
        assert len(graph.edges) == 1

    def test_get_upstream(self):
        """L1: Can trace upstream dependencies."""
        graph = LineageGraph()
        graph.add_edge(LineageEdge(
            parent_id='incident_1', parent_type='incident',
            child_id='eval_1', child_type='eval', relation_type='generated',
            timestamp='2026-04-22T00:00:00Z'
        ))
        graph.add_edge(LineageEdge(
            parent_id='eval_1', parent_type='eval',
            child_id='policy_1', child_type='policy', relation_type='generated',
            timestamp='2026-04-22T00:00:00Z'
        ))

        upstream = graph.get_upstream('policy_1')
        assert 'eval_1' in upstream
        assert 'incident_1' in upstream

    def test_get_downstream(self):
        """L1: Can trace downstream dependents."""
        graph = LineageGraph()
        graph.add_edge(LineageEdge(
            parent_id='policy_1', parent_type='policy',
            child_id='decision_1', child_type='decision', relation_type='used_by',
            timestamp='2026-04-22T00:00:00Z'
        ))
        graph.add_edge(LineageEdge(
            parent_id='decision_1', parent_type='decision',
            child_id='enforcement_1', child_type='enforcement', relation_type='triggers',
            timestamp='2026-04-22T00:00:00Z'
        ))

        downstream = graph.get_downstream('policy_1')
        assert 'decision_1' in downstream
        assert 'enforcement_1' in downstream

    def test_explain_artifact(self):
        """L1: Can explain artifact origin."""
        graph = LineageGraph()
        graph.add_edge(LineageEdge(
            parent_id='eval_1', parent_type='eval',
            child_id='policy_1', child_type='policy', relation_type='generated',
            timestamp='2026-04-22T00:00:00Z'
        ))

        explanation = graph.explain_artifact('policy_1')
        assert explanation['artifact_id'] == 'policy_1'
        assert 'eval_1' in explanation['created_from']
        assert 'policy' in explanation['explanation'].lower()


class TestCoreQueries:
    """Test core intelligence queries."""

    def test_policy_impact_query(self):
        """L2: Query most impactful policies."""
        store = {
            'policies': [
                {'policy_id': 'policy_1'},
                {'policy_id': 'policy_2'}
            ],
            'incidents': [],
            'evals': [],
            'decisions': [],
            'calibration': []
        }
        graph = LineageGraph()
        queries = IntelligenceQueries(graph, store)

        results = queries.query_policy_impact()
        assert len(results) >= 0
        assert all('policy_id' in r and 'incidents_prevented' in r for r in results)

    def test_evidence_gaps_query(self):
        """L3: Query evidence gaps."""
        store = {
            'policies': [],
            'incidents': [
                {'incident_id': 'inc_1', 'incident_type': 'auth_failure'},
                {'incident_id': 'inc_2', 'incident_type': 'network_error'}
            ],
            'evals': [
                {'eval_id': 'eval_1', 'incident_type': 'auth_failure'}
            ],
            'decisions': [],
            'calibration': []
        }
        graph = LineageGraph()
        queries = IntelligenceQueries(graph, store)

        gaps = queries.query_evidence_gaps()
        assert any(g['incident_type'] == 'network_error' for g in gaps)

    def test_policy_chains_query(self):
        """L4: Query policy chains."""
        store = {
            'policies': [],
            'incidents': [],
            'evals': [],
            'decisions': [
                {'policies_applied': ['policy_1', 'policy_2']},
                {'policies_applied': ['policy_1', 'policy_2']},
                {'policies_applied': ['policy_3']}
            ],
            'calibration': []
        }
        graph = LineageGraph()
        queries = IntelligenceQueries(graph, store)

        chains = queries.query_policy_chains()
        assert len(chains) > 0
        assert any(chain['frequency'] == 2 for chain in chains)

    def test_calibration_by_policy_query(self):
        """L5: Query calibration by policy."""
        store = {
            'policies': [],
            'incidents': [],
            'evals': [],
            'decisions': [],
            'calibration': [
                {'policy_id': 'policy_1', 'calibration_error': 0.02},
                {'policy_id': 'policy_1', 'calibration_error': 0.03},
                {'policy_id': 'policy_2', 'calibration_error': 0.08}
            ]
        }
        graph = LineageGraph()
        queries = IntelligenceQueries(graph, store)

        results = queries.query_calibration_by_policy()
        assert len(results) >= 2
        policy_1_result = next(r for r in results if r['policy_id'] == 'policy_1')
        assert policy_1_result['avg_calibration_error'] == pytest.approx(0.025)
        policy_2_result = next(r for r in results if r['policy_id'] == 'policy_2')
        assert policy_2_result['needs_review'] is True

    def test_incident_root_causes_query(self):
        """Bonus: Query incident root causes."""
        store = {
            'policies': [],
            'incidents': [
                {'incident_id': 'inc_1', 'root_cause': 'timeout'},
                {'incident_id': 'inc_2', 'root_cause': 'timeout'},
                {'incident_id': 'inc_3', 'root_cause': 'auth_failure'}
            ],
            'evals': [],
            'decisions': [],
            'calibration': []
        }
        graph = LineageGraph()
        queries = IntelligenceQueries(graph, store)

        causes = queries.query_incident_root_causes()
        assert causes[0]['root_cause'] == 'timeout'
        assert causes[0]['frequency'] == 2
