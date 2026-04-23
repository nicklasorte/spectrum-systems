"""Advanced query surfaces based on operational needs (Phase M)."""

from typing import List, Dict, Any, Optional


class AdvancedQuerySurfaces:
    """Queries ops teams actually need."""

    def __init__(self, artifact_store: Optional[Any] = None):
        self.store = artifact_store or {}

    def query_correction_patterns(self) -> List[Dict[str, Any]]:
        """M1: Which fixes work best for incident types?"""
        corrections = self.store.get('corrections', [])

        patterns = {}
        for correction in corrections:
            incident_type = correction.get('incident_type')
            fix_type = correction.get('fix_type')
            success = correction.get('success', False)

            key = (incident_type, fix_type)
            if key not in patterns:
                patterns[key] = {'successes': 0, 'total': 0}

            patterns[key]['total'] += 1
            if success:
                patterns[key]['successes'] += 1

        results = []
        for (incident_type, fix_type), stats in patterns.items():
            success_rate = stats['successes'] / stats['total'] if stats['total'] > 0 else 0
            results.append({
                'incident_type': incident_type,
                'fix_type': fix_type,
                'success_rate': success_rate,
                'samples': stats['total']
            })

        return sorted(results, key=lambda x: x['success_rate'], reverse=True)

    def query_model_tournament_results(self) -> Dict[str, Any]:
        """M2: Compare models on test set."""
        models = self.store.get('models', [])

        tournament = {}
        for model in models:
            tournament[model.get('model_id')] = {
                'accuracy': model.get('accuracy', 0),
                'latency_ms': model.get('latency_ms', 0),
                'cost_per_request': model.get('cost_per_request', 0),
                'test_set_size': model.get('test_set_size', 0)
            }

        return {'models': tournament}

    def query_context_incident_correlation(self) -> List[Dict[str, Any]]:
        """M3: Which context properties predict failures?"""
        incidents = self.store.get('incidents', [])

        context_stats = {}
        for incident in incidents:
            context = incident.get('context', {})
            for key, value in context.items():
                ctx_key = f'{key}={value}'
                if ctx_key not in context_stats:
                    context_stats[ctx_key] = {'incidents': 0, 'total': 0}
                context_stats[ctx_key]['incidents'] += 1
                context_stats[ctx_key]['total'] += 1

        results = []
        for context_key, stats in context_stats.items():
            incident_rate = stats['incidents'] / stats['total'] if stats['total'] > 0 else 0
            results.append({
                'context_property': context_key,
                'incident_rate': incident_rate,
                'observations': stats['total']
            })

        return sorted(results, key=lambda x: x['incident_rate'], reverse=True)

    def query_capability_readiness(self) -> Dict[str, Any]:
        """M4: Which models ready for which use cases?"""
        capabilities = self.store.get('capabilities', [])

        readiness = {}
        for cap in capabilities:
            model = cap.get('model_id')
            use_case = cap.get('use_case')
            ready = cap.get('ready', False)

            if model not in readiness:
                readiness[model] = {}

            readiness[model][use_case] = {
                'ready': ready,
                'confidence': cap.get('confidence', 0)
            }

        return {'capability_readiness': readiness}

    def query_policy_regression_analysis(self) -> List[Dict[str, Any]]:
        """M5: Compare old vs new policy outcomes."""
        comparisons = self.store.get('policy_comparisons', [])

        results = []
        for comparison in comparisons:
            old_incidents = comparison.get('old_policy_incidents', 0)
            new_incidents = comparison.get('new_policy_incidents', 0)
            improvement = (old_incidents - new_incidents) / max(old_incidents, 1) * 100

            results.append({
                'policy_id': comparison.get('policy_id'),
                'old_incidents': old_incidents,
                'new_incidents': new_incidents,
                'improvement_percent': improvement,
                'regression': improvement < 0
            })

        return sorted(results, key=lambda x: x['improvement_percent'], reverse=True)

    def query_eval_importance(self) -> List[Dict[str, Any]]:
        """M6: Which evals best predict real incidents?"""
        evals = self.store.get('evals', [])

        importance = []
        for eval_case in evals:
            predictive_power = eval_case.get('predictive_power', 0)
            importance.append({
                'eval_id': eval_case.get('eval_id'),
                'incident_type': eval_case.get('incident_type'),
                'predictive_power': predictive_power,
                'usage_count': eval_case.get('usage_count', 0)
            })

        return sorted(importance, key=lambda x: x['predictive_power'], reverse=True)

    def query_quality_by_context_class(self) -> List[Dict[str, Any]]:
        """M7: Which context types have worst quality?"""
        decisions = self.store.get('decisions', [])

        by_context = {}
        for decision in decisions:
            context_class = decision.get('context_class', 'unknown')
            quality = decision.get('quality_score', 0)

            if context_class not in by_context:
                by_context[context_class] = []
            by_context[context_class].append(quality)

        results = []
        for context_class, scores in by_context.items():
            avg_quality = sum(scores) / len(scores) if scores else 0
            results.append({
                'context_class': context_class,
                'avg_quality': avg_quality,
                'decisions': len(scores)
            })

        return sorted(results, key=lambda x: x['avg_quality'])

    def query_judge_bias_detection(self) -> List[Dict[str, Any]]:
        """M8: Detect reviewer bias patterns."""
        reviews = self.store.get('reviews', [])

        by_judge = {}
        for review in reviews:
            judge = review.get('judge_id')
            decision = review.get('decision')
            demographic = review.get('subject_demographic')

            if judge not in by_judge:
                by_judge[judge] = {}
            if demographic not in by_judge[judge]:
                by_judge[judge][demographic] = {'approvals': 0, 'total': 0}

            by_judge[judge][demographic]['total'] += 1
            if decision == 'approve':
                by_judge[judge][demographic]['approvals'] += 1

        results = []
        for judge, demographics in by_judge.items():
            approval_rates = {}
            for demographic, stats in demographics.items():
                rate = stats['approvals'] / stats['total'] if stats['total'] > 0 else 0
                approval_rates[demographic] = rate

            if len(approval_rates) > 1:
                rates = list(approval_rates.values())
                bias_score = max(rates) - min(rates)
                results.append({
                    'judge_id': judge,
                    'approval_rates': approval_rates,
                    'bias_score': bias_score,
                    'biased': bias_score > 0.15
                })

        return sorted(results, key=lambda x: x['bias_score'], reverse=True)
