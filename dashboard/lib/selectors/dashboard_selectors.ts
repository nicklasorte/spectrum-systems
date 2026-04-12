import type {
  ArtifactRecord,
  DashboardPublication,
  DashboardViewModel,
  ExplorerCoverageStatus,
  RecommendationRecord,
  SectionInput,
  SectionState
} from '../../types/dashboard'
import { deriveRenderState } from '../guards/render_state_guards'

function makeSection<T>(title: string, data: T | null, state: SectionState, reason: string, provenance: SectionInput<T>['provenance']): SectionInput<T> {
  return { title, data, state, reason, provenance }
}

function confidenceFromScore(score?: number): 'High' | 'Medium' | 'Low' {
  if (typeof score !== 'number') return 'Low'
  if (score >= 0.8) return 'High'
  if (score >= 0.5) return 'Medium'
  return 'Low'
}

function recommendationProvenanceRows(record: RecommendationRecord, timestamp?: string): Array<{ artifact: string; path: string; keyFields: string[]; timestamp?: string; provenanceConfidence?: 'high' | 'low' }> {
  const basis = (record.source_basis ?? []).filter((value) => typeof value === 'string' && value.trim().length > 0)
  const rows = [{
    artifact: 'next_action_recommendation_record.json',
    path: '/next_action_recommendation_record.json',
    keyFields: ['records', 'recommended_next_action', 'confidence', 'source_basis', 'provenance_categories'],
    timestamp,
    provenanceConfidence: 'high' as const
  }]

  if (basis.length === 0) return rows

  return [
    ...rows,
    ...basis.map((pathValue) => ({
      artifact: pathValue.split('/').pop() ?? pathValue,
      path: pathValue.startsWith('/') ? pathValue : `/${pathValue}`,
      keyFields: ['unknown'],
      timestamp,
      provenanceConfidence: 'low' as const
    }))
  ]
}

function classifyExplorerStatus(artifact: ArtifactRecord, declaredArtifacts: Set<string>): ExplorerCoverageStatus {
  const isDeclared = declaredArtifacts.has(artifact.name)
  if (isDeclared && artifact.exists && artifact.valid) return 'declared_loaded_valid'
  if (isDeclared && artifact.exists && !artifact.valid) return 'loaded_invalid'
  if (isDeclared && !artifact.exists) return 'declared_missing'
  if (!isDeclared && artifact.exists && !artifact.valid) return 'loaded_invalid'
  return 'loaded_undeclared'
}

function deriveHardGateUnsatisfied(readinessStatus?: string): boolean {
  const normalized = readinessStatus ?? 'unknown'
  return normalized !== 'ready' && normalized !== 'pass'
}

function deriveRunBlocked(currentRunStatus?: string): boolean {
  const normalized = currentRunStatus ?? 'unknown'
  return normalized === 'blocked' || normalized === 'repair_required' || normalized === 'failed'
}

const ARTIFACT_EXPLORER_FAMILY_BY_NAME: Record<string, string> = {
  'next_action_recommendation_record.json': 'recommendation',
  'recommendation_accuracy_tracker.json': 'recommendation',
  'recommendation_review_surface.json': 'recommendation',
  'current_run_state_record.json': 'run_state',
  'hard_gate_status_record.json': 'hard_gate'
}

function artifactExplorerFamily(name: string): string {
  return ARTIFACT_EXPLORER_FAMILY_BY_NAME[name] ?? 'snapshot/publication'
}

export function selectDashboardViewModel(publication: DashboardPublication): DashboardViewModel {
  const state = deriveRenderState(publication)
  const sectionState: SectionState = state.kind === 'renderable' ? 'renderable' : state.kind === 'no_data' ? 'empty' : state.kind

  const snapshot = publication.snapshot.data
  const hardGate = publication.hardGate.data
  const runState = publication.runState.data
  const drift = publication.drift.data
  const bottleneck = publication.bottleneck.data
  const constitution = publication.constitution.data
  const deferredItems = publication.deferredRegister.data?.items ?? []
  const deferredReadiness = publication.deferredTracker.data?.items ?? []

  const declaredRequired = publication.manifest.data?.required_files ?? []
  const declaredArtifacts = new Set(declaredRequired)
  const loadedByName = new Map(publication.allArtifacts.map((item) => [item.name, item]))

  const loadedCount = declaredRequired.filter((name) => {
    const loaded = loadedByName.get(name)
    return Boolean(loaded?.exists)
  }).length
  const validLoadedCount = declaredRequired.filter((name) => {
    const loaded = loadedByName.get(name)
    return Boolean(loaded?.exists && loaded.valid)
  }).length
  const declaredCount = declaredRequired.length

  const manifestCompleteness = declaredCount === 0
    ? 'No declared artifacts'
    : validLoadedCount >= declaredCount
      ? `Complete (${validLoadedCount}/${declaredCount})`
      : `Incomplete (${validLoadedCount}/${declaredCount} valid declared artifacts)`

  const syncAuditState = publication.syncAudit.exists && publication.syncAudit.valid
    ? `sync_audit:${publication.syncAudit.data?.publication_state ?? 'unknown'}`
    : `sync_audit_unavailable:${publication.syncAudit.error ?? 'missing_or_invalid'}`

  const hardGateUnsatisfied = deriveHardGateUnsatisfied(hardGate?.readiness_status)
  const runBlocked = deriveRunBlocked(runState?.current_run_status)

  const recommendationRecords = publication.recommendationRecord.data?.records ?? []
  const recommendationRecord = recommendationRecords.length ? recommendationRecords[recommendationRecords.length - 1] : null
  const recommendationIsArtifactBacked = publication.recommendationRecord.exists && publication.recommendationRecord.valid && recommendationRecord !== null

  const recommendation = recommendationIsArtifactBacked
    ? {
        title: recommendationRecord.recommended_next_action ?? 'Recommendation record missing action text',
        reason: `Recommendation ID ${recommendationRecord.recommendation_id ?? 'unknown'} from governed artifact record.`,
        confidence: confidenceFromScore(recommendationRecord.confidence),
        sourceBasis: 'recommendation artifact',
        why: [
          `Derived from cycle ${recommendationRecord.cycle_id ?? 'unknown'}.`,
          `Backed by ${(recommendationRecord.provenance_categories ?? []).join(', ') || 'declared provenance categories'}.`
        ],
        whatChanges: [
          'Recommendation record changes in a newer cycle artifact.',
          'Source artifacts in source_basis shift due to new execution evidence.'
        ],
        provenance: recommendationProvenanceRows(recommendationRecord, publication.recommendationRecord.timestamp),
        synthesizedFallback: false
      }
    : {
        title: 'No recommendation available',
        reason: 'Governed recommendation artifact missing or invalid',
        confidence: 'Low' as const,
        sourceBasis: 'abstain_missing_artifact',
        why: [
          'UI abstains when recommendation artifact is missing or invalid.',
          'No local recommendation policy is synthesized in fallback path.'
        ],
        whatChanges: ['Publish a valid next_action_recommendation_record artifact to populate recommendation content.'],
        provenance: [{
          artifact: publication.recommendationRecord.name,
          path: publication.recommendationRecord.path,
          keyFields: ['unknown'],
          timestamp: publication.recommendationRecord.timestamp,
          provenanceConfidence: 'low' as const
        }],
        synthesizedFallback: true
      }

  const freshnessHours = snapshot ? Math.max(0, Math.floor((Date.now() - Date.parse(publication.snapshotMeta.data?.last_refreshed_time ?? '')) / (1000 * 60 * 60))) : 0

  const topology = [
    { node: 'RIL', artifact: publication.snapshot },
    { node: 'CDE', artifact: publication.bottleneck },
    { node: 'TLC', artifact: publication.runState },
    { node: 'PQX', artifact: publication.constitution },
    { node: 'FRE', artifact: publication.drift },
    { node: 'SEL', artifact: publication.hardGate },
    { node: 'PRG', artifact: publication.manifest }
  ].map(({ node, artifact }) => ({
    node,
    status: (artifact.exists ? (artifact.valid ? 'online' : 'degraded') : 'missing') as 'online' | 'missing' | 'degraded',
    provenance: artifact.path
  }))

  const explorerRows = [
    ...publication.allArtifacts
      .filter((artifact) => declaredArtifacts.has(artifact.name) || artifact.exists)
      .map((artifact) => ({
        family: artifactExplorerFamily(artifact.name),
        name: artifact.name,
        path: artifact.path,
        status: classifyExplorerStatus(artifact, declaredArtifacts)
      })),
    ...declaredRequired
      .filter((name) => !loadedByName.has(name))
      .map((name) => ({
        family: artifactExplorerFamily(name),
        name,
        path: `/${name}`,
        status: 'declared_not_loaded' as const
      }))
  ]

  return {
    state,
    repoName: snapshot?.repo_name ?? 'Not available yet',
    freshness: {
      status: state.kind === 'stale' ? 'Stale' : state.kind === 'renderable' ? 'Fresh' : 'Unknown',
      lastRefresh: publication.snapshotMeta.data?.last_refreshed_time ?? 'Not available yet',
      note: `Snapshot age is ${freshnessHours}h.`
    },
    integrity: {
      manifestCompleteness,
      publicationState: publication.manifest.data?.publication_state ?? state.kind,
      syncAuditState,
      declaredCount,
      loadedCount,
      validLoadedCount
    },
    recommendation,
    comparison: {
      bottleneck: 'Prior comparison unavailable',
      drift: drift?.trend ?? 'Not available yet',
      hardGate: hardGate?.readiness_status ?? 'Not available yet',
      runState: runState?.current_run_status ?? 'Not available yet',
      recommendation: recommendation.title,
      warningReasons: state.truthViolationReasons.join(', ') || 'No truth-violation reason codes'
    },
    topology,
    artifactExplorer: explorerRows,
    reviewQueue: [
      ...(state.kind !== 'renderable' ? [{ kind: 'freeze' as const, reason: state.reason }] : []),
      ...(hardGateUnsatisfied ? [{ kind: 'require_human_review' as const, reason: 'Hard gate unsatisfied.' }] : []),
      ...(runBlocked ? [{ kind: 'warn' as const, reason: 'Run blocked/repair-needed.' }] : []),
      ...(constitution?.violations?.length ? [{ kind: 'governance_exception' as const, reason: constitution.violations.join('; ') }] : [])
    ],
    healthScorecards: [
      { family: 'snapshot/publication', score: publication.snapshot.exists ? 100 : 0, grade: publication.snapshot.exists ? 'A' : 'F', rule: 'artifact exists + valid' },
      { family: 'run state', score: publication.runState.exists ? 100 : 0, grade: publication.runState.exists ? 'A' : 'F', rule: 'current_run_state_record required' },
      { family: 'hard gate', score: hardGateUnsatisfied ? 40 : 100, grade: hardGateUnsatisfied ? 'D' : 'A', rule: 'readiness_status enum must be ready/pass' },
      { family: 'drift', score: publication.drift.exists ? 100 : 0, grade: publication.drift.exists ? 'A' : 'F', rule: 'drift artifact required' },
      { family: 'recommendation quality', score: state.kind === 'renderable' && !recommendation.synthesizedFallback ? 100 : 20, grade: state.kind === 'renderable' && !recommendation.synthesizedFallback ? 'A' : 'D', rule: 'recommendation artifact should be available and valid' },
      { family: 'constitutional alignment', score: constitution?.violations?.length ? 30 : 100, grade: constitution?.violations?.length ? 'D' : 'A', rule: 'no constitutional violations' }
    ],
    sections: {
      snapshot: makeSection('Repository snapshot', snapshot ?? null, sectionState, state.reason, [{ artifact: publication.snapshot.name, path: publication.snapshot.path, keyFields: ['repo_name', 'root_counts', 'runtime_hotspots'] }]),
      bottleneck: makeSection('Bottleneck', bottleneck ?? null, sectionState, state.reason, [{ artifact: publication.bottleneck.name, path: publication.bottleneck.path, keyFields: ['bottleneck_name', 'explanation'] }]),
      drift: makeSection('Drift', drift ?? null, sectionState, state.reason, [{ artifact: publication.drift.name, path: publication.drift.path, keyFields: ['drift_classification', 'trend'] }]),
      hardGate: makeSection('Hard gate', hardGate ?? null, sectionState, state.reason, [{ artifact: publication.hardGate.name, path: publication.hardGate.path, keyFields: ['gate_name', 'readiness_status'] }]),
      runState: makeSection('Run state', runState ?? null, sectionState, state.reason, [{ artifact: publication.runState.name, path: publication.runState.path, keyFields: ['current_run_status', 'repair_loop_count'] }]),
      deferred: makeSection('Deferred items', { items: deferredItems, readiness: deferredReadiness }, publication.deferredRegister.exists ? sectionState : 'unavailable', publication.deferredRegister.exists ? state.reason : 'Deferred artifact unavailable.', [{ artifact: publication.deferredRegister.name, path: publication.deferredRegister.path, keyFields: ['items'], timestamp: publication.deferredRegister.timestamp }]),
      constitutional: makeSection('Constitutional checks', constitution ?? null, publication.constitution.exists ? sectionState : 'unavailable', publication.constitution.exists ? state.reason : 'Constitutional artifact unavailable.', [{ artifact: publication.constitution.name, path: publication.constitution.path, keyFields: ['status', 'violations'] }])
    },
    provenance: publication.allArtifacts.map((item) => ({
      name: item.name,
      path: item.path,
      status: item.exists ? (item.valid ? 'valid' : 'invalid') : 'missing',
      timestamp: item.timestamp,
      keysUsed: item.name === 'repo_snapshot.json'
        ? ['repo_name', 'root_counts', 'runtime_hotspots']
        : item.name === 'repo_snapshot_meta.json'
          ? ['data_source_state', 'last_refreshed_time']
          : item.name === 'hard_gate_status_record.json'
            ? ['gate_name', 'readiness_status']
            : item.name === 'current_run_state_record.json'
              ? ['current_run_status', 'repair_loop_count']
              : item.name === 'next_action_recommendation_record.json'
                ? ['records', 'recommended_next_action', 'confidence', 'source_basis']
                : item.name === 'dashboard_publication_sync_audit.json'
                  ? ['artifact_type', 'publication_state', 'required_artifact_count', 'records']
                  : item.name === 'dashboard_publication_manifest.json'
                    ? ['publication_state', 'artifact_count', 'required_files']
                    : ['unknown'],
      provenanceConfidence: item.name === 'repo_snapshot.json' ||
        item.name === 'repo_snapshot_meta.json' ||
        item.name === 'hard_gate_status_record.json' ||
        item.name === 'current_run_state_record.json' ||
        item.name === 'next_action_recommendation_record.json' ||
        item.name === 'dashboard_publication_sync_audit.json' ||
        item.name === 'dashboard_publication_manifest.json'
        ? 'high'
        : 'low'
    })),
    trends: [
      { label: 'freshness', value: state.kind === 'stale' ? 'stale' : 'live' },
      { label: 'drift', value: drift?.trend ?? 'not available' },
      { label: 'repair loops', value: String(runState?.repair_loop_count ?? 'not available') },
      { label: 'recommendation accuracy', value: publication.recommendationAccuracyTracker.data?.accuracy !== undefined ? String(publication.recommendationAccuracyTracker.data.accuracy) : 'artifact unavailable' },
      { label: 'trust/operator posture', value: state.kind === 'renderable' ? 'operational' : 'degraded' },
      { label: 'exception pressure', value: constitution?.violations?.length ? 'elevated' : 'normal' }
    ],
    history: {
      status: 'no-history',
      entries: ['History artifacts not published in current bundle.']
    }
  }
}
