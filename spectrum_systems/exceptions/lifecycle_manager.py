"""
ExceptionLifecycleManager: Tracks exceptions, enforces expiry, generates policy candidates.
"""

import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List


@dataclass
class ExceptionArtifact:
    """Immutable exception record."""
    exception_id: str
    exception_reason: str
    issued_by: str
    issued_date: str
    expiry_date: str
    affected_resource: str
    severity: str  # low, medium, high
    policy_candidate_generated: bool
    conversion_status: str  # pending, converted, expired, stale
    created_timestamp: str


class ExceptionLifecycleManager:
    """
    Tracks exceptions:
    1. Store exception_artifact immutably
    2. Daily: check expiry, mark expired, generate policy_candidate if needed
    3. Weekly: surface exception hotspots for governance team review
    """

    def __init__(self, artifact_store):
        """
        Args:
            artifact_store: ArtifactStore for persisting exceptions and policies
        """
        self.artifact_store = artifact_store

    def track_exception(self, exception_data: Dict[str, Any]) -> str:
        """
        Store a new exception_artifact immutably.

        Args:
            exception_data: Dict with exception_reason, issued_by, expiry_date,
                            affected_resource, severity

        Returns: exception_id

        Fails closed: if expiry_date is missing or in past, raises ValueError
        """
        expiry_str = exception_data.get('expiry_date')
        if not expiry_str:
            raise ValueError("exception_data must include expiry_date (no indefinite exceptions)")

        try:
            expiry_dt = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))
        except ValueError as e:
            raise ValueError(f"Invalid expiry_date format: {str(e)}")

        if expiry_dt.tzinfo is None:
            expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)

        if expiry_dt <= datetime.now(timezone.utc):
            raise ValueError(f"expiry_date must be in future, got {expiry_str}")

        exception_id = str(uuid.uuid4())
        exception = ExceptionArtifact(
            exception_id=exception_id,
            exception_reason=exception_data.get('exception_reason', 'unspecified'),
            issued_by=exception_data.get('issued_by', 'unknown'),
            issued_date=exception_data.get('issued_date', datetime.utcnow().isoformat() + 'Z'),
            expiry_date=expiry_str,
            affected_resource=exception_data.get('affected_resource', 'unknown'),
            severity=exception_data.get('severity', 'medium'),
            policy_candidate_generated=False,
            conversion_status='pending',
            created_timestamp=datetime.utcnow().isoformat() + 'Z'
        )

        self.artifact_store.put(
            asdict(exception),
            namespace='governance/exceptions',
            immutable=True
        )

        return exception_id

    def check_expiry(self) -> List[Dict[str, Any]]:
        """
        Daily job: find expired exceptions, emit policy_candidate_artifact.

        Algorithm:
        1. Fetch all exceptions with conversion_status = 'pending'
        2. For each: if expiry_date <= today, mark as 'expired'
        3. If 5+ exceptions of same resource in 30 days, generate policy_candidate
        4. Store policy_candidate with link back to exceptions

        Returns: List of generated policy_candidate artifacts
        """
        try:
            pending = self.artifact_store.query({
                'artifact_type': 'exception_artifact',
                'conversion_status': 'pending'
            }, limit=10000)

            policy_candidates = []
            now = datetime.now(timezone.utc)

            active_by_resource: Dict[str, List[Dict]] = {}
            for exc in pending:
                expiry_str = exc.get('expiry_date', '')
                try:
                    expiry_dt = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))
                    if expiry_dt.tzinfo is None:
                        expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
                except (ValueError, AttributeError):
                    self._update_exception_status(exc.get('exception_id', ''), 'expired')
                    continue

                if expiry_dt <= now:
                    self._update_exception_status(exc['exception_id'], 'expired')
                else:
                    resource = exc.get('affected_resource', 'unknown')
                    if resource not in active_by_resource:
                        active_by_resource[resource] = []
                    active_by_resource[resource].append(exc)

            cutoff = now - timedelta(days=30)
            for resource, exceptions in active_by_resource.items():
                recent = []
                for e in exceptions:
                    issued_str = e.get('issued_date', '')
                    try:
                        issued_dt = datetime.fromisoformat(issued_str.replace('Z', '+00:00'))
                        if issued_dt.tzinfo is None:
                            issued_dt = issued_dt.replace(tzinfo=timezone.utc)
                        if issued_dt >= cutoff:
                            recent.append(e)
                    except (ValueError, AttributeError):
                        continue

                if len(recent) >= 5:
                    policy_candidate = self._generate_policy_candidate(resource, recent)
                    policy_candidates.append(policy_candidate)
                    for exc in recent:
                        self._update_exception_status(exc['exception_id'], 'converted')

            return policy_candidates

        except Exception as e:
            self._emit_error_artifact(f"Exception check_expiry failed: {str(e)}")
            raise RuntimeError(f"Exception lifecycle check_expiry failed: {str(e)}")

    def _generate_policy_candidate(self, resource: str, exceptions: List[Dict]) -> Dict[str, Any]:
        """
        Convert exception pattern into policy proposal.

        Algorithm:
        1. Analyze exception reasons (frequency of each reason)
        2. Extract pattern: "gate X granted exception Y times for reason Z"
        3. Recommend: "change gate X logic to accommodate Z automatically"
        """
        reason_counts: Dict[str, int] = {}
        for exc in exceptions:
            reason = exc.get('exception_reason', 'unspecified')
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

        top_reason = max(reason_counts, key=reason_counts.get)

        policy_candidate = {
            'artifact_type': 'policy_candidate_artifact',
            'policy_id': str(uuid.uuid4()),
            'generated_from_resource': resource,
            'pattern': f"Gate {resource} granted exception {len(exceptions)} times",
            'top_reason': top_reason,
            'reason_frequencies': reason_counts,
            'linked_exception_ids': [e['exception_id'] for e in exceptions],
            'created_timestamp': datetime.utcnow().isoformat() + 'Z',
            'recommendation': (
                f"Review and potentially update {resource} gate logic to handle: {top_reason}"
            )
        }

        self.artifact_store.put(
            policy_candidate,
            namespace='governance/policies/candidates'
        )

        return policy_candidate

    def _update_exception_status(self, exception_id: str, new_status: str) -> None:
        """Update exception conversion_status for lifecycle tracking."""
        try:
            self.artifact_store.update_field(
                artifact_id=exception_id,
                field='conversion_status',
                value=new_status,
                namespace='governance/exceptions'
            )
        except Exception as e:
            raise RuntimeError(f"Failed to update exception status: {str(e)}")

    def get_exception_hotspots(self, days: int = 30) -> Dict[str, int]:
        """
        Fetch exception hotspots: which gates had the most exceptions?

        Returns: {gate_name: exception_count}
        """
        exceptions = self.artifact_store.query({
            'artifact_type': 'exception_artifact',
            'recency_days': days
        }, limit=10000)

        hotspots: Dict[str, int] = {}
        for exc in exceptions:
            resource = exc.get('affected_resource', 'unknown')
            hotspots[resource] = hotspots.get(resource, 0) + 1

        return dict(sorted(hotspots.items(), key=lambda x: x[1], reverse=True))

    def _emit_error_artifact(self, error_msg: str) -> None:
        """Emit error_artifact on failure (fail-closed)."""
        error_artifact = {
            'artifact_type': 'error_artifact',
            'source': 'ExceptionLifecycleManager',
            'error_message': error_msg,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        self.artifact_store.put(error_artifact, namespace='governance/errors')
