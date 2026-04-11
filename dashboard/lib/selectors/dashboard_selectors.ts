import type { DashboardPublication, DashboardViewModel, SectionInput, SectionState } from '../../types/dashboard'
import { deriveRenderState } from '../guards/render_state_guards'

function statusFromState(state: SectionState): string {
  if (state === 'renderable') return 'renderable'
  return state
}

function makeSection<T>(title: string, data: T | null, state: SectionState, reason: string, provenance: SectionInput<T>['provenance']): SectionInput<T> {
  return { title, data, state, reason, provenance }
}

function truthyStatus(value?: string): boolean {
  const v = (value ?? '').toLowerCase()
  return ['pass', 'ready', 'good', 'healthy', 'satisfied'].some((token) => v.includes(token))
}

function blockedStatus(value?: string): boolean {
  const v = (value ?? '').toLowerCase()
  return ['block', 'repair', 'fail', 'risk', 'freeze'].some((token) => v.includes(token))
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

  const truthViolation = state.kind !== 'renderable'
  const hardGateUnsatisfied = !truthyStatus(hardGate?.readiness_status)
  const runBlocked = blockedStatus(runState?.current_run_status)

  const recommendation = truthViolation
    ? {
        title: 'No recommendation: fail-closed truth gate active',
        reason: 'Critical artifacts are missing, stale, invalid, or not live-backed.',
        confidence: 'Low' as const,
        sourceBasis: 'truth gate',
        why: ['UI cannot imply correctness without backed artifacts.', 'Fail-closed execution blocks operator guidance under truth violation.'],
        whatChanges: ['Required artifacts are publish-complete.', 'Freshness and source-live checks pass.']
      }
    : hardGateUnsatisfied
      ? {
          title: `Satisfy hard gate: ${hardGate?.gate_name ?? 'active gate'}`,
          reason: 'Promotion requires certification and hard-gate evidence closure.',
          confidence: 'High' as const,
          sourceBasis: 'hard gate',
          why: ['Hard gate readiness is unsatisfied.', 'Control integrity remains blocked.'],
          whatChanges: ['Required hard-gate evidence becomes complete.', 'Hard gate readiness moves to pass/ready.']
        }
      : runBlocked
        ? {
            title: `Run bounded repair for ${bottleneck?.bottleneck_name ?? 'current bottleneck'}`,
            reason: 'Current run-state artifact indicates blocked or repair-needed execution.',
            confidence: 'High' as const,
            sourceBasis: 'run state',
            why: ['Run-state indicates blocked flow.', 'Repair loop pressure should be reduced before expansion.'],
            whatChanges: ['Run state clears from blocked/repair.', 'Repair loop pressure stabilizes.']
          }
        : {
            title: `Address bottleneck: ${bottleneck?.bottleneck_name ?? 'best available target'}`,
            reason: bottleneck?.explanation ?? 'Bottleneck evidence exists in published artifacts.',
            confidence: 'Medium' as const,
            sourceBasis: 'bottleneck',
            why: ['Current bottleneck artifact exists.', 'Reducing bottleneck improves execution integrity.'],
            whatChanges: ['Hard gate becomes unsatisfied.', 'Run state becomes blocked.']
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

  return {
    state,
    repoName: snapshot?.repo_name ?? 'Not available yet',
    freshness: {
      status: state.kind === 'stale' ? 'Stale' : state.kind === 'renderable' ? 'Fresh' : 'Unknown',
      lastRefresh: publication.snapshotMeta.data?.last_refreshed_time ?? 'Not available yet',
      note: `Snapshot age is ${freshnessHours}h.`
    },
    integrity: {
      manifestCompleteness: state.missingArtifacts.length ? 'Incomplete' : 'Complete',
      publicationState: state.kind,
      syncAuditState: publication.manifest.exists ? 'Published' : 'Missing manifest'
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
    artifactExplorer: publication.allArtifacts.map((artifact) => ({
      family: artifact.name.includes('recommendation') ? 'recommendation' : artifact.name.includes('run') ? 'run_state' : artifact.name.includes('gate') ? 'hard_gate' : 'snapshot/publication',
      name: artifact.name,
      path: artifact.path,
      status: artifact.exists ? (artifact.valid ? 'valid' : 'invalid') : 'missing'
    })),
    reviewQueue: [
      ...(state.kind !== 'renderable' ? [{ kind: 'freeze' as const, reason: state.reason }] : []),
      ...(hardGateUnsatisfied ? [{ kind: 'require_human_review' as const, reason: 'Hard gate unsatisfied.' }] : []),
      ...(runBlocked ? [{ kind: 'warn' as const, reason: 'Run blocked/repair-needed.' }] : []),
      ...(constitution?.violations?.length ? [{ kind: 'governance_exception' as const, reason: constitution.violations.join('; ') }] : [])
    ],
    healthScorecards: [
      { family: 'snapshot/publication', score: publication.snapshot.exists ? 100 : 0, grade: publication.snapshot.exists ? 'A' : 'F', rule: 'artifact exists + valid' },
      { family: 'run state', score: publication.runState.exists ? 100 : 0, grade: publication.runState.exists ? 'A' : 'F', rule: 'current_run_state_record required' },
      { family: 'hard gate', score: truthyStatus(hardGate?.readiness_status) ? 100 : 40, grade: truthyStatus(hardGate?.readiness_status) ? 'A' : 'D', rule: 'readiness_status must indicate pass/ready' },
      { family: 'drift', score: publication.drift.exists ? 100 : 0, grade: publication.drift.exists ? 'A' : 'F', rule: 'drift artifact required' },
      { family: 'recommendation quality', score: state.kind === 'renderable' ? 100 : 20, grade: state.kind === 'renderable' ? 'A' : 'D', rule: 'truth render gate must be renderable' },
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
      keysUsed: ['artifact-backed']
    })),
    trends: [
      { label: 'freshness', value: state.kind === 'stale' ? 'stale' : 'live' },
      { label: 'drift', value: drift?.trend ?? 'not available' },
      { label: 'repair loops', value: String(runState?.repair_loop_count ?? 'not available') },
      { label: 'recommendation accuracy', value: 'artifact unavailable' },
      { label: 'trust/operator posture', value: state.kind === 'renderable' ? 'operational' : 'degraded' },
      { label: 'exception pressure', value: constitution?.violations?.length ? 'elevated' : 'normal' }
    ],
    history: {
      status: 'no-history',
      entries: ['History artifacts not published in current bundle.']
    }
  }
}
