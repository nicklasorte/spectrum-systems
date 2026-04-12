export type RenderStateKind = 'renderable' | 'no_data' | 'incomplete_publication' | 'stale' | 'truth_violation'

export type ArtifactRecord<T = unknown> = {
  name: string
  path: string
  exists: boolean
  valid: boolean
  data: T | null
  error?: string
  timestamp?: string
}

export type DashboardManifest = {
  publication_state?: string
  artifact_count?: number
  required_files?: string[]
}

export type Snapshot = {
  generated_at?: string
  freshness_timestamp_utc?: string
  repo_name?: string
  root_counts?: {
    files_total?: number
    runtime_modules?: number
    tests?: number
    contracts_total?: number
    docs?: number
    run_artifacts?: number
  }
  runtime_hotspots?: Array<{ area?: string; count?: number; note?: string }>
  operational_signals?: Array<{ title?: string; status?: string; detail?: string }>
}

export type SnapshotMeta = {
  last_refreshed_time?: string
  snapshot_size?: string
  data_source_state?: string
}

export type DashboardFreshnessStatus = {
  artifact_type?: 'dashboard_freshness_status'
  trace_id?: string
  refresh_run_id?: string
  freshness_window_hours?: number
  status?: 'fresh' | 'stale' | 'unknown'
  publication_state?: string
  snapshot_last_refreshed_time?: string
  snapshot_age_hours?: number
  evidence_basis?: string[]
}

export type DriftRecord = {
  drift_classification?: string
  trend?: string
  key_signals?: string[]
  short_recommendation?: string
}

export type HardGateReadinessStatus = 'ready' | 'pass' | 'blocked' | 'failed' | 'unknown'

export type HardGateState = {
  gate_name?: string
  readiness_status?: HardGateReadinessStatus
  pass_fail?: string
  required_evidence?: string[]
  falsification_risks?: string[]
}

export type RunExecutionStatus = 'healthy' | 'ready' | 'blocked' | 'repair_required' | 'failed' | 'unknown'

export type RunState = {
  current_run_status?: RunExecutionStatus
  status?: string
  last_successful_cycle?: string
  last_blocked_cycle?: string
  repair_loop_count?: number
  first_pass_quality?: string
}

export type BottleneckRecord = {
  bottleneck_name?: string
  explanation?: string
  impacted_layers?: string[]
  evidence?: string[]
}

export type ConstitutionResult = {
  status?: string
  summary?: string
  violations?: string[]
}

export type DeferredItem = {
  item_id?: string
  item_name?: string
  reason_deferred?: string
  missing_evidence?: string[]
  return_condition?: string
}

export type DeferredReadiness = { item_id?: string; readiness_signal?: string }

export type RecommendationRecord = {
  recommendation_id?: string
  cycle_id?: string
  recommended_next_action?: string
  confidence?: number
  source_basis?: string[]
  provenance_categories?: string[]
}

export type RecommendationRecordCollection = {
  records?: RecommendationRecord[]
}

export type RecommendationAccuracyTracker = {
  evaluated_recommendations?: number
  correct?: number
  partially_correct?: number
  wrong?: number
  accuracy?: number
}

export type DashboardPublicationSyncAudit = {
  artifact_type?: 'dashboard_publication_sync_audit'
  publication_state?: string
  required_artifact_count?: number
  records?: Array<{ artifact?: string; source?: string; sha256?: string; size_bytes?: number }>
}

export type RefreshRunRecord = {
  artifact_type?: 'refresh_run_record'
  refresh_run_id?: string
  trace_id?: string
  run_id?: string
  target_artifact_family?: string
  start_time?: string
  end_time?: string
  outcome?: 'success' | 'failed' | 'skipped' | 'partial'
  refreshed_artifacts?: string[]
  stale_artifacts_found?: string[]
  failure_class?: string
  trigger_mode?: 'scheduled' | 'manual' | 'repair' | 'test'
}

export type PublicationAttemptRecord = {
  artifact_type?: 'publication_attempt_record'
  publish_attempt_id?: string
  refresh_run_id?: string
  trace_id?: string
  decision?: 'allow' | 'block' | 'freeze'
  reason_codes?: string[]
  trigger_mode?: 'scheduled' | 'manual' | 'repair' | 'test'
  timestamp?: string
}

export type JudgmentApplicationArtifact = {
  artifact_type?: 'judgment_application_artifact'
  decision_id?: string
  judgment_ids?: string[]
  consumed_by_control?: boolean
  generated_at?: string
}

export type OperatorOverrideCaptureArtifact = {
  artifact_type?: 'operator_override_capture'
  generated_at?: string
  overrides?: Array<{
    override_id?: string
    recommendation_id?: string
    operator_action?: string
    reason?: string
    captured_as_learning_signal?: boolean
  }>
}

export type RecommendationReplayPack = {
  artifact_type?: 'recommendation_replay_pack'
  generated_at?: string
  scenario_ids?: string[]
  scenario_basis?: string
}

export type SerialBundleValidatorResult = {
  artifact_type?: 'serial_bundle_validator_result'
  generated_at?: string
  pass?: boolean
  pass_through_umbrellas?: string[]
  empty_batches?: string[]
}

export type DashboardPublicContractCoverage = {
  artifact_type?: 'dashboard_public_contract_coverage'
  generated_at?: string
  covered_artifacts?: string[]
}

export type GovernedPromotionDisciplineGate = {
  artifact_type?: 'governed_promotion_discipline_gate'
  generated_at?: string
  promotion_decision?: string
  allowed_decisions?: string[]
  fail_closed?: boolean
}

export type ExplorerCoverageStatus = 'declared_loaded_valid' | 'declared_not_loaded' | 'declared_missing' | 'loaded_invalid' | 'loaded_undeclared'

export type DashboardPublication = {
  manifest: ArtifactRecord<DashboardManifest>
  snapshot: ArtifactRecord<Snapshot>
  snapshotMeta: ArtifactRecord<SnapshotMeta>
  freshnessStatus: ArtifactRecord<DashboardFreshnessStatus>
  drift: ArtifactRecord<DriftRecord>
  runState: ArtifactRecord<RunState>
  hardGate: ArtifactRecord<HardGateState>
  bottleneck: ArtifactRecord<BottleneckRecord>
  constitution: ArtifactRecord<ConstitutionResult>
  deferredRegister: ArtifactRecord<{ items?: DeferredItem[] }>
  deferredTracker: ArtifactRecord<{ items?: DeferredReadiness[] }>
  recommendationRecord: ArtifactRecord<RecommendationRecordCollection>
  syncAudit: ArtifactRecord<DashboardPublicationSyncAudit>
  recommendationAccuracyTracker: ArtifactRecord<RecommendationAccuracyTracker>
  refreshRunRecord: ArtifactRecord<RefreshRunRecord>
  publicationAttemptRecord: ArtifactRecord<PublicationAttemptRecord>
  judgmentApplication: ArtifactRecord<JudgmentApplicationArtifact>
  overrideCapture: ArtifactRecord<OperatorOverrideCaptureArtifact>
  replayPack: ArtifactRecord<RecommendationReplayPack>
  serialValidator: ArtifactRecord<SerialBundleValidatorResult>
  contractCoverage: ArtifactRecord<DashboardPublicContractCoverage>
  promotionGate: ArtifactRecord<GovernedPromotionDisciplineGate>
  declaredArtifactMap: Record<string, ArtifactRecord>
  allArtifacts: ArtifactRecord[]
}

export type SectionState = 'renderable' | 'empty' | 'unavailable' | 'incomplete' | 'incomplete_publication' | 'stale' | 'truth_violation'

export type SectionInput<T> = {
  state: SectionState
  title: string
  data: T | null
  reason?: string
  provenance: Array<{ artifact: string; path: string; keyFields: string[]; timestamp?: string; provenanceConfidence?: 'high' | 'low' }>
}

export type DashboardPanelSurface = {
  panelId: string
  title: string
  status: 'renderable' | 'blocked'
  summary: string
  rows: Array<Array<string>>
  blockedReason?: string
}

export type DashboardViewModel = {
  state: {
    kind: RenderStateKind
    reason: string
    missingArtifacts: string[]
    staleArtifacts: string[]
    truthViolationReasons: string[]
  }
  repoName: string
  freshness: { status: 'Fresh' | 'Stale' | 'Unknown'; lastRefresh: string; note: string }
  integrity: {
    manifestCompleteness: string
    publicationState: string
    syncAuditState: string
    declaredCount: number
    loadedCount: number
    validLoadedCount: number
  }
  recommendation: {
    title: string
    reason: string
    confidence: 'High' | 'Medium' | 'Low'
    sourceBasis: string
    why: string[]
    whatChanges: string[]
    provenance: Array<{ artifact: string; path: string; keyFields: string[]; timestamp?: string; provenanceConfidence?: 'high' | 'low' }>
    synthesizedFallback: boolean
  }
  comparison: Record<string, string>
  topology: Array<{ node: string; status: 'online' | 'missing' | 'degraded'; provenance: string }>
  artifactExplorer: Array<{ family: string; name: string; path: string; status: ExplorerCoverageStatus }>
  reviewQueue: Array<{ kind: 'warn' | 'freeze' | 'require_human_review' | 'governance_exception'; reason: string }>
  healthScorecards: Array<{ family: string; score: number; grade: string; rule: string }>
  sections: {
    snapshot: SectionInput<Snapshot>
    bottleneck: SectionInput<BottleneckRecord>
    drift: SectionInput<DriftRecord>
    hardGate: SectionInput<HardGateState>
    runState: SectionInput<RunState>
    deferred: SectionInput<{ items: DeferredItem[]; readiness: DeferredReadiness[] }>
    constitutional: SectionInput<ConstitutionResult>
  }
  provenance: Array<{ name: string; path: string; status: string; timestamp?: string; keysUsed: string[]; provenanceConfidence?: 'high' | 'low' }>
  trends: Array<{ label: string; value: string }>
  history: { status: string; entries: string[] }
  operatorPanels: DashboardPanelSurface[]
  certificationGate: { status: 'pass' | 'blocked'; reasons: string[] }
}
