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

export type Snapshot = {
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

export type DriftRecord = {
  drift_classification?: string
  trend?: string
  key_signals?: string[]
  short_recommendation?: string
}

export type HardGateState = {
  gate_name?: string
  readiness_status?: string
  required_evidence?: string[]
  falsification_risks?: string[]
}

export type RunState = {
  current_run_status?: string
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

export type DashboardPublication = {
  manifest: ArtifactRecord<Record<string, unknown>>
  snapshot: ArtifactRecord<Snapshot>
  snapshotMeta: ArtifactRecord<SnapshotMeta>
  drift: ArtifactRecord<DriftRecord>
  runState: ArtifactRecord<RunState>
  hardGate: ArtifactRecord<HardGateState>
  bottleneck: ArtifactRecord<BottleneckRecord>
  constitution: ArtifactRecord<ConstitutionResult>
  deferredRegister: ArtifactRecord<{ items?: DeferredItem[] }>
  deferredTracker: ArtifactRecord<{ items?: DeferredReadiness[] }>
  allArtifacts: ArtifactRecord[]
}

export type SectionState = 'renderable' | 'empty' | 'unavailable' | 'incomplete' | 'incomplete_publication' | 'stale' | 'truth_violation'

export type SectionInput<T> = {
  state: SectionState
  title: string
  data: T | null
  reason?: string
  provenance: Array<{ artifact: string; path: string; keyFields: string[]; timestamp?: string }>
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
  integrity: { manifestCompleteness: string; publicationState: string; syncAuditState: string }
  recommendation: {
    title: string
    reason: string
    confidence: 'High' | 'Medium' | 'Low'
    sourceBasis: string
    why: string[]
    whatChanges: string[]
  }
  comparison: Record<string, string>
  topology: Array<{ node: string; status: 'online' | 'missing' | 'degraded'; provenance: string }>
  artifactExplorer: Array<{ family: string; name: string; path: string; status: string }>
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
  provenance: Array<{ name: string; path: string; status: string; timestamp?: string; keysUsed: string[] }>
  trends: Array<{ label: string; value: string }>
  history: { status: string; entries: string[] }
}
