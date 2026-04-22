"""Integration tests: Phases 29-34 end-to-end flow."""

import pytest
from unittest.mock import Mock


def test_phases_29_34_complete_flow():
    """Test: Complete flow from incident → eval → roadmap → policy coverage."""
    artifact_store = Mock()

    from spectrum_systems.learning.incident_to_eval import IncidentToEvalConverter
    converter = IncidentToEvalConverter(artifact_store)

    postmortem = {
        'postmortem_id': 'pm_1',
        'incident_id': 'inc_1',
        'incident_type': 'eval_miss',
        'root_causes': ['Coverage gap'],
        'failure_pattern': 'eval_miss on long context scenarios > 5000 tokens',
        'eval_expansion_required': True,
        'proposed_eval_cases': []
    }

    proposals = converter.process_postmortem(postmortem)
    assert len(proposals) > 0

    from spectrum_systems.governance.canonical_truth import CanonicalTruthManager
    canon_mgr = CanonicalTruthManager(artifact_store)
    canonical = canon_mgr.create_canonical_truth('canon_1', {'policy_1': 'rule_1'})
    assert canonical.hash is not None

    from spectrum_systems.security.artifact_signing import ArtifactSigner
    signer = ArtifactSigner(artifact_store, 'signer_1')
    signed = signer.sign_artifact({'artifact_id': 'decision_1', 'severity': 'critical'}, severity='critical')
    assert signed is not None

    from spectrum_systems.governance.override_hotspot_manager import OverrideHotspotManager
    hotspot_mgr = OverrideHotspotManager(artifact_store)
    artifact_store.query.return_value = [
        {'affected_resource': 'eval_gate', 'exception_id': 'exc_1'},
        {'affected_resource': 'eval_gate', 'exception_id': 'exc_2'},
    ]
    report = hotspot_mgr.generate_hotspot_report(30)
    assert report['total_overrides'] == 2

    from spectrum_systems.planning.roadmap_health_coupler import RoadmapHealthCoupler
    coupler = RoadmapHealthCoupler(artifact_store)
    artifact_store.query.return_value = [
        {'metrics': {'decision_divergence': {'current': 0.05}, 'exception_rate': {'current': 0.01}}}
    ]
    priority = coupler.generate_priority_report()
    assert priority['current_health'] == 'healthy'

    from spectrum_systems.governance.policy_eval_coverage import PolicyEvalCoverageChecker
    checker = PolicyEvalCoverageChecker(artifact_store)
    artifact_store.query.side_effect = [
        [{'policy_id': 'policy_1'}],
        [{'eval_case_id': 'eval_1'}],
    ]
    coverage = checker.generate_coverage_report()
    assert coverage['coverage_percent'] == 100
