"""ComplianceTracker: Final audit gate for production."""

import uuid
from datetime import datetime
from typing import Dict, Any
import subprocess


class ComplianceTracker:
    """Track compliance with all governance rules."""

    def __init__(self, artifact_store):
        self.artifact_store = artifact_store
        self.code_version = self._get_code_version()

    def generate_compliance_report(self) -> Dict[str, Any]:
        """Generate comprehensive compliance report."""
        try:
            policies = self.artifact_store.query({'artifact_type': 'policy_registry_entry'}, limit=10000)

            if not policies:
                return {
                    'total_policies': 0,
                    'policies_compliant': 0,
                    'compliance_percent': 100,
                    'audit_status': 'pass',
                    'recommendation': 'No policies to audit'
                }

            compliant_count = 0
            for policy in policies:
                if self._policy_compliant(policy):
                    compliant_count += 1

            compliance = (compliant_count / len(policies) * 100) if policies else 0

            if compliance == 100:
                audit_status = 'pass'
            elif compliance >= 95:
                audit_status = 'warning'
            else:
                audit_status = 'fail'

            sla_metrics = {
                'trace_coverage_slo': 0.999,
                'eval_coverage_slo': 1.0,
                'policy_coverage_slo': 1.0,
                'production_ready': audit_status == 'pass'
            }

            report = {
                'artifact_type': 'compliance_status_report',
                'report_id': str(uuid.uuid4()),
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'total_policies': len(policies),
                'policies_compliant': compliant_count,
                'compliance_percent': compliance,
                'sla_metrics': sla_metrics,
                'audit_status': audit_status,
                'recommendation': self._generate_recommendation(audit_status, compliance)
            }

            self.artifact_store.put(report, namespace='governance/reports')

            audit_log = {
                'artifact_type': 'governance_audit_log',
                'audit_id': str(uuid.uuid4()),
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'compliance_report_id': report['report_id'],
                'status': audit_status,
                'code_version': self.code_version
            }

            self.artifact_store.put(audit_log, namespace='governance/audit_logs')

            return report

        except Exception as e:
            self._emit_error_artifact(f"Compliance report generation failed: {str(e)}")
            raise RuntimeError(f"Failed to generate compliance report: {str(e)}")

    def _policy_compliant(self, policy: Dict[str, Any]) -> bool:
        """Check if policy is compliant."""
        required_fields = ['policy_id', 'version', 'status', 'eval_backing']
        return all(policy.get(field) for field in required_fields)

    def _generate_recommendation(self, audit_status: str, compliance: float) -> str:
        if audit_status == 'pass':
            return 'System COMPLIANT. Ready for production deployment.'
        elif audit_status == 'warning':
            return f'System {compliance:.1f}% compliant. Address warnings before production.'
        else:
            return 'System NON-COMPLIANT. Block production. Remediate failures.'

    def _get_code_version(self) -> str:
        try:
            result = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except Exception:
            return 'unknown'

    def _emit_error_artifact(self, error_msg: str) -> None:
        error_artifact = {'artifact_type': 'error_artifact', 'source': 'ComplianceTracker', 'error_message': error_msg, 'timestamp': datetime.utcnow().isoformat() + 'Z'}
        try:
            self.artifact_store.put(error_artifact, namespace='governance/errors')
        except Exception:
            pass
