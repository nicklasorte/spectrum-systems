"""OverrideHotspotManager: Track override hotspots, enforce expiry."""

import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any
import subprocess


class OverrideHotspotManager:
    def __init__(self, artifact_store):
        self.artifact_store = artifact_store
        self.code_version = self._get_code_version()

    def generate_hotspot_report(self, days: int = 30) -> Dict[str, Any]:
        try:
            overrides = self.artifact_store.query({'artifact_type': 'exception_artifact', 'recency_days': days}, limit=10000)

            if not overrides:
                return {
                    'total_overrides': 0,
                    'hotspots': [],
                    'high_risk_gates': [],
                    'recommendation': 'No overrides in period. Good.'
                }

            hotspots_by_gate = {}
            for override in overrides:
                gate = override.get('affected_resource', 'unknown')

                if gate not in hotspots_by_gate:
                    hotspots_by_gate[gate] = {'count': 0}

                hotspots_by_gate[gate]['count'] += 1

            hotspots = [
                {
                    'gate_name': gate,
                    'override_count': data['count'],
                    'severity': 'high' if data['count'] >= 5 else 'medium'
                }
                for gate, data in hotspots_by_gate.items()
            ]

            hotspots.sort(key=lambda x: x['override_count'], reverse=True)
            high_risk = [h['gate_name'] for h in hotspots if h['override_count'] >= 5]

            report = {
                'artifact_type': 'override_hotspot_report',
                'report_id': str(uuid.uuid4()),
                'report_timestamp': datetime.utcnow().isoformat() + 'Z',
                'period_days': days,
                'total_overrides': len(overrides),
                'hotspots': hotspots,
                'high_risk_gates': high_risk,
                'recommendation': self._generate_recommendation(len(overrides), high_risk)
            }

            self.artifact_store.put(report, namespace='governance/reports')
            return report

        except Exception as e:
            self._emit_error_artifact(f"Hotspot report generation failed: {str(e)}")
            raise RuntimeError(f"Failed to generate hotspot report: {str(e)}")

    def enforce_override_expiry(self) -> List[str]:
        try:
            now = datetime.utcnow()
            expired_ids = []

            overrides = self.artifact_store.query({'artifact_type': 'exception_artifact', 'conversion_status': 'pending'}, limit=10000)

            for override in overrides:
                expiry_str = override.get('expiry_date')
                try:
                    expiry = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))
                    if expiry <= now:
                        self._update_exception_status(override['exception_id'], 'expired')
                        expired_ids.append(override['exception_id'])
                except Exception:
                    pass

            return expired_ids

        except Exception as e:
            self._emit_error_artifact(f"Override expiry enforcement failed: {str(e)}")
            raise RuntimeError(f"Failed to enforce override expiry: {str(e)}")

    def _generate_recommendation(self, total: int, high_risk: List[str]) -> str:
        if len(high_risk) > 0:
            return f'CRITICAL: {len(high_risk)} gates have >= 5 overrides. Convert to policy.'
        elif total > 10:
            return f'WARNING: {total} overrides in period. Monitor closely.'
        else:
            return 'Override usage within normal range.'

    def _update_exception_status(self, exception_id: str, new_status: str) -> None:
        try:
            self.artifact_store.update_field(artifact_id=exception_id, field='conversion_status', value=new_status, namespace='governance/exceptions')
        except Exception:
            pass

    def _get_code_version(self) -> str:
        try:
            result = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except Exception:
            return 'unknown'

    def _emit_error_artifact(self, error_msg: str) -> None:
        error_artifact = {'artifact_type': 'error_artifact', 'source': 'OverrideHotspotManager', 'error_message': error_msg, 'timestamp': datetime.utcnow().isoformat() + 'Z'}
        try:
            self.artifact_store.put(error_artifact, namespace='governance/errors')
        except Exception:
            pass
