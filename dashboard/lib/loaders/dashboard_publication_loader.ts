import type {
  BottleneckRecord,
  ConstitutionResult,
  DashboardPublication,
  DeferredItem,
  DeferredReadiness,
  DriftRecord,
  HardGateState,
  RunState,
  Snapshot,
  SnapshotMeta
} from '../../types/dashboard'
import { fetchJsonArtifact } from './fetch_json_artifact'
import { markValidated } from '../validation/dashboard_validation'

export async function loadDashboardPublication(): Promise<DashboardPublication> {
  const [
    manifest,
    snapshot,
    snapshotMeta,
    drift,
    runState,
    hardGate,
    bottleneck,
    constitution,
    deferredRegister,
    deferredTracker
  ] = await Promise.all([
    fetchJsonArtifact<Record<string, unknown>>('dashboard_publication_manifest.json'),
    fetchJsonArtifact<Snapshot>('repo_snapshot.json'),
    fetchJsonArtifact<SnapshotMeta>('repo_snapshot_meta.json'),
    fetchJsonArtifact<DriftRecord>('drift_trend_continuity_artifact.json'),
    fetchJsonArtifact<RunState>('current_run_state_record.json'),
    fetchJsonArtifact<HardGateState>('hard_gate_status_record.json'),
    fetchJsonArtifact<BottleneckRecord>('current_bottleneck_record.json'),
    fetchJsonArtifact<ConstitutionResult>('constitutional_drift_checker_result.json'),
    fetchJsonArtifact<{ items?: DeferredItem[] }>('deferred_item_register.json'),
    fetchJsonArtifact<{ items?: DeferredReadiness[] }>('deferred_return_tracker.json')
  ])

  const allArtifacts = [manifest, snapshot, snapshotMeta, drift, runState, hardGate, bottleneck, constitution, deferredRegister, deferredTracker].map(markValidated)

  return {
    manifest: markValidated(manifest),
    snapshot: markValidated(snapshot),
    snapshotMeta: markValidated(snapshotMeta),
    drift: markValidated(drift),
    runState: markValidated(runState),
    hardGate: markValidated(hardGate),
    bottleneck: markValidated(bottleneck),
    constitution: markValidated(constitution),
    deferredRegister: markValidated(deferredRegister),
    deferredTracker: markValidated(deferredTracker),
    allArtifacts
  }
}
