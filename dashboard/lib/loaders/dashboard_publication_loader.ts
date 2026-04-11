import type {
  ArtifactRecord,
  BottleneckRecord,
  ConstitutionResult,
  DashboardManifest,
  DashboardPublication,
  DeferredItem,
  DeferredReadiness,
  DriftRecord,
  HardGateState,
  RecommendationAccuracyTracker,
  RecommendationRecordCollection,
  RunState,
  Snapshot,
  SnapshotMeta
} from '../../types/dashboard'
import { fetchJsonArtifact } from './fetch_json_artifact'
import { markValidated } from '../validation/dashboard_validation'

function notLoadedArtifact(name: string): ArtifactRecord {
  return {
    name,
    path: `/${name}`,
    exists: false,
    valid: false,
    data: null,
    error: 'Artifact declared as optional/unloaded in current dashboard publication loader.'
  }
}

export async function loadDashboardPublication(): Promise<DashboardPublication> {
  const manifest = markValidated(await fetchJsonArtifact<DashboardManifest>('dashboard_publication_manifest.json'))
  const declaredArtifacts = new Set(manifest.data?.required_files ?? [])

  const [
    snapshot,
    snapshotMeta,
    drift,
    runState,
    hardGate,
    bottleneck,
    constitution,
    deferredRegister,
    deferredTracker,
    recommendationRecord,
    recommendationAccuracyTracker
  ] = await Promise.all([
    fetchJsonArtifact<Snapshot>('repo_snapshot.json'),
    fetchJsonArtifact<SnapshotMeta>('repo_snapshot_meta.json'),
    fetchJsonArtifact<DriftRecord>('drift_trend_continuity_artifact.json'),
    fetchJsonArtifact<RunState>('current_run_state_record.json'),
    fetchJsonArtifact<HardGateState>('hard_gate_status_record.json'),
    fetchJsonArtifact<BottleneckRecord>('current_bottleneck_record.json'),
    fetchJsonArtifact<ConstitutionResult>('constitutional_drift_checker_result.json'),
    fetchJsonArtifact<{ items?: DeferredItem[] }>('deferred_item_register.json'),
    fetchJsonArtifact<{ items?: DeferredReadiness[] }>('deferred_return_tracker.json'),
    fetchJsonArtifact<RecommendationRecordCollection>('next_action_recommendation_record.json'),
    declaredArtifacts.has('recommendation_accuracy_tracker.json')
      ? fetchJsonArtifact<RecommendationAccuracyTracker>('recommendation_accuracy_tracker.json')
      : Promise.resolve(notLoadedArtifact('recommendation_accuracy_tracker.json') as ArtifactRecord<RecommendationAccuracyTracker>)
  ])

  const validatedArtifacts = [
    snapshot,
    snapshotMeta,
    drift,
    runState,
    hardGate,
    bottleneck,
    constitution,
    deferredRegister,
    deferredTracker,
    recommendationRecord,
    recommendationAccuracyTracker
  ].map(markValidated)

  return {
    manifest,
    snapshot: validatedArtifacts[0] as ArtifactRecord<Snapshot>,
    snapshotMeta: validatedArtifacts[1] as ArtifactRecord<SnapshotMeta>,
    drift: validatedArtifacts[2] as ArtifactRecord<DriftRecord>,
    runState: validatedArtifacts[3] as ArtifactRecord<RunState>,
    hardGate: validatedArtifacts[4] as ArtifactRecord<HardGateState>,
    bottleneck: validatedArtifacts[5] as ArtifactRecord<BottleneckRecord>,
    constitution: validatedArtifacts[6] as ArtifactRecord<ConstitutionResult>,
    deferredRegister: validatedArtifacts[7] as ArtifactRecord<{ items?: DeferredItem[] }>,
    deferredTracker: validatedArtifacts[8] as ArtifactRecord<{ items?: DeferredReadiness[] }>,
    recommendationRecord: validatedArtifacts[9] as ArtifactRecord<RecommendationRecordCollection>,
    recommendationAccuracyTracker: validatedArtifacts[10] as ArtifactRecord<RecommendationAccuracyTracker>,
    allArtifacts: [manifest, ...validatedArtifacts]
  }
}
