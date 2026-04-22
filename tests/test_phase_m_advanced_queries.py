"""Tests for Phase M: Advanced Query Surfaces."""

import pytest
from spectrum_systems.queries.advanced_surfaces import AdvancedQuerySurfaces


class TestAdvancedQueries:
    """Test ops-driven advanced query surfaces."""

    def test_correction_patterns_query(self):
        """M1: Query which fixes work best."""
        store = {
            'corrections': [
                {'incident_type': 'auth', 'fix_type': 'reset_session', 'success': True},
                {'incident_type': 'auth', 'fix_type': 'reset_session', 'success': True},
                {'incident_type': 'auth', 'fix_type': 'revoke_token', 'success': False},
            ]
        }
        queries = AdvancedQuerySurfaces(store)

        results = queries.query_correction_patterns()
        assert len(results) >= 1
        reset_result = next(r for r in results if r['fix_type'] == 'reset_session')
        assert reset_result['success_rate'] == 1.0

    def test_model_tournament_query(self):
        """M2: Query model comparison."""
        store = {
            'models': [
                {'model_id': 'claude_v1', 'accuracy': 0.95, 'latency_ms': 100},
                {'model_id': 'claude_v2', 'accuracy': 0.97, 'latency_ms': 150}
            ]
        }
        queries = AdvancedQuerySurfaces(store)

        results = queries.query_model_tournament_results()
        assert 'models' in results
        assert 'claude_v1' in results['models']
        assert 'claude_v2' in results['models']

    def test_context_incident_correlation_query(self):
        """M3: Query context properties that predict failures."""
        store = {
            'incidents': [
                {'context': {'user_risk': 'high', 'network_quality': 'low'}},
                {'context': {'user_risk': 'high', 'network_quality': 'low'}},
                {'context': {'user_risk': 'low', 'network_quality': 'high'}}
            ]
        }
        queries = AdvancedQuerySurfaces(store)

        results = queries.query_context_incident_correlation()
        assert len(results) > 0
        high_risk_result = next(
            (r for r in results if 'user_risk=high' in r['context_property']),
            None
        )
        assert high_risk_result is not None

    def test_capability_readiness_query(self):
        """M4: Query model readiness for use cases."""
        store = {
            'capabilities': [
                {'model_id': 'claude_v1', 'use_case': 'web_auth', 'ready': True},
                {'model_id': 'claude_v1', 'use_case': 'fraud', 'ready': False},
                {'model_id': 'claude_v2', 'use_case': 'web_auth', 'ready': True}
            ]
        }
        queries = AdvancedQuerySurfaces(store)

        results = queries.query_capability_readiness()
        assert 'capability_readiness' in results
        assert 'claude_v1' in results['capability_readiness']

    def test_policy_regression_analysis_query(self):
        """M5: Query policy regression."""
        store = {
            'policy_comparisons': [
                {'policy_id': 'pol_1', 'old_policy_incidents': 100, 'new_policy_incidents': 80},
                {'policy_id': 'pol_2', 'old_policy_incidents': 50, 'new_policy_incidents': 60}
            ]
        }
        queries = AdvancedQuerySurfaces(store)

        results = queries.query_policy_regression_analysis()
        pol_1 = next(r for r in results if r['policy_id'] == 'pol_1')
        assert pol_1['improvement_percent'] == pytest.approx(20.0)
        assert pol_1['regression'] is False

        pol_2 = next(r for r in results if r['policy_id'] == 'pol_2')
        assert pol_2['improvement_percent'] == pytest.approx(-20.0)
        assert pol_2['regression'] is True

    def test_eval_importance_query(self):
        """M6: Query which evals are most predictive."""
        store = {
            'evals': [
                {'eval_id': 'eval_1', 'incident_type': 'auth', 'predictive_power': 0.8},
                {'eval_id': 'eval_2', 'incident_type': 'network', 'predictive_power': 0.2}
            ]
        }
        queries = AdvancedQuerySurfaces(store)

        results = queries.query_eval_importance()
        assert results[0]['eval_id'] == 'eval_1'
        assert results[0]['predictive_power'] == 0.8

    def test_quality_by_context_class_query(self):
        """M7: Query quality by context type."""
        store = {
            'decisions': [
                {'context_class': 'enterprise', 'quality_score': 0.99},
                {'context_class': 'enterprise', 'quality_score': 0.98},
                {'context_class': 'startup', 'quality_score': 0.90},
                {'context_class': 'startup', 'quality_score': 0.92}
            ]
        }
        queries = AdvancedQuerySurfaces(store)

        results = queries.query_quality_by_context_class()
        startup = next(r for r in results if r['context_class'] == 'startup')
        enterprise = next(r for r in results if r['context_class'] == 'enterprise')
        assert startup['avg_quality'] < enterprise['avg_quality']

    def test_judge_bias_detection_query(self):
        """M8: Query judge bias patterns."""
        store = {
            'reviews': [
                {'judge_id': 'judge_1', 'decision': 'approve', 'subject_demographic': 'women'},
                {'judge_id': 'judge_1', 'decision': 'approve', 'subject_demographic': 'women'},
                {'judge_id': 'judge_1', 'decision': 'reject', 'subject_demographic': 'men'},
                {'judge_id': 'judge_1', 'decision': 'reject', 'subject_demographic': 'men'}
            ]
        }
        queries = AdvancedQuerySurfaces(store)

        results = queries.query_judge_bias_detection()
        assert len(results) > 0
        if results:
            judge = results[0]
            assert 'approval_rates' in judge
            assert 'bias_score' in judge
