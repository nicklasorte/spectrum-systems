import type { DashboardPublication, RenderStateKind } from '../../types/dashboard'

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

  const refreshed = publication.snapshotMeta.data?.last_refreshed_time
  const stale = refreshed ? (Date.now() - Date.parse(refreshed)) / (1000 * 60 * 60) > 6 : true
  if (stale) {
    return {
      kind: 'stale',
      reason: 'Publication freshness gate failed.',
      missingArtifacts: [],
      staleArtifacts: ['repo_snapshot.json'],
      truthViolationReasons: ['stale_publication']
    }
  }

  return { kind: 'renderable', reason: 'Publication is renderable.', missingArtifacts: [], staleArtifacts: [], truthViolationReasons: [] }
}
