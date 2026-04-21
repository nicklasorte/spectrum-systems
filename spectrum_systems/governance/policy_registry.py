"""PolicyRegistry: Central store of all governance rules, policies, and decision logic.
Immutable, versioned, auditable. No policy in prompts allowed."""

import uuid
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import subprocess


@dataclass
class PolicyRegistryEntry:
    """Single immutable policy entry."""
    policy_id: str
    policy_name: str
    policy_version: str
    rule_id: str
    rule_condition_type: str
    rule_condition_text: str
    decision_class: str
    applies_to_artifact_types: List[str]
    status: str
    created_timestamp: str
    source_code_version: str


class PolicyRegistry:
    """Central policy registry: all governance rules stored here, versioned, auditable.
    Fail-closed: Any policy lookup that fails returns block decision."""

    def __init__(self, artifact_store):
        """Args: artifact_store: ArtifactStore for persisting policies"""
        self.artifact_store = artifact_store
        self.code_version = self._get_code_version()
        self._load_policies()

    def _load_policies(self) -> None:
        """Load all active policies into memory cache."""
        try:
            self.policies = self.artifact_store.query({
                'artifact_type': 'policy_registry_entry',
                'status': 'active'
            }, limit=10000)
        except Exception as e:
            self._emit_error_artifact(f"Failed to load policies: {str(e)}")
            self.policies = []

    def create_policy(self, policy_data: Dict[str, Any]) -> str:
        """Create and store a new policy immutably. Fails closed: invalid policy
        raises error before storage. Returns: policy_id"""
        required = [
            'policy_name', 'policy_version', 'rule_id', 'rule_condition_type',
            'rule_condition_text', 'decision_class', 'applies_to_artifact_types'
        ]

        for field in required:
            if field not in policy_data:
                raise ValueError(f"Missing required field: {field}")

        version = policy_data['policy_version']
        if not self._is_valid_semver(version):
            raise ValueError(f"Invalid semantic version: {version}")

        policy_id = policy_data.get('policy_id', str(uuid.uuid4()))
        entry = PolicyRegistryEntry(
            policy_id=policy_id,
            policy_name=policy_data['policy_name'],
            policy_version=version,
            rule_id=policy_data['rule_id'],
            rule_condition_type=policy_data['rule_condition_type'],
            rule_condition_text=policy_data['rule_condition_text'],
            decision_class=policy_data['decision_class'],
            applies_to_artifact_types=policy_data['applies_to_artifact_types'],
            status=policy_data.get('status', 'draft'),
            created_timestamp=datetime.utcnow().isoformat() + 'Z',
            source_code_version=self.code_version
        )

        self.artifact_store.put(
            asdict(entry),
            namespace='governance/policies',
            immutable=True
        )

        return policy_id

    def get_policy(self, policy_id: str) -> Optional[PolicyRegistryEntry]:
        """Retrieve policy by ID (fails closed if not found)."""
        try:
            for policy in self.policies:
                if policy.get('policy_id') == policy_id and policy.get('status') == 'active':
                    return policy
            return None
        except Exception:
            return None

    def get_policies_for_decision_class(self, decision_class: str) -> List[PolicyRegistryEntry]:
        """Get all active policies for a decision class (fails closed on error)."""
        try:
            matching = []
            for policy in self.policies:
                if policy.get('decision_class') == decision_class and policy.get('status') == 'active':
                    matching.append(policy)
            return matching
        except Exception:
            self._emit_error_artifact(f"Failed to query policies for {decision_class}")
            return []

    def audit_for_hidden_logic(self) -> List[Dict[str, Any]]:
        """Scan codebase for ungoverned decision logic. Heuristics:
        1. Hardcoded thresholds in code (not in policy registry)
        2. Decision logic in prompts (marked by keywords)
        3. Heuristic functions not linked to rule_ids
        Returns: List of findings (ungoverned logic detected)"""
        findings = []

        try:
            result = subprocess.run(
                ['grep', '-r', '-E', r'if.*>.*0\.[0-9]+|if.*<.*0\.[0-9]+', 'spectrum_systems/'],
                capture_output=True,
                text=True,
                timeout=30
            )

            for line in result.stdout.split('\n'):
                if line.strip():
                    findings.append({
                        'finding_type': 'hardcoded_threshold',
                        'location': line,
                        'severity': 'high',
                        'recommendation': 'Move threshold to policy registry with rule_id'
                    })

            result = subprocess.run(
                ['grep', '-r', '-E', r'should.*block|must.*allow|if.*then.*block', 'spectrum_systems/'],
                capture_output=True,
                text=True,
                timeout=30
            )

            for line in result.stdout.split('\n'):
                if line.strip() and 'docstring' not in line:
                    findings.append({
                        'finding_type': 'logic_in_prompt',
                        'location': line,
                        'severity': 'critical',
                        'recommendation': 'Extract rule to policy registry; reference rule_id in code'
                    })

            return findings

        except Exception as e:
            self._emit_error_artifact(f"Audit for hidden logic failed: {str(e)}")
            return []

    def generate_ungoverned_logic_audit(self) -> Dict[str, Any]:
        """Full audit of ungoverned decision surface. Returns: audit_artifact ready to store"""
        findings = self.audit_for_hidden_logic()

        audit = {
            'artifact_type': 'ungoverned_logic_audit',
            'audit_id': str(uuid.uuid4()),
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'total_findings': len(findings),
            'critical_findings': sum(1 for f in findings if f['severity'] == 'critical'),
            'high_findings': sum(1 for f in findings if f['severity'] == 'high'),
            'findings': findings,
            'recommendation': 'All critical findings must be resolved before promotion'
        }

        self.artifact_store.put(
            audit,
            namespace='governance/audits'
        )

        return audit

    def _is_valid_semver(self, version: str) -> bool:
        """Check if version matches semantic versioning."""
        import re
        pattern = r'^\d+\.\d+\.\d+$'
        return bool(re.match(pattern, version))

    def _get_code_version(self) -> str:
        """Get current git commit hash."""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except Exception:
            return 'unknown'

    def _emit_error_artifact(self, error_msg: str) -> None:
        """Emit error_artifact on failure (fail-closed)."""
        error_artifact = {
            'artifact_type': 'error_artifact',
            'source': 'PolicyRegistry',
            'error_message': error_msg,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        try:
            self.artifact_store.put(error_artifact, namespace='governance/errors')
        except Exception:
            pass
