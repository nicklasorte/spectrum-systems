import type {
  ArtifactRecord,
  BottleneckRecord,
  ConstitutionResult,
  DashboardManifest,
  DashboardFreshnessStatus,
  DashboardPublication,
  DeferredItem,
  DeferredReadiness,
  DriftRecord,
  DashboardPublicationSyncAudit,
  HardGateState,
  RecommendationAccuracyTracker,
  RecommendationRecordCollection,
  RunState,
  Snapshot,
  SnapshotMeta
} from '../../types/dashboard'
import { fetchJsonArtifact } from './fetch_json_artifact'
import { markValidated } from '../validation/dashboard_validation'

function missingArtifact<T>(name: string): ArtifactRecord<T> {
  return {
    name,
    path: `/${name}`,
    exists: false,
    valid: false,
    data: null,
    error: 'Artifact declared in publication contract but not retrievable.'
  }
}

function artifactByName<T>(artifactsByName: Map<string, ArtifactRecord>, name: string): ArtifactRecord<T> {
  const artifact = artifactsByName.get(name)
  return artifact ? (artifact as ArtifactRecord<T>) : missingArtifact<T>(name)
}

export async function loadDashboardPublication(): Promise<DashboardPublication> {
  const manifest = markValidated(await fetchJsonArtifact<DashboardManifest>('dashboard_publication_manifest.json'))
  const requiredFiles = manifest.data?.required_files ?? []

  const declaredArtifacts = await Promise.all(requiredFiles.map((name) => fetchJsonArtifact(name)))
  const validatedDeclaredArtifacts = declaredArtifacts.map(markValidated)
  const declaredArtifactsByName = new Map(validatedDeclaredArtifacts.map((artifact) => [artifact.name, artifact]))

  return {
    manifest,
    snapshot: artifactByName<Snapshot>(declaredArtifactsByName, 'repo_snapshot.json'),
    snapshotMeta: artifactByName<SnapshotMeta>(declaredArtifactsByName, 'repo_snapshot_meta.json'),
    freshnessStatus: artifactByName<DashboardFreshnessStatus>(declaredArtifactsByName, 'dashboard_freshness_status.json'),
    drift: artifactByName<DriftRecord>(declaredArtifactsByName, 'drift_trend_continuity_artifact.json'),
    runState: artifactByName<RunState>(declaredArtifactsByName, 'current_run_state_record.json'),
    hardGate: artifactByName<HardGateState>(declaredArtifactsByName, 'hard_gate_status_record.json'),
    bottleneck: artifactByName<BottleneckRecord>(declaredArtifactsByName, 'current_bottleneck_record.json'),
    constitution: artifactByName<ConstitutionResult>(declaredArtifactsByName, 'constitutional_drift_checker_result.json'),
    deferredRegister: artifactByName<{ items?: DeferredItem[] }>(declaredArtifactsByName, 'deferred_item_register.json'),
    deferredTracker: artifactByName<{ items?: DeferredReadiness[] }>(declaredArtifactsByName, 'deferred_return_tracker.json'),
    recommendationRecord: artifactByName<RecommendationRecordCollection>(declaredArtifactsByName, 'next_action_recommendation_record.json'),
    syncAudit: artifactByName<DashboardPublicationSyncAudit>(declaredArtifactsByName, 'dashboard_publication_sync_audit.json'),
    recommendationAccuracyTracker: artifactByName<RecommendationAccuracyTracker>(declaredArtifactsByName, 'recommendation_accuracy_tracker.json'),
    declaredArtifactMap: Object.fromEntries(validatedDeclaredArtifacts.map((artifact) => [artifact.name, artifact])),
    allArtifacts: [manifest, ...validatedDeclaredArtifacts]
  }
}
