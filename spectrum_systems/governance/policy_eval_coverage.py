"""PolicyEvalCoverageChecker: Verify all policies have eval coverage."""

import uuid
from datetime import datetime
from typing import Dict, Any, List
import subprocess


class PolicyEvalCoverageChecker:
    def __init__(self, artifact_store):
        self.artifact_store = artifact_store
        self.code_version = self._get_code_version()

    def generate_coverage_report(self) -> Dict[str, Any]:
        try:
            policies = self.artifact_store.query({'artifact_type': 'policy_registry_entry', 'status': 'active'}, limit=10000)

            if not policies:
                return {
                    'total_policies': 0,
                    'policies_with_evals': 0,
                    'policies_without_evals': [],
                    'coverage_percent': 100,
                    'recommendation': 'No active policies.'
                }

            policies_without_evals = []
            policies_with_evals_count = 0

            for policy in policies:
                policy_id = policy.get('policy_id')

                evals = self.artifact_store.query({'artifact_type': 'eval_case', 'policy_id': policy_id}, limit=1)

                if evals and len(evals) > 0:
                    policies_with_evals_count += 1
                else:
                    policies_without_evals.append(policy_id)

            coverage = (policies_with_evals_count / len(policies) * 100) if policies else 0

            report = {
                'artifact_type': 'policy_eval_coverage_report',
                'report_id': str(uuid.uuid4()),
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'total_policies': len(policies),
                'policies_with_evals': policies_with_evals_count,
                'policies_without_evals': policies_without_evals,
                'coverage_percent': coverage,
                'recommendation': self._generate_recommendation(coverage, policies_without_evals)
            }

            self.artifact_store.put(report, namespace='governance/reports')
            return report

        except Exception as e:
            self._emit_error_artifact(f"Coverage report generation failed: {str(e)}")
            raise RuntimeError(f"Failed to generate coverage report: {str(e)}")

    def _generate_recommendation(self, coverage: float, unmeasured: List[str]) -> str:
        if coverage == 100:
            return 'All policies have eval backing. Proceed to production.'
        elif coverage >= 95:
            return f'{len(unmeasured)} policies lack eval coverage. High risk. Require review.'
        else:
            return 'CRITICAL: Major policies lack eval backing. Block promotion.'

    def _get_code_version(self) -> str:
        try:
            result = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except Exception:
            return 'unknown'

    def _emit_error_artifact(self, error_msg: str) -> None:
        error_artifact = {'artifact_type': 'error_artifact', 'source': 'PolicyEvalCoverageChecker', 'error_message': error_msg, 'timestamp': datetime.utcnow().isoformat() + 'Z'}
        try:
            self.artifact_store.put(error_artifact, namespace='governance/errors')
        except Exception:
            pass
