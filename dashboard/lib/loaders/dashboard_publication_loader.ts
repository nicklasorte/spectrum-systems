import type {
  ArtifactRecord,
  BottleneckRecord,
  ConstitutionResult,
  DashboardManifest,
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

function artifactByName<T>(artifacts: ArtifactRecord[], name: string): ArtifactRecord<T> {
  const artifact = artifacts.find((item) => item.name === name)
  return artifact ? (artifact as ArtifactRecord<T>) : missingArtifact<T>(name)
}

export async function loadDashboardPublication(): Promise<DashboardPublication> {
  const manifest = markValidated(await fetchJsonArtifact<DashboardManifest>('dashboard_publication_manifest.json'))
  const requiredFiles = manifest.data?.required_files ?? []

  const loadedRequiredArtifacts = await Promise.all(requiredFiles.map((name) => fetchJsonArtifact(name)))
  const validatedArtifacts = loadedRequiredArtifacts.map(markValidated)

  return {
    manifest,
    snapshot: artifactByName<Snapshot>(validatedArtifacts, 'repo_snapshot.json'),
    snapshotMeta: artifactByName<SnapshotMeta>(validatedArtifacts, 'repo_snapshot_meta.json'),
    drift: artifactByName<DriftRecord>(validatedArtifacts, 'drift_trend_continuity_artifact.json'),
    runState: artifactByName<RunState>(validatedArtifacts, 'current_run_state_record.json'),
    hardGate: artifactByName<HardGateState>(validatedArtifacts, 'hard_gate_status_record.json'),
    bottleneck: artifactByName<BottleneckRecord>(validatedArtifacts, 'current_bottleneck_record.json'),
    constitution: artifactByName<ConstitutionResult>(validatedArtifacts, 'constitutional_drift_checker_result.json'),
    deferredRegister: artifactByName<{ items?: DeferredItem[] }>(validatedArtifacts, 'deferred_item_register.json'),
    deferredTracker: artifactByName<{ items?: DeferredReadiness[] }>(validatedArtifacts, 'deferred_return_tracker.json'),
    recommendationRecord: artifactByName<RecommendationRecordCollection>(validatedArtifacts, 'next_action_recommendation_record.json'),
    syncAudit: artifactByName<DashboardPublicationSyncAudit>(validatedArtifacts, 'dashboard_publication_sync_audit.json'),
    recommendationAccuracyTracker: artifactByName<RecommendationAccuracyTracker>(validatedArtifacts, 'recommendation_accuracy_tracker.json'),
    allArtifacts: [manifest, ...validatedArtifacts]
  }
}
