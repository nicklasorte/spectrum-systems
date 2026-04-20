"""
DriftDetector: Measures decision entropy, exception rate trends, eval pass rate trends.
Emits drift_signal_record immutably. Fails closed: any calculation error triggers error_artifact.
"""

import uuid
from datetime import datetime
from typing import List, Dict, Any
from dataclasses import dataclass, asdict


@dataclass
class DriftSignalRecord:
    """Immutable drift signal."""
    signal_id: str
    signal_type: str  # decision_divergence, exception_rate, eval_pass_drop, trace_gap
    metric_name: str
    baseline_value: float
    current_value: float
    threshold_warn: float
    threshold_critical: float
    severity: str  # warning, critical
    timestamp: str
    affected_artifacts: List[str]
    remediation_steps: List[str]
    source_code_version: str


class DriftDetector:
    """
    Detects drift across:
    - decision_divergence: same context_class → different outcomes
    - exception_rate: rising exceptions week-over-week
    - eval_pass_rate: eval pass rate dropping
    - trace_coverage: trace gaps increasing
    """

    def __init__(self, artifact_store, eval_runner, baseline_metrics: Dict[str, Any]):
        """
        Args:
            artifact_store: ArtifactStore for persisting signals
            eval_runner: EvalRunner for measuring eval pass rates
            baseline_metrics: Dict with thresholds (from drift-thresholds-manifest.json)
        """
        self.artifact_store = artifact_store
        self.eval_runner = eval_runner
        self.baseline_metrics = baseline_metrics
        self.code_version = self._get_code_version()

    def detect_drift(self) -> List[DriftSignalRecord]:
        """
        Main entry point: measure all drift vectors, emit signals for those exceeding thresholds.

        Fails closed: any exception triggers error_artifact and re-raises.

        Returns: List of DriftSignalRecord (may be empty if no drift detected)
        """
        signals = []

        try:
            # Vector 1: Decision Divergence (higher is worse)
            divergence = self._calculate_decision_divergence()
            if divergence > self.baseline_metrics['decision_divergence']['threshold_warn']:
                signal = self._emit_signal(
                    signal_type='decision_divergence',
                    metric_name='spectrum_systems.drift.decision_divergence',
                    current_value=divergence,
                    baseline_value=self.baseline_metrics['decision_divergence']['baseline'],
                    threshold_warn=self.baseline_metrics['decision_divergence']['threshold_warn'],
                    threshold_critical=self.baseline_metrics['decision_divergence']['threshold_critical'],
                    higher_is_worse=True
                )
                signals.append(signal)

            # Vector 2: Exception Rate (higher is worse)
            exception_rate = self._calculate_exception_rate()
            if exception_rate > self.baseline_metrics['exception_rate']['threshold_warn']:
                signal = self._emit_signal(
                    signal_type='exception_rate',
                    metric_name='spectrum_systems.drift.exception_rate',
                    current_value=exception_rate,
                    baseline_value=self.baseline_metrics['exception_rate']['baseline'],
                    threshold_warn=self.baseline_metrics['exception_rate']['threshold_warn'],
                    threshold_critical=self.baseline_metrics['exception_rate']['threshold_critical'],
                    higher_is_worse=True
                )
                signals.append(signal)

            # Vector 3: Eval Pass Rate Drop (lower is worse)
            eval_pass_rate = self._calculate_eval_pass_rate()
            threshold_crit_ep = self.baseline_metrics['eval_pass_rate']['threshold_critical']
            baseline_ep = self.baseline_metrics['eval_pass_rate']['baseline']
            threshold_warn_ep = threshold_crit_ep + (baseline_ep - threshold_crit_ep) * 0.5
            if eval_pass_rate < threshold_warn_ep:
                signal = self._emit_signal(
                    signal_type='eval_pass_drop',
                    metric_name='spectrum_systems.drift.eval_pass_rate',
                    current_value=eval_pass_rate,
                    baseline_value=baseline_ep,
                    threshold_warn=threshold_warn_ep,
                    threshold_critical=threshold_crit_ep,
                    higher_is_worse=False
                )
                signals.append(signal)

            # Vector 4: Trace Coverage Gap (lower is worse)
            trace_coverage = self._calculate_trace_coverage()
            threshold_crit_tc = self.baseline_metrics['trace_coverage']['threshold_critical']
            baseline_tc = self.baseline_metrics['trace_coverage']['baseline']
            threshold_warn_tc = threshold_crit_tc + (baseline_tc - threshold_crit_tc) * 0.5
            if trace_coverage < threshold_warn_tc:
                signal = self._emit_signal(
                    signal_type='trace_gap',
                    metric_name='spectrum_systems.drift.trace_coverage',
                    current_value=trace_coverage,
                    baseline_value=baseline_tc,
                    threshold_warn=threshold_warn_tc,
                    threshold_critical=threshold_crit_tc,
                    higher_is_worse=False
                )
                signals.append(signal)

            return signals

        except Exception as e:
            self._emit_error_artifact(str(e))
            raise RuntimeError(f"DriftDetector.detect_drift() failed: {str(e)}")

    def _calculate_decision_divergence(self) -> float:
        """
        Same context_class, different outcomes = divergence.

        Algorithm:
        1. Group decisions by context_class
        2. For each context_class with N >= 5 decisions, count divergent outcomes
        3. Return: (count of divergent decisions) / (total decisions)

        SLO: < 0.10 (10% divergence acceptable)
        """
        try:
            decisions = self.artifact_store.query({'artifact_type': 'control_decision'}, limit=1000)

            if not decisions:
                return 0.0

            grouped = {}
            for decision in decisions:
                ctx_class = decision.get('context_class', 'unknown')
                if ctx_class not in grouped:
                    grouped[ctx_class] = []
                grouped[ctx_class].append(decision)

            divergent_count = 0
            total_count = 0

            for ctx_class, decisions_in_class in grouped.items():
                if len(decisions_in_class) < 5:
                    continue

                outcomes = set()
                for d in decisions_in_class:
                    outcomes.add(d.get('decision_type', 'unknown'))

                if len(outcomes) > 1:
                    divergent_count += len(decisions_in_class)

                total_count += len(decisions_in_class)

            return divergent_count / total_count if total_count > 0 else 0.0

        except Exception as e:
            raise ValueError(f"Failed to calculate decision_divergence: {str(e)}")

    def _calculate_exception_rate(self) -> float:
        """
        Exceptions per total artifacts produced.

        Algorithm:
        1. Count exception_artifacts in last 7 days
        2. Count total artifacts produced in last 7 days
        3. Return: exceptions / total

        SLO: < 2% (< 0.02)
        """
        try:
            exceptions = self.artifact_store.query(
                {'artifact_type': 'exception_artifact', 'recency_days': 7},
                limit=10000
            )

            all_artifacts = self.artifact_store.query(
                {'recency_days': 7},
                limit=10000
            )

            if not all_artifacts:
                return 0.0

            return len(exceptions) / len(all_artifacts) if len(all_artifacts) > 0 else 0.0

        except Exception as e:
            raise ValueError(f"Failed to calculate exception_rate: {str(e)}")

    def _calculate_eval_pass_rate(self) -> float:
        """
        Percentage of evals passing.

        Algorithm:
        1. Run all eval_cases against recent artifacts
        2. Count passes vs fails
        3. Return: passes / total

        SLO: > 95% (> 0.95)
        """
        try:
            eval_results = self.eval_runner.get_recent_results(days=7)

            if not eval_results:
                return 1.0

            passes = sum(1 for result in eval_results if result.get('status') == 'pass')
            total = len(eval_results)

            return passes / total if total > 0 else 1.0

        except Exception as e:
            raise ValueError(f"Failed to calculate eval_pass_rate: {str(e)}")

    def _calculate_trace_coverage(self) -> float:
        """
        Percentage of artifacts with complete trace linkage.

        Algorithm:
        1. Fetch recent artifacts
        2. Check each has trace_id, parent_artifact_ids, complete lineage
        3. Return: traced / total

        SLO: > 99.9% (> 0.999)
        """
        try:
            artifacts = self.artifact_store.query({'recency_days': 7}, limit=10000)

            if not artifacts:
                return 1.0

            traced = 0
            for artifact in artifacts:
                if artifact.get('trace_id') and artifact.get('parent_artifact_ids'):
                    traced += 1

            return traced / len(artifacts) if len(artifacts) > 0 else 0.0

        except Exception as e:
            raise ValueError(f"Failed to calculate trace_coverage: {str(e)}")

    def _emit_signal(
        self,
        signal_type: str,
        metric_name: str,
        current_value: float,
        baseline_value: float,
        threshold_warn: float,
        threshold_critical: float,
        higher_is_worse: bool = True
    ) -> DriftSignalRecord:
        """Create and store drift_signal_record immutably."""
        if higher_is_worse:
            severity = 'critical' if current_value >= threshold_critical else 'warning'
        else:
            severity = 'critical' if current_value <= threshold_critical else 'warning'

        signal = DriftSignalRecord(
            signal_id=str(uuid.uuid4()),
            signal_type=signal_type,
            metric_name=metric_name,
            baseline_value=baseline_value,
            current_value=current_value,
            threshold_warn=threshold_warn,
            threshold_critical=threshold_critical,
            severity=severity,
            timestamp=datetime.utcnow().isoformat() + 'Z',
            affected_artifacts=self._find_affected_artifacts(signal_type),
            remediation_steps=self._generate_remediation(signal_type),
            source_code_version=self.code_version
        )

        self.artifact_store.put(
            asdict(signal),
            namespace='governance/signals',
            immutable=True
        )

        return signal

    def _find_affected_artifacts(self, signal_type: str) -> List[str]:
        """Find artifact IDs affected by this drift."""
        try:
            if signal_type == 'decision_divergence':
                decisions = self.artifact_store.query({'artifact_type': 'control_decision'}, limit=100)
                return [d.get('artifact_id') for d in decisions if d.get('artifact_id')]
            elif signal_type == 'exception_rate':
                exceptions = self.artifact_store.query({'artifact_type': 'exception_artifact'}, limit=50)
                return [e.get('affected_artifact_id') for e in exceptions if e.get('affected_artifact_id')]
            elif signal_type == 'eval_pass_drop':
                failures = self.artifact_store.query({'artifact_type': 'eval_result', 'status': 'fail'}, limit=100)
                return [f.get('artifact_id') for f in failures if f.get('artifact_id')]
            elif signal_type == 'trace_gap':
                untraced = self.artifact_store.query({'trace_id': {'$exists': False}}, limit=100)
                return [u.get('artifact_id') for u in untraced if u.get('artifact_id')]
            return []
        except Exception:
            return []

    def _generate_remediation(self, signal_type: str) -> List[str]:
        """Generate remediation steps."""
        remediation_map = {
            'decision_divergence': [
                'Review recent control_decision artifacts for inconsistency',
                'Check if context_class definitions have drifted',
                'Re-calibrate decision policies'
            ],
            'exception_rate': [
                'Investigate exception_artifact root causes',
                'Review exception_conversion_rules for adequacy',
                'Consider policy updates'
            ],
            'eval_pass_drop': [
                'Audit eval_case failures',
                'Check model version or prompt changes',
                'Consider rolling back recent updates'
            ],
            'trace_gap': [
                'Verify trace_context propagation in all code paths',
                'Check artifact store for incomplete lineage records',
                'Audit tracing instrumentation'
            ]
        }
        return remediation_map.get(signal_type, ['Contact governance team'])

    def _emit_error_artifact(self, error_msg: str) -> None:
        """Emit error_artifact on calculation failure (fail-closed)."""
        error_artifact = {
            'artifact_type': 'error_artifact',
            'source': 'DriftDetector',
            'error_message': error_msg,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        self.artifact_store.put(error_artifact, namespace='governance/errors')

    def _get_code_version(self) -> str:
        """Get current git commit hash."""
        try:
            import subprocess
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except Exception:
            return 'unknown'
