import type { DashboardPublication, RenderStateKind } from '../../types/dashboard'

const critical = ['repo_snapshot.json', 'repo_snapshot_meta.json', 'hard_gate_status_record.json', 'current_run_state_record.json', 'drift_trend_continuity_artifact.json', 'current_bottleneck_record.json']

export function deriveRenderState(publication: DashboardPublication): {
  kind: RenderStateKind
  reason: string
  missingArtifacts: string[]
  staleArtifacts: string[]
  truthViolationReasons: string[]
} {
  const missing = publication.allArtifacts.filter((item) => !item.exists || !item.valid).map((item) => item.name)

  if (!publication.snapshot.exists && !publication.snapshotMeta.exists) {
    return { kind: 'no_data', reason: 'No dashboard publication artifacts available.', missingArtifacts: ['repo_snapshot.json', 'repo_snapshot_meta.json'], staleArtifacts: [], truthViolationReasons: ['no_publication'] }
  }

  const missingCritical = critical.filter((name) => missing.includes(name))
  if (missingCritical.length > 0) {
    return { kind: 'incomplete_publication', reason: 'Required publication artifacts are incomplete.', missingArtifacts: missingCritical, staleArtifacts: [], truthViolationReasons: ['missing_critical_artifact'] }
  }

  const refreshed = publication.snapshotMeta.data?.last_refreshed_time
  const sourceState = (publication.snapshotMeta.data?.data_source_state ?? '').toLowerCase()
  const stale = refreshed ? (Date.now() - Date.parse(refreshed)) / (1000 * 60 * 60) > 6 : true

  if (stale) {
    return { kind: 'stale', reason: 'Publication freshness gate failed.', missingArtifacts: [], staleArtifacts: ['repo_snapshot.json'], truthViolationReasons: ['stale_publication'] }
  }

  if (sourceState !== 'live') {
    return { kind: 'truth_violation', reason: 'Publication source is not live.', missingArtifacts: [], staleArtifacts: [], truthViolationReasons: ['source_not_live'] }
  }

  return { kind: 'renderable', reason: 'Publication is renderable.', missingArtifacts: [], staleArtifacts: [], truthViolationReasons: [] }
}
