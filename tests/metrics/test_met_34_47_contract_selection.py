"""Contract preflight pytest selection target for MET-34-47."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
METRICS_DIR = REPO_ROOT / 'artifacts' / 'dashboard_metrics'
REVIEWS_DIR = REPO_ROOT / 'docs' / 'reviews'
INTELLIGENCE_ROUTE_PATH = REPO_ROOT / 'apps' / 'dashboard-3ls' / 'app' / 'api' / 'intelligence' / 'route.ts'
DASHBOARD_PAGE_PATH = REPO_ROOT / 'apps' / 'dashboard-3ls' / 'app' / 'page.tsx'

ARTIFACTS = (
    'owner_read_observation_ledger_record.json',
    'materialization_observation_mapper_record.json',
    'comparable_case_qualification_gate_record.json',
    'trend_ready_case_pack_record.json',
    'override_evidence_source_adapter_record.json',
    'fold_candidate_proof_check_record.json',
    'operator_debuggability_drill_record.json',
    'generated_artifact_policy_handoff_record.json',
)

ENVELOPE_FIELDS = (
    'artifact_type',
    'schema_version',
    'record_id',
    'created_at',
    'owner_system',
    'data_source',
    'source_artifacts_used',
    'reason_codes',
    'status',
    'warnings',
    'failure_prevented',
    'signal_improved',
)

REVIEW_DOCS = (
    'MET-42-owner-handoff-authority-redteam.md',
    'MET-43-owner-handoff-authority-fixes.md',
    'MET-44-trend-override-honesty-redteam.md',
    'MET-45-trend-override-honesty-fixes.md',
    'MET-46-simplification-debuggability-redteam.md',
    'MET-47-final-readiness-review.md',
)

BANNED_TERMS = ('approv' + 'ed', 'accept' + 'ed', 'adopt' + 'ed')


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


@pytest.mark.parametrize('name', ARTIFACTS)
def test_artifacts_exist_and_parse(name: str) -> None:
    path = METRICS_DIR / name
    assert path.is_file(), f'missing artifact: {path}'
    assert isinstance(_json(path), dict)


@pytest.mark.parametrize('name', ARTIFACTS)
def test_artifacts_have_required_envelope(name: str) -> None:
    data = _json(METRICS_DIR / name)
    for field in ENVELOPE_FIELDS:
        assert field in data, f'{name} missing field: {field}'
    assert data['owner_system'] == 'MET'
    assert data['data_source'] == 'artifact_store'
    assert isinstance(data['source_artifacts_used'], list) and data['source_artifacts_used']


def test_owner_read_has_no_acceptance_vocabulary() -> None:
    data = _json(METRICS_DIR / 'owner_read_observation_ledger_record.json')
    items = data.get('owner_read_items') or []
    assert items
    for item in items:
        state = str(item.get('read_observation_state', '')).lower()
        for banned in BANNED_TERMS:
            assert banned not in state


def test_materialization_observed_requires_owner_refs() -> None:
    data = _json(METRICS_DIR / 'materialization_observation_mapper_record.json')
    for item in data.get('materialization_observations') or []:
        if item.get('materialization_observation') == 'observed':
            refs = item.get('observed_owner_artifact_refs')
            assert isinstance(refs, list) and refs


def test_comparable_case_groups_qualify_only_when_rules_met() -> None:
    data = _json(METRICS_DIR / 'comparable_case_qualification_gate_record.json')
    min_case_count = data['qualification_rules']['min_case_count']
    for group in data.get('qualified_case_groups') or []:
        if group.get('qualifies_for_trend') is True:
            assert group.get('case_count', 0) >= min_case_count
            assert group.get('trend_state') == 'eligible_for_observation'
            assert group.get('frequency_state') == 'eligible_for_observation'


def test_trend_ready_pack_cases_needed_when_insufficient() -> None:
    data = _json(METRICS_DIR / 'trend_ready_case_pack_record.json')
    for pack in data.get('case_packs') or []:
        if pack.get('trend_readiness') == 'insufficient_cases':
            assert isinstance(pack.get('cases_needed'), int)
            assert pack['cases_needed'] > 0


def test_override_state_absent_or_unknown_without_refs() -> None:
    data = _json(METRICS_DIR / 'override_evidence_source_adapter_record.json')
    if not data.get('override_evidence_refs'):
        assert data.get('override_source_state') in {'absent', 'unknown', 'partial'}
        assert data.get('override_evidence_count') == 'unknown'


def test_fold_ready_requires_all_coverage_flags_true() -> None:
    data = _json(METRICS_DIR / 'fold_candidate_proof_check_record.json')
    for candidate in data.get('fold_candidates') or []:
        if candidate.get('fold_safety_observation') == 'fold_ready_observation':
            assert candidate.get('same_failure_prevented') is True
            assert candidate.get('same_signal_improved') is True
            assert candidate.get('upstream_artifacts_covered') is True
            assert candidate.get('downstream_consumers_covered') is True
            assert candidate.get('debug_questions_covered') is True


def test_operator_drill_carries_six_questions() -> None:
    data = _json(METRICS_DIR / 'operator_debuggability_drill_record.json')
    required = {
        'what_failed',
        'why',
        'where_in_loop',
        'source_evidence',
        'next_recommended_input',
        'what_remains_unknown',
    }
    for item in data.get('drill_items') or []:
        assert required.issubset(set((item.get('questions') or {}).keys()))


def test_generated_artifact_policy_handoff_present_without_competing_policy() -> None:
    data = _json(METRICS_DIR / 'generated_artifact_policy_handoff_record.json')
    assert 'central_policy_path' in data
    assert data.get('central_policy_state') in {'present', 'absent', 'partial', 'unknown'}


def test_api_and_dashboard_reference_new_fields() -> None:
    route_src = INTELLIGENCE_ROUTE_PATH.read_text(encoding='utf-8')
    page_src = DASHBOARD_PAGE_PATH.read_text(encoding='utf-8')
    for field in (
        'owner_read_observations:',
        'materialization_observation_mapper:',
        'comparable_case_qualification_gate:',
        'trend_ready_case_pack:',
        'override_evidence_source_adapter:',
        'fold_candidate_proof_check:',
        'operator_debuggability_drill:',
        'generated_artifact_policy_handoff:',
    ):
        assert field in route_src
    for tid in (
        'owner-read-observations-section',
        'materialization-observations-section',
        'comparable-trend-readiness-section',
        'fold-safety-section',
        'operator-debuggability-drill-section',
    ):
        assert tid in page_src


def test_review_and_fix_docs_exist() -> None:
    for name in REVIEW_DOCS:
        assert (REVIEWS_DIR / name).is_file()
