"""IncidentToEvalConverter: Auto-generate evals from postmortems."""

import uuid
from datetime import datetime
from typing import List, Dict, Any
from dataclasses import dataclass, asdict
import subprocess


@dataclass
class EvalExpansionProposal:
    """Proposed eval cases from incident."""
    eval_case_id: str
    eval_case_name: str
    eval_case_description: str
    source_incident_id: str
    is_critical: bool
    status: str


class IncidentToEvalConverter:
    """Convert incidents into eval cases automatically."""

    def __init__(self, artifact_store):
        self.artifact_store = artifact_store
        self.code_version = self._get_code_version()

    def process_postmortem(self, postmortem: Dict[str, Any]) -> List[EvalExpansionProposal]:
        """Process postmortem → generate eval case proposals."""
        try:
            proposals = []
            incident_id = postmortem.get('incident_id', 'unknown')
            incident_type = postmortem.get('incident_type', 'unknown')
            failure_pattern = postmortem.get('failure_pattern', '')

            if incident_type == 'eval_miss':
                proposals.extend(self._generate_slice_evals(failure_pattern, incident_id))
            elif incident_type == 'decision_error':
                proposals.extend(self._generate_policy_evals(failure_pattern, incident_id))
            elif incident_type == 'trace_gap':
                proposals.extend(self._generate_tracing_evals(failure_pattern, incident_id))
            elif incident_type == 'calibration_failure':
                proposals.extend(self._generate_calibration_evals(failure_pattern, incident_id))
            elif incident_type == 'silent_regression':
                proposals.extend(self._generate_regression_evals(failure_pattern, incident_id))

            for proposal in proposals:
                self.artifact_store.put(asdict(proposal), namespace='governance/eval_proposals', immutable=True)

            log_entry = {
                'artifact_type': 'eval_expansion_log',
                'log_id': str(uuid.uuid4()),
                'incident_id': incident_id,
                'incident_type': incident_type,
                'proposals_generated': len(proposals),
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }

            self.artifact_store.put(log_entry, namespace='governance/logs')
            return proposals

        except Exception as e:
            self._emit_error_artifact(f"Postmortem processing failed: {str(e)}")
            raise RuntimeError(f"Failed to process postmortem: {str(e)}")

    def _generate_slice_evals(self, failure_pattern: str, incident_id: str) -> List[EvalExpansionProposal]:
        proposals = []
        if 'long context' in failure_pattern.lower():
            proposals.append(EvalExpansionProposal(
                eval_case_id=str(uuid.uuid4()),
                eval_case_name='eval_long_context_5000plus',
                eval_case_description='Test artifacts with context length > 5000 tokens',
                source_incident_id=incident_id,
                is_critical=True,
                status='proposed'
            ))
        return proposals

    def _generate_policy_evals(self, failure_pattern: str, incident_id: str) -> List[EvalExpansionProposal]:
        proposals = []
        if 'policy' in failure_pattern.lower():
            proposals.append(EvalExpansionProposal(
                eval_case_id=str(uuid.uuid4()),
                eval_case_name='eval_policy_boundary_conditions',
                eval_case_description='Test policy at edge boundaries',
                source_incident_id=incident_id,
                is_critical=True,
                status='proposed'
            ))
        return proposals

    def _generate_tracing_evals(self, failure_pattern: str, incident_id: str) -> List[EvalExpansionProposal]:
        return [EvalExpansionProposal(
            eval_case_id=str(uuid.uuid4()),
            eval_case_name='eval_trace_context_propagation',
            eval_case_description='Verify trace context propagated through all steps',
            source_incident_id=incident_id,
            is_critical=True,
            status='proposed'
        )]

    def _generate_calibration_evals(self, failure_pattern: str, incident_id: str) -> List[EvalExpansionProposal]:
        return [EvalExpansionProposal(
            eval_case_id=str(uuid.uuid4()),
            eval_case_name='eval_judge_overconfidence_detection',
            eval_case_description='Verify judge overconfidence is detected and flagged',
            source_incident_id=incident_id,
            is_critical=True,
            status='proposed'
        )]

    def _generate_regression_evals(self, failure_pattern: str, incident_id: str) -> List[EvalExpansionProposal]:
        return [EvalExpansionProposal(
            eval_case_id=str(uuid.uuid4()),
            eval_case_name='eval_regression_detection_on_update',
            eval_case_description='Detect regressions automatically on model/policy update',
            source_incident_id=incident_id,
            is_critical=True,
            status='proposed'
        )]

    def _get_code_version(self) -> str:
        try:
            result = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except Exception:
            return 'unknown'

    def _emit_error_artifact(self, error_msg: str) -> None:
        error_artifact = {'artifact_type': 'error_artifact', 'source': 'IncidentToEvalConverter', 'error_message': error_msg, 'timestamp': datetime.utcnow().isoformat() + 'Z'}
        try:
            self.artifact_store.put(error_artifact, namespace='governance/errors')
        except Exception:
            pass
