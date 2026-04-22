"""Five core intelligence queries that show value immediately."""

from typing import List, Dict, Any, Optional
from .lineage_graph import LineageGraph


class IntelligenceQueries:
    """Query suite for intelligence layer."""

    def __init__(self, lineage: LineageGraph, artifact_store: Optional[Any] = None):
        self.lineage = lineage
        self.store = artifact_store or {}

    def query_policy_impact(self) -> List[Dict[str, Any]]:
        """L2: Which policies prevent the most incidents?"""
        policies = self.store.get('policies', [])

        impacts = []
        for policy in policies:
            blocks = len(self.lineage.get_downstream(policy.get('policy_id', '')))
            impacts.append({
                'policy_id': policy.get('policy_id'),
                'incidents_prevented': blocks,
                'impact_score': blocks / max(len(policies), 1)
            })

        return sorted(impacts, key=lambda x: x['incidents_prevented'], reverse=True)

    def query_evidence_gaps(self) -> List[Dict[str, Any]]:
        """L3: Which incident types have no evals?"""
        incidents = self.store.get('incidents', [])
        evals = self.store.get('evals', [])

        eval_types = set(e.get('incident_type') for e in evals)
        gaps = []

        for incident in incidents:
            if incident.get('incident_type') not in eval_types:
                gaps.append({
                    'incident_type': incident.get('incident_type'),
                    'incident_id': incident.get('incident_id'),
                    'gap_severity': 'high'
                })

        return gaps

    def query_policy_chains(self) -> List[Dict[str, Any]]:
        """L4: Which policies commonly fire together (chains)?"""
        decisions = self.store.get('decisions', [])

        chains = {}
        for decision in decisions:
            policies = decision.get('policies_applied', [])
            key = tuple(sorted(policies))

            if key not in chains:
                chains[key] = 0
            chains[key] += 1

        return [
            {'chain': list(k), 'frequency': v}
            for k, v in sorted(chains.items(), key=lambda x: x[1], reverse=True)
        ]

    def query_calibration_by_policy(self) -> List[Dict[str, Any]]:
        """L5: Which policies have calibration issues?"""
        records = self.store.get('calibration', [])

        by_policy = {}
        for record in records:
            policy = record.get('policy_id', 'unknown')
            error = abs(record.get('calibration_error', 0))

            if policy not in by_policy:
                by_policy[policy] = []
            by_policy[policy].append(error)

        results = []
        for policy, errors in by_policy.items():
            avg_error = sum(errors) / len(errors) if errors else 0
            results.append({
                'policy_id': policy,
                'avg_calibration_error': avg_error,
                'needs_review': avg_error > 0.05
            })

        return sorted(results, key=lambda x: x['avg_calibration_error'], reverse=True)

    def query_incident_root_causes(self) -> List[Dict[str, Any]]:
        """Bonus: Which root causes appear most frequently?"""
        incidents = self.store.get('incidents', [])

        causes = {}
        for incident in incidents:
            root_cause = incident.get('root_cause', 'unknown')
            if root_cause not in causes:
                causes[root_cause] = 0
            causes[root_cause] += 1

        return [
            {'root_cause': cause, 'frequency': count}
            for cause, count in sorted(causes.items(), key=lambda x: x[1], reverse=True)
        ]
