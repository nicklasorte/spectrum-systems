import type { DashboardPublication, RenderStateKind } from '../../types/dashboard'

const DEFAULT_FRESHNESS_WINDOW_HOURS = 6

function parseIsoUtcTimestamp(raw: unknown): number | null {
  if (typeof raw !== 'string') return null
  const trimmed = raw.trim()
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(trimmed)) return null
  const parsed = Date.parse(trimmed)
  return Number.isFinite(parsed) ? parsed : null
}

export function deriveRenderState(publication: DashboardPublication): {
  kind: RenderStateKind
  reason: string
  missingArtifacts: string[]
  staleArtifacts: string[]
  truthViolationReasons: string[]
} {
  const loadedByName = new Map(publication.allArtifacts.map((item) => [item.name, item]))
  const declaredArtifacts = publication.manifest.data?.required_files ?? []

  const missingDeclared = declaredArtifacts.filter((name) => {
    const item = loadedByName.get(name)
    return !item || !item.exists
  })

  const invalidLoaded = publication.allArtifacts.filter((item) => item.exists && !item.valid).map((item) => item.name)
  const incompleteArtifacts = [...new Set([...missingDeclared, ...invalidLoaded])]

  if (!publication.snapshot.exists && !publication.snapshotMeta.exists) {
    return {
      kind: 'no_data',
      reason: 'No dashboard publication artifacts available.',
      missingArtifacts: ['repo_snapshot.json', 'repo_snapshot_meta.json'],
      staleArtifacts: [],
      truthViolationReasons: ['no_publication']
    }
  }

  if (incompleteArtifacts.length > 0) {
    return {
      kind: 'incomplete_publication',
      reason: 'Manifest-declared publication artifacts are incomplete, missing, or invalid.',
      missingArtifacts: incompleteArtifacts,
      staleArtifacts: [],
      truthViolationReasons: ['incomplete_manifest_coverage']
    }
  }

  const sourceState = String(publication.snapshotMeta.data?.data_source_state ?? '').toLowerCase()
  if (sourceState !== 'live') {
    return {
      kind: 'truth_violation',
      reason: 'Publication source is not live.',
      missingArtifacts: [],
      staleArtifacts: [],
      truthViolationReasons: ['source_not_live']
    }
  }

  const freshnessPublicationState = String(publication.freshnessStatus.data?.publication_state ?? '').toLowerCase()
  if (freshnessPublicationState && freshnessPublicationState !== 'live') {
    return {
      kind: 'truth_violation',
      reason: 'Publication freshness state is not live.',
      missingArtifacts: [],
      staleArtifacts: [],
      truthViolationReasons: ['source_not_live']
    }
  }

  const freshnessWindow = publication.freshnessStatus.data?.freshness_window_hours
  const thresholdHours = Number.isFinite(freshnessWindow) && Number(freshnessWindow) > 0
    ? Number(freshnessWindow)
    : DEFAULT_FRESHNESS_WINDOW_HOURS
  const freshnessTimestampMs = parseIsoUtcTimestamp(publication.freshnessStatus.data?.snapshot_last_refreshed_time)
  const metaTimestampMs = parseIsoUtcTimestamp(publication.snapshotMeta.data?.last_refreshed_time)
  const normalizedFreshnessStatus = String(publication.freshnessStatus.data?.status ?? '').toLowerCase()
  const staleByTime = freshnessTimestampMs === null ? true : (Date.now() - freshnessTimestampMs) / (1000 * 60 * 60) > thresholdHours
  const stale = freshnessTimestampMs === null ||
    metaTimestampMs === null ||
    freshnessTimestampMs !== metaTimestampMs ||
    (normalizedFreshnessStatus !== 'fresh' && normalizedFreshnessStatus !== 'stale') ||
    (normalizedFreshnessStatus === 'fresh' && staleByTime) ||
    (normalizedFreshnessStatus === 'stale' && !staleByTime)

  if (stale) {
    return {
      kind: 'stale',
      reason: 'Publication freshness gate failed.',
      missingArtifacts: [],
      staleArtifacts: ['repo_snapshot.json'],
      truthViolationReasons: ['stale_publication']
    }
  }

  const attemptDecision = String(publication.publicationAttemptRecord.data?.decision ?? '').toLowerCase()
  if (attemptDecision && attemptDecision !== 'allow') {
    return {
      kind: 'truth_violation',
      reason: 'Governed publication attempt decision is not allow.',
      missingArtifacts: [],
      staleArtifacts: [],
      truthViolationReasons: ['publication_blocked']
    }
  }

  const refreshTrace = String(publication.refreshRunRecord.data?.trace_id ?? '')
  const freshnessTrace = String(publication.freshnessStatus.data?.trace_id ?? '')
  const publicationTrace = String(publication.publicationAttemptRecord.data?.trace_id ?? '')
  if (refreshTrace && freshnessTrace && publicationTrace && (refreshTrace !== freshnessTrace || refreshTrace !== publicationTrace)) {
    return {
      kind: 'truth_violation',
      reason: 'Trace linkage mismatch across refresh/freshness/publication artifacts.',
      missingArtifacts: [],
      staleArtifacts: [],
      truthViolationReasons: ['trace_linkage_missing']
    }
  }

  return { kind: 'renderable', reason: 'Publication is renderable.', missingArtifacts: [], staleArtifacts: [], truthViolationReasons: [] }
}
