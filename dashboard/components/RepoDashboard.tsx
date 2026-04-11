'use client'

import { useEffect, useMemo, useState, type CSSProperties } from 'react'

type RootCounts = {
  files_total?: number
  runtime_modules?: number
  tests?: number
  contracts_total?: number
  docs?: number
  run_artifacts?: number
}

type RuntimeHotspot = {
  area?: string
  count?: number
  note?: string
}

type OperationalSignal = {
  title?: string
  status?: string
  detail?: string
}

type Snapshot = {
  repo_name?: string
  root_counts?: RootCounts
  runtime_hotspots?: RuntimeHotspot[]
  operational_signals?: OperationalSignal[]
}

type SnapshotMeta = {
  last_refreshed_time?: string
  snapshot_size?: string
  data_source_state?: string
}

type BottleneckRecord = {
  bottleneck_name?: string
  explanation?: string
  impacted_layers?: string[]
  evidence?: string[]
}

type DriftRecord = {
  drift_classification?: string
  trend?: string
  key_signals?: string[]
  short_recommendation?: string
}

type RoadmapState = {
  primary_phase?: string
  secondary_phase?: string
  active_batch?: string
  next_step?: string
}

type MaturityTracker = {
  primary_phase?: string
  secondary_phase?: string
}

type HardGateState = {
  gate_name?: string
  readiness_status?: string
  required_evidence?: string[]
  falsification_risks?: string[]
}

type RunState = {
  current_run_status?: string
  last_successful_cycle?: string
  last_blocked_cycle?: string
  repair_loop_count?: number
  first_pass_quality?: string
}

type DeferredItem = {
  item_id?: string
  item_name?: string
  reason_deferred?: string
  missing_evidence?: string[]
  return_condition?: string
}

type DeferredReadiness = {
  item_id?: string
  readiness_signal?: string
}

type ConstitutionResult = {
  status?: string
  violations?: string[]
  summary?: string
}

type NextAction = {
  title: string
  reason: string
  confidence: 'High' | 'Medium' | 'Low'
  sourceBasis: string
  why: string[]
  whatChanges: string[]
}

type RefreshState = 'Fresh' | 'Stale' | 'Unknown'

type ArtifactLoad = {
  label: string
  loaded: boolean
}

type ArtifactPresence = Record<string, boolean>

const NOT_AVAILABLE = 'Not available yet'
const HISTORY_NOT_AVAILABLE = 'History not available yet'
const NO_DEFERRED_ITEMS = 'No deferred items'
const NO_VIOLATIONS = 'No violations detected'

const pageStyle: CSSProperties = {
  maxWidth: 1040,
  margin: '0 auto',
  padding: '20px 12px 36px'
}

const sectionStyle: CSSProperties = {
  marginTop: 14,
  display: 'grid',
  gap: 12,
  gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))'
}

const cardStyle: CSSProperties = {
  background: '#ffffff',
  border: '1px solid #e2e8f0',
  borderRadius: 14,
  padding: 16,
  boxShadow: '0 1px 2px rgba(15, 23, 42, 0.05)'
}

const prominentCardStyle: CSSProperties = {
  ...cardStyle,
  border: '1px solid #cbd5e1',
  boxShadow: '0 4px 14px rgba(15, 23, 42, 0.08)'
}

function safeArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String).filter((item) => item.trim().length > 0) : []
}

function isUnavailableText(value?: string | null): boolean {
  if (!value) return true
  return value.trim().length === 0 || value.toLowerCase().includes('not available yet') || value.toLowerCase() === 'unknown'
}

function isTruthyStatus(value?: string): boolean {
  if (isUnavailableText(value)) return false
  const normalized = (value ?? '').toLowerCase()
  return ['pass', 'passed', 'ok', 'ready', 'healthy', 'satisfied', 'true', 'good'].some((token) => normalized.includes(token))
}

function isBlockedStatus(value?: string): boolean {
  const normalized = (value ?? '').toLowerCase()
  return ['block', 'repair', 'fail', 'stuck', 'degraded', 'risk'].some((token) => normalized.includes(token))
}

function statusTone(value: string): { color: string; border: string; bg: string } {
  const v = value.toLowerCase()
  if (v.includes('at risk')) return { color: '#b91c1c', border: '#fecaca', bg: '#fef2f2' }
  if (v.includes('watch')) return { color: '#92400e', border: '#fde68a', bg: '#fffbeb' }
  if (v.includes('good') || v.includes('healthy') || v.includes('fresh')) return { color: '#166534', border: '#bbf7d0', bg: '#f0fdf4' }
  if (v.includes('fallback') || v.includes('stale')) return { color: '#92400e', border: '#fde68a', bg: '#fffbeb' }
  return { color: '#475569', border: '#cbd5e1', bg: '#f8fafc' }
}

function Field({ label, value }: { label: string; value?: string | number | null }) {
  const rendered = typeof value === 'string' && isUnavailableText(value) ? NOT_AVAILABLE : value
  return (
    <div style={{ marginTop: 8 }}>
      <p style={{ margin: 0, fontSize: 12, color: '#64748b', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.3 }}>{label}</p>
      <p style={{ margin: '2px 0 0', fontSize: 15, color: '#0f172a' }}>{rendered ?? NOT_AVAILABLE}</p>
    </div>
  )
}

function StringList({ items, emptyText = NOT_AVAILABLE }: { items: string[]; emptyText?: string }) {
  if (!items.length) {
    return <p style={{ margin: '6px 0 0', color: '#64748b', fontSize: 14 }}>{emptyText}</p>
  }

  return (
    <ul style={{ margin: '8px 0 0', paddingLeft: 18, color: '#1e293b' }}>
      {items.map((item, index) => (
        <li key={`${item}-${index}`} style={{ marginBottom: 4, fontSize: 14 }}>
          {item}
        </li>
      ))}
    </ul>
  )
}

function compareText(current?: string, previous?: string, labels?: { up: string; down: string; equal: string }): string {
  if (!current || !previous || isUnavailableText(current) || isUnavailableText(previous)) return HISTORY_NOT_AVAILABLE
  if (current === previous) return labels?.equal ?? 'Unchanged'

  const parseTrend = (value: string) => {
    const lower = value.toLowerCase()
    if (lower.includes('improv') || lower.includes('decreas') || lower.includes('down')) return -1
    if (lower.includes('worse') || lower.includes('increas') || lower.includes('up')) return 1
    return 0
  }

  const delta = parseTrend(current) - parseTrend(previous)
  if (delta > 0) return labels?.up ?? 'Increased'
  if (delta < 0) return labels?.down ?? 'Decreased'
  return labels?.equal ?? 'Changed'
}

function deriveRefreshState(meta: SnapshotMeta | null): { state: RefreshState; stalenessNote: string } {
  if (!meta) return { state: 'Unknown', stalenessNote: 'Snapshot metadata not available.' }

  const source = (meta.data_source_state ?? '').toLowerCase()
  if (source.includes('fallback')) return { state: 'Unknown', stalenessNote: 'Invalid source state: fallback is not allowed.' }

  if (isUnavailableText(meta.last_refreshed_time)) {
    return { state: 'Unknown', stalenessNote: 'Refresh timestamp not available.' }
  }

  const refreshedAt = Date.parse(meta.last_refreshed_time ?? '')
  if (Number.isNaN(refreshedAt)) {
    return { state: 'Unknown', stalenessNote: 'Refresh timestamp format is not parseable.' }
  }

  const ageHours = (Date.now() - refreshedAt) / (1000 * 60 * 60)
  if (ageHours > 6) return { state: 'Stale', stalenessNote: `Snapshot age is ${Math.floor(ageHours)}h.` }
  return { state: 'Fresh', stalenessNote: `Snapshot age is ${Math.max(0, Math.floor(ageHours))}h.` }
}

export default function RepoDashboard() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [snapshotMeta, setSnapshotMeta] = useState<SnapshotMeta | null>(null)
  const [bottleneck, setBottleneck] = useState<BottleneckRecord | null>(null)
  const [drift, setDrift] = useState<DriftRecord | null>(null)
  const [previousDrift, setPreviousDrift] = useState<DriftRecord | null>(null)
  const [roadmapState, setRoadmapState] = useState<RoadmapState | null>(null)
  const [maturityState, setMaturityState] = useState<MaturityTracker | null>(null)
  const [hardGate, setHardGate] = useState<HardGateState | null>(null)
  const [previousHardGate, setPreviousHardGate] = useState<HardGateState | null>(null)
  const [runState, setRunState] = useState<RunState | null>(null)
  const [previousRunState, setPreviousRunState] = useState<RunState | null>(null)
  const [deferredItems, setDeferredItems] = useState<DeferredItem[]>([])
  const [deferredTracker, setDeferredTracker] = useState<DeferredReadiness[]>([])
  const [constitutionDrift, setConstitutionDrift] = useState<ConstitutionResult | null>(null)
  const [roadmapAlignment, setRoadmapAlignment] = useState<ConstitutionResult | null>(null)
  const [serialBundle, setSerialBundle] = useState<ConstitutionResult | null>(null)
  const [artifactPresence, setArtifactPresence] = useState<ArtifactPresence>({})

  useEffect(() => {
    let cancelled = false

    const retrieveArtifact = async <T,>(path: string): Promise<{ data: T | null; loaded: boolean }> => {
      try {
        const response = await fetch(path)
        if (!response.ok) return { data: null, loaded: false }
        return { data: (await response.json()) as T, loaded: true }
      } catch {
        return { data: null, loaded: false }
      }
    }

    const retrieveAll = async () => {
      const presence: ArtifactPresence = {}

      const snapshotData = await retrieveArtifact<Snapshot>('/repo_snapshot.json')
      presence.repo_snapshot = snapshotData.loaded
      if (!cancelled) setSnapshot(snapshotData.data)

      const snapshotMetaData = await retrieveArtifact<SnapshotMeta>('/repo_snapshot_meta.json')
      presence.repo_snapshot_meta = snapshotMetaData.loaded
      if (!cancelled) setSnapshotMeta(snapshotMetaData.data)

      const loaders = await Promise.all([
        retrieveArtifact<BottleneckRecord>('/current_bottleneck_record.json'),
        retrieveArtifact<DriftRecord>('/drift_trend_continuity_artifact.json'),
        retrieveArtifact<DriftRecord>('/prior_drift_trend_continuity_artifact.json'),
        retrieveArtifact<RoadmapState>('/canonical_roadmap_state_artifact.json'),
        retrieveArtifact<MaturityTracker>('/maturity_phase_tracker.json'),
        retrieveArtifact<HardGateState>('/hard_gate_status_record.json'),
        retrieveArtifact<HardGateState>('/prior_hard_gate_status_record.json'),
        retrieveArtifact<RunState>('/current_run_state_record.json'),
        retrieveArtifact<RunState>('/prior_current_run_state_record.json'),
        retrieveArtifact<{ items?: DeferredItem[] }>('/deferred_item_register.json'),
        retrieveArtifact<{ items?: DeferredReadiness[] }>('/deferred_return_tracker.json'),
        retrieveArtifact<ConstitutionResult>('/constitutional_drift_checker_result.json'),
        retrieveArtifact<ConstitutionResult>('/roadmap_alignment_validator_result.json'),
        retrieveArtifact<ConstitutionResult>('/serial_bundle_validator_result.json')
      ])

      if (!cancelled) {
        presence.current_bottleneck_record = loaders[0].loaded
        setBottleneck(loaders[0].data)
        presence.drift_trend_continuity = loaders[1].loaded
        setDrift(loaders[1].data)
        setPreviousDrift(loaders[2].data)
        setRoadmapState(loaders[3].data)
        setMaturityState(loaders[4].data)
        presence.hard_gate_status = loaders[5].loaded
        setHardGate(loaders[5].data)
        setPreviousHardGate(loaders[6].data)
        presence.current_run_state = loaders[7].loaded
        setRunState(loaders[7].data)
        setPreviousRunState(loaders[8].data)
        presence.deferred_item_register = loaders[9].loaded
        setDeferredItems(Array.isArray(loaders[9].data?.items) ? loaders[9].data.items : [])
        presence.deferred_return_tracker = loaders[10].loaded
        setDeferredTracker(Array.isArray(loaders[10].data?.items) ? loaders[10].data.items : [])
        presence.constitutional_drift_checker = loaders[11].loaded
        setConstitutionDrift(loaders[11].data)
        presence.roadmap_alignment_validator = loaders[12].loaded
        setRoadmapAlignment(loaders[12].data)
        presence.serial_bundle_validator = loaders[13].loaded
        setSerialBundle(loaders[13].data)
      }

      if (!cancelled) setArtifactPresence(presence)
    }

    retrieveAll()

    return () => {
      cancelled = true
    }
  }, [])

  const counts = useMemo(() => snapshot?.root_counts ?? {}, [snapshot?.root_counts])

  const deferredSignalById = useMemo(() => {
    const map = new Map<string, string>()
    deferredTracker.forEach((item) => {
      if (item.item_id) map.set(item.item_id, item.readiness_signal ?? NOT_AVAILABLE)
    })
    return map
  }, [deferredTracker])

  const constitutionPanels = useMemo(
    () => [
      { title: 'Drift checker', payload: constitutionDrift },
      { title: 'Alignment validator', payload: roadmapAlignment },
      { title: 'Serial bundle validator', payload: serialBundle }
    ],
    [constitutionDrift, roadmapAlignment, serialBundle]
  )

  const artifactLoads = useMemo<ArtifactLoad[]>(
    () => [
      { label: 'repo_snapshot', loaded: artifactPresence.repo_snapshot ?? !!snapshot },
      { label: 'repo_snapshot_meta', loaded: artifactPresence.repo_snapshot_meta ?? !!snapshotMeta },
      { label: 'current_bottleneck_record', loaded: artifactPresence.current_bottleneck_record ?? !!bottleneck },
      { label: 'drift_trend_continuity', loaded: artifactPresence.drift_trend_continuity ?? !!drift },
      { label: 'hard_gate_status', loaded: artifactPresence.hard_gate_status ?? !!hardGate },
      { label: 'current_run_state', loaded: artifactPresence.current_run_state ?? !!runState },
      { label: 'deferred_item_register', loaded: artifactPresence.deferred_item_register ?? false },
      { label: 'deferred_return_tracker', loaded: artifactPresence.deferred_return_tracker ?? false },
      { label: 'constitutional_drift_checker', loaded: artifactPresence.constitutional_drift_checker ?? !!constitutionDrift },
      { label: 'roadmap_alignment_validator', loaded: artifactPresence.roadmap_alignment_validator ?? !!roadmapAlignment },
      { label: 'serial_bundle_validator', loaded: artifactPresence.serial_bundle_validator ?? !!serialBundle }
    ],
    [snapshot, snapshotMeta, bottleneck, drift, hardGate, runState, constitutionDrift, roadmapAlignment, serialBundle, artifactPresence]
  )

  const refresh = useMemo(() => deriveRefreshState(snapshotMeta), [snapshotMeta])

  const hardGateUnsatisfied = useMemo(() => {
    if (!hardGate?.gate_name || isUnavailableText(hardGate.gate_name)) return false
    return !isTruthyStatus(hardGate?.readiness_status)
  }, [hardGate])

  const constitutionViolations = useMemo(
    () =>
      constitutionPanels.some(({ payload }) => {
        const violations = safeArray(payload?.violations)
        return violations.length > 0 || isBlockedStatus(payload?.status)
      }),
    [constitutionPanels]
  )

  const driftWorsening = useMemo(() => {
    const trend = (drift?.trend ?? '').toLowerCase()
    const classification = (drift?.drift_classification ?? '').toLowerCase()
    return trend.includes('worsen') || trend.includes('up') || (classification.includes('moderate') && trend.includes('increase')) || classification.includes('high')
  }, [drift])

  const runBlocked = useMemo(() => isBlockedStatus(runState?.current_run_status), [runState])
  const staleData = refresh.state === 'Stale'

  const keyMissingForGuidance = useMemo(() => {
    const critical = [hardGate, runState, drift, bottleneck]
    return critical.filter((item) => !item).length >= 2
  }, [hardGate, runState, drift, bottleneck])

  const topWarnings = useMemo(() => {
    const warnings: string[] = []
    if (hardGateUnsatisfied) warnings.push('Hard gate unsatisfied.')
    if (driftWorsening) warnings.push('Drift trend is worsening.')
    if (runBlocked) warnings.push('Last run is blocked or in repair-needed state.')
    if (constitutionViolations) warnings.push('Constitutional alignment warning detected.')
    if (!snapshot) warnings.push('Repository snapshot artifact is missing.')
    if (staleData) warnings.push('Snapshot appears stale.')
    if (keyMissingForGuidance) warnings.push('Key artifacts are missing; recommendation quality is degraded.')
    return warnings
  }, [hardGateUnsatisfied, driftWorsening, runBlocked, constitutionViolations, snapshot, staleData, keyMissingForGuidance])

  const showWarningBanner = topWarnings.length > 0

  const truthViolation = useMemo(() => {
    if (!snapshot || !snapshotMeta) return true
    if ((snapshotMeta.data_source_state ?? '').toLowerCase() !== 'live') return true
    const missingCritical = artifactLoads
      .filter((item) => ['hard_gate_status', 'current_run_state', 'drift_trend_continuity', 'current_bottleneck_record'].includes(item.label))
      .some((item) => !item.loaded)
    if (missingCritical) return true
    if (refresh.state === 'Stale') return true
    return false
  }, [snapshot, snapshotMeta, artifactLoads, refresh.state])

  const nextAction = useMemo<NextAction>(() => {
    if (truthViolation) {
      return {
        title: 'No recommendation: fail-closed truth gate active',
        reason: 'Critical artifacts are missing, stale, or not live-backed. Retrieve fresh governed artifacts before action.',
        confidence: 'Low',
        sourceBasis: 'truth gate',
        why: ['Dashboard cannot imply correctness without evidence.', 'Fail-closed mode blocks action guidance under truth violation.'],
        whatChanges: ['Required live artifacts are available and complete.', 'Freshness gate passes with current timestamps.']
      }
    }

    if (hardGateUnsatisfied) {
      const evidence = safeArray(hardGate?.required_evidence)[0]
      return {
        title: `Satisfy hard gate: ${hardGate?.gate_name ?? 'active gate'}`,
        reason: evidence ? `Missing evidence: ${evidence}` : 'Hard gate readiness is not yet satisfied.',
        confidence: 'High',
        sourceBasis: 'hard gate',
        why: ['Hard gate is unsatisfied in current artifact state.', 'Promotion requires certification before expansion.'],
        whatChanges: ['Hard gate is satisfied with required evidence.', 'Control integrity returns to Good.']
      }
    }

    if (runBlocked) {
      return {
        title: `Run bounded repair for ${bottleneck?.bottleneck_name ?? 'best available target'}`,
        reason: `Current run state is ${runState?.current_run_status ?? 'blocked'} and requires recovery.`,
        confidence: 'High',
        sourceBasis: 'run state',
        why: ['Current run status indicates blocked or repair-needed execution.', 'Repair loop pressure should be reduced before advancing.'],
        whatChanges: ['Run state clears from blocked/repair-needed.', 'Repair loop pressure stabilizes.']
      }
    }

    if (bottleneck?.bottleneck_name && !isUnavailableText(bottleneck.bottleneck_name)) {
      return {
        title: `Address bottleneck: ${bottleneck.bottleneck_name}`,
        reason: bottleneck.explanation ?? 'Clear bottleneck evidence exists in current artifacts.',
        confidence: keyMissingForGuidance ? 'Low' : 'Medium',
        sourceBasis: 'bottleneck',
        why: ['A current bottleneck is explicitly identified.', 'Reducing bottleneck pressure improves execution integrity.'],
        whatChanges: ['A new bottleneck becomes primary.', 'Run state changes to blocked and requires repair first.']
      }
    }

    const readyDeferred = deferredItems.find((item) => {
      const signal = (item.item_id ? deferredSignalById.get(item.item_id) : '').toLowerCase()
      return signal.includes('ready') || signal.includes('revisit') || signal.includes('go')
    })

    if (readyDeferred) {
      return {
        title: `Revisit deferred item: ${readyDeferred.item_name ?? readyDeferred.item_id ?? 'deferred item'}`,
        reason: 'Deferred readiness signal indicates near-term re-entry potential.',
        confidence: keyMissingForGuidance ? 'Low' : 'Medium',
        sourceBasis: 'deferred readiness',
        why: ['Deferred tracker indicates a near-actionable item.', 'Return conditions are closest for this item.'],
        whatChanges: ['Readiness signal weakens or missing evidence grows.', 'Higher-priority gate/run blocking appears.']
      }
    }

    return {
      title: 'Run next governed execution cycle',
      reason: 'No explicit blocking gate, blocked run, or actionable deferred target is present.',
      confidence: keyMissingForGuidance ? 'Low' : 'Medium',
      sourceBasis: 'run state / drift / roadmap state',
      why: ['Current view does not show a stronger immediate blocker.', 'A governed cycle refreshes evidence and state.'],
      whatChanges: ['Hard gate becomes unsatisfied.', 'Run state becomes blocked or bottleneck clarity increases.']
    }
  }, [truthViolation, hardGateUnsatisfied, hardGate, runBlocked, runState, bottleneck, deferredItems, deferredSignalById, keyMissingForGuidance])

  const completeness = useMemo(() => {
    const loaded = artifactLoads.filter((item) => item.loaded).map((item) => item.label)
    const missing = artifactLoads.filter((item) => !item.loaded).map((item) => item.label)
    return {
      loaded,
      missing,
      degraded: missing.some((label) => ['hard_gate_status', 'current_run_state', 'drift_trend_continuity', 'current_bottleneck_record'].includes(label))
    }
  }, [artifactLoads])

  const integritySummary = useMemo(() => {
    const executionIntegrity = runBlocked ? 'At Risk' : runState ? 'Good' : 'Unknown'
    const reviewIntegrity = constitutionPanels.some(({ payload }) => payload) ? (constitutionViolations ? 'At Risk' : 'Good') : 'Unknown'
    const controlIntegrity = hardGateUnsatisfied || driftWorsening ? 'Watch' : hardGate ? 'Good' : 'Unknown'
    const constitutionalIntegrity = constitutionViolations ? 'At Risk' : constitutionPanels.some(({ payload }) => payload) ? 'Good' : 'Unknown'
    return { executionIntegrity, reviewIntegrity, controlIntegrity, constitutionalIntegrity }
  }, [runBlocked, runState, constitutionPanels, constitutionViolations, hardGateUnsatisfied, driftWorsening, hardGate])

  const changeSummary = useMemo(
    () => ({
      bottleneck:
        bottleneck?.bottleneck_name && previousDrift
          ? 'Changed / check prior bottleneck artifact'
          : HISTORY_NOT_AVAILABLE,
      drift: compareText(drift?.trend, previousDrift?.trend, { up: 'Worsened', down: 'Improved', equal: 'Stable' }),
      repairLoops:
        typeof runState?.repair_loop_count === 'number' && typeof previousRunState?.repair_loop_count === 'number'
          ? runState.repair_loop_count > previousRunState.repair_loop_count
            ? 'Increased'
            : runState.repair_loop_count < previousRunState.repair_loop_count
              ? 'Decreased'
              : 'Unchanged'
          : HISTORY_NOT_AVAILABLE,
      hardGate: compareText(hardGate?.readiness_status, previousHardGate?.readiness_status, { equal: 'Unchanged', up: 'Changed', down: 'Changed' }),
      deferredReadiness: deferredTracker.length ? 'Current readiness available; prior comparison not available.' : HISTORY_NOT_AVAILABLE
    }),
    [bottleneck?.bottleneck_name, previousDrift, drift?.trend, runState?.repair_loop_count, previousRunState?.repair_loop_count, hardGate?.readiness_status, previousHardGate?.readiness_status, deferredTracker.length]
  )

  const criticalPath = useMemo(() => {
    if (hardGateUnsatisfied) return ['Satisfy hard gate', 'Address active bottleneck', 'Run next governed cycle', 'Review outcome artifacts']
    if (runBlocked) return ['Run bounded repair', 'Stabilize run state', 'Run next governed cycle', 'Review outcome artifacts']
    if (bottleneck?.bottleneck_name && !isUnavailableText(bottleneck.bottleneck_name)) return ['Address bottleneck', 'Run next governed cycle', 'Review outcome artifacts']
    return ['Run next governed cycle', 'Review outcome artifacts', 'Tune based on new evidence']
  }, [hardGateUnsatisfied, runBlocked, bottleneck?.bottleneck_name])

  const deferredReactivation = useMemo(() => {
    const candidates = deferredItems.map((item) => {
      const signal = item.item_id ? deferredSignalById.get(item.item_id) ?? NOT_AVAILABLE : NOT_AVAILABLE
      const normalized = signal.toLowerCase()
      const score = normalized.includes('ready') ? 3 : normalized.includes('revisit') || normalized.includes('soon') ? 2 : 1
      return { item, signal, score }
    })

    return candidates.sort((a, b) => b.score - a.score).slice(0, 3)
  }, [deferredItems, deferredSignalById])

  const trendStrip = useMemo(() => {
    const driftTrend = isUnavailableText(drift?.trend) ? 'Unknown' : drift?.trend
    const repairTrend =
      typeof runState?.repair_loop_count === 'number' && typeof previousRunState?.repair_loop_count === 'number'
        ? runState.repair_loop_count > previousRunState.repair_loop_count
          ? 'up'
          : runState.repair_loop_count < previousRunState.repair_loop_count
            ? 'down'
            : 'unchanged'
        : 'Unknown'
    const fpq = isUnavailableText(runState?.first_pass_quality) ? 'Unknown' : runState?.first_pass_quality
    const bottleneckStability = previousDrift ? 'check change card' : 'Not available yet'

    return [`Drift: ${driftTrend ?? 'Unknown'}`, `Repair loops: ${repairTrend}`, `First-pass quality: ${fpq ?? 'Unknown'}`, `Bottleneck stability: ${bottleneckStability}`]
  }, [drift?.trend, runState?.repair_loop_count, previousRunState?.repair_loop_count, runState?.first_pass_quality, previousDrift])

  const caveats = useMemo(() => {
    const items: string[] = []
    if (completeness.degraded) items.push('Recommendations are partially degraded due to missing key artifacts.')
    if (truthViolation) items.push('Fail-closed truth gate is active until live artifact completeness is restored.')
    if (Object.values(changeSummary).every((value) => value === HISTORY_NOT_AVAILABLE)) items.push('Comparison history is not available yet.')
    if (nextAction.confidence === 'Low') items.push('Confidence is reduced due to incomplete or inferred evidence.')
    return items
  }, [completeness.degraded, truthViolation, changeSummary, nextAction.confidence])

  const readinessToExpand = useMemo(() => {
    if (truthViolation) return 'Unknown'
    if (hardGateUnsatisfied || constitutionViolations || runBlocked) return 'Tune instead'
    if (driftWorsening || nextAction.confidence === 'Low') return 'Validate with another run'
    return 'Ready for bounded expansion'
  }, [truthViolation, hardGateUnsatisfied, constitutionViolations, runBlocked, driftWorsening, nextAction.confidence])

  const systemMap = useMemo(
    () => [
      { name: 'RIL', status: artifactPresence.repo_snapshot ? 'online' : 'missing', provenance: '/repo_snapshot.json' },
      { name: 'CDE', status: artifactPresence.current_bottleneck_record ? 'online' : 'missing', provenance: '/current_bottleneck_record.json' },
      { name: 'TLC', status: artifactPresence.current_run_state ? 'online' : 'missing', provenance: '/current_run_state_record.json' },
      { name: 'PQX', status: artifactPresence.serial_bundle_validator ? 'online' : 'missing', provenance: '/serial_bundle_validator_result.json' },
      { name: 'FRE', status: artifactPresence.drift_trend_continuity ? 'online' : 'missing', provenance: '/drift_trend_continuity_artifact.json' },
      { name: 'SEL', status: artifactPresence.hard_gate_status ? 'online' : 'missing', provenance: '/hard_gate_status_record.json' },
      { name: 'PRG', status: artifactPresence.roadmap_alignment_validator ? 'online' : 'missing', provenance: '/roadmap_alignment_validator_result.json' }
    ],
    [artifactPresence]
  )

  return (
    <main style={pageStyle}>
      <header style={{ marginBottom: 10 }}>
        <h1 style={{ margin: 0, fontSize: 30, lineHeight: 1.15 }}>Operator Control Surface</h1>
        <p style={{ margin: '8px 0 0', color: '#475569', fontSize: 15 }}>
          Live governed execution view for <strong>{snapshot?.repo_name ?? NOT_AVAILABLE}</strong>. Focus on what matters now, what to do next, and artifact integrity.
        </p>
      </header>

      {truthViolation ? (
        <section style={{ ...cardStyle, border: '1px solid #dc2626', background: '#fef2f2', marginTop: 12 }}>
          <h2 style={{ margin: 0, fontSize: 16, color: '#991b1b' }}>Fail-closed mode</h2>
          <p style={{ margin: '8px 0 0', color: '#7f1d1d' }}>Truth violation detected. Dashboard guidance is intentionally degraded until live artifact integrity is restored.</p>
        </section>
      ) : null}

      {showWarningBanner ? (
        <section style={{ ...cardStyle, border: '1px solid #fecaca', background: '#fff7f7', marginTop: 12 }}>
          <h2 style={{ margin: 0, fontSize: 16, color: '#991b1b' }}>Operator warning</h2>
          <StringList items={topWarnings} />
        </section>
      ) : null}

      <section style={{ ...sectionStyle, gridTemplateColumns: '1fr', marginTop: 12 }}>
        <article style={prominentCardStyle}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
            <h2 style={{ margin: 0, fontSize: 18 }}>Next Action</h2>
            <span style={{ padding: '4px 10px', borderRadius: 999, border: `1px solid ${statusTone(refresh.state).border}`, background: statusTone(refresh.state).bg, color: statusTone(refresh.state).color, fontSize: 12, fontWeight: 700 }}>
              Refresh: {refresh.state}
            </span>
            <span style={{ padding: '4px 10px', borderRadius: 999, border: '1px solid #cbd5e1', fontSize: 12, color: '#475569' }}>{refresh.stalenessNote}</span>
          </div>
          <p style={{ margin: '10px 0 0', fontSize: 20, fontWeight: 700, color: '#0f172a' }}>{nextAction.title}</p>
          <p style={{ margin: '6px 0 0', color: '#334155' }}>{nextAction.reason}</p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 12 }}>
            <span style={{ padding: '4px 10px', borderRadius: 999, border: '1px solid #cbd5e1', fontSize: 12, fontWeight: 600 }}>Confidence: {nextAction.confidence}</span>
            <span style={{ padding: '4px 10px', borderRadius: 999, border: '1px solid #cbd5e1', fontSize: 12, color: '#475569' }}>Source basis: {nextAction.sourceBasis}</span>
          </div>
          <Field label='Why this action?' value='' />
          <StringList items={nextAction.why} />
          <Field label='What would change this recommendation?' value='' />
          <StringList items={nextAction.whatChanges} />
        </article>
      </section>

      <section style={sectionStyle}>
        <article style={cardStyle}>
          <h2 style={{ margin: 0, fontSize: 17 }}>Canonical system map</h2>
          {systemMap.map((node) => (
            <div key={node.name} style={{ marginTop: 10, display: 'flex', justifyContent: 'space-between', gap: 10 }}>
              <span style={{ fontWeight: 700 }}>{node.name}</span>
              <span style={{ color: node.status === 'online' ? '#166534' : '#b91c1c' }}>{node.status}</span>
              <span style={{ color: '#64748b', fontSize: 12 }}>{node.provenance}</span>
            </div>
          ))}
        </article>

        <article style={cardStyle}>
          <h2 style={{ margin: 0, fontSize: 17 }}>Trend strip</h2>
          <StringList items={trendStrip} emptyText={NOT_AVAILABLE} />
        </article>
        <article style={cardStyle}>
          <h2 style={{ margin: 0, fontSize: 17 }}>Top warnings</h2>
          <StringList items={topWarnings} emptyText='No active warnings.' />
        </article>
      </section>

      <section style={sectionStyle}>
        <article style={cardStyle}>
          <h2 style={{ margin: 0, fontSize: 17 }}>System integrity summary</h2>
          {[
            ['Execution integrity', integritySummary.executionIntegrity],
            ['Review integrity', integritySummary.reviewIntegrity],
            ['Control integrity', integritySummary.controlIntegrity],
            ['Constitutional integrity', integritySummary.constitutionalIntegrity]
          ].map(([label, value]) => {
            const tone = statusTone(value)
            return (
              <div key={label} style={{ marginTop: 10, display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'center' }}>
                <span style={{ color: '#334155', fontSize: 14 }}>{label}</span>
                <span style={{ color: tone.color, border: `1px solid ${tone.border}`, background: tone.bg, borderRadius: 999, padding: '3px 10px', fontSize: 12, fontWeight: 600 }}>{value}</span>
              </div>
            )
          })}
        </article>

        <article style={cardStyle}>
          <h2 style={{ margin: 0, fontSize: 17 }}>Data completeness</h2>
          <Field label='Recommendation quality' value={completeness.degraded ? 'Degraded' : 'Sufficient'} />
          <Field label='Loaded key artifacts' value='' />
          <StringList items={completeness.loaded} />
          <Field label='Missing key artifacts' value='' />
          <StringList items={completeness.missing} emptyText='No key artifacts missing.' />
        </article>
      </section>

      <section style={sectionStyle}>
        <article style={cardStyle}>
          <h2 style={{ margin: 0, fontSize: 17 }}>What changed since last cycle</h2>
          <Field label='Bottleneck' value={changeSummary.bottleneck} />
          <Field label='Drift' value={changeSummary.drift} />
          <Field label='Repair loop pressure' value={changeSummary.repairLoops} />
          <Field label='Hard gate' value={changeSummary.hardGate} />
          <Field label='Deferred readiness' value={changeSummary.deferredReadiness} />
          {Object.values(changeSummary).every((value) => value === HISTORY_NOT_AVAILABLE) ? <p style={{ margin: '10px 0 0', color: '#64748b' }}>{HISTORY_NOT_AVAILABLE}</p> : null}
        </article>

        <article style={cardStyle}>
          <h2 style={{ margin: 0, fontSize: 17 }}>Critical path</h2>
          <ol style={{ margin: '10px 0 0', paddingLeft: 18 }}>
            {criticalPath.map((step, index) => (
              <li key={`${step}-${index}`} style={{ marginBottom: 6, color: '#1e293b' }}>
                {step}
              </li>
            ))}
          </ol>
        </article>
      </section>

      <section style={sectionStyle}>
        <article style={cardStyle}>
          <h2 style={{ margin: 0, fontSize: 17 }}>Decision provenance</h2>
          <Field label='Contributing artifacts' value='' />
          <StringList
            items={[
              'hard_gate_status_record',
              'current_run_state_record',
              'current_bottleneck_record',
              'drift_trend_continuity_artifact',
              'deferred_return_tracker',
              'canonical_roadmap_state_artifact'
            ]}
          />
          <Field label='Contributing system surfaces' value='' />
          <StringList items={['hard gate', 'run state', 'bottleneck', 'drift', 'deferred tracker', 'roadmap state']} />
        </article>

        <article style={cardStyle}>
          <h2 style={{ margin: 0, fontSize: 17 }}>Deferred reactivation</h2>
          {deferredReactivation.length ? (
            deferredReactivation.map(({ item, signal }, index) => (
              <div key={`${item.item_id ?? item.item_name ?? 'deferred'}-${index}`} style={{ marginTop: index === 0 ? 10 : 14, paddingTop: index === 0 ? 0 : 12, borderTop: index === 0 ? 'none' : '1px solid #e2e8f0' }}>
                <p style={{ margin: 0, fontWeight: 700 }}>{item.item_name ?? item.item_id ?? NOT_AVAILABLE}</p>
                <Field label='Readiness signal' value={signal} />
                <Field label='Missing evidence' value='' />
                <StringList items={safeArray(item.missing_evidence)} emptyText={NOT_AVAILABLE} />
                <Field label='Return condition' value={item.return_condition} />
              </div>
            ))
          ) : (
            <p style={{ margin: '8px 0 0', color: '#64748b' }}>No deferred items close to reactivation.</p>
          )}
        </article>
      </section>

      <section style={sectionStyle}>
        <article style={cardStyle}>
          <h2 style={{ margin: 0, fontSize: 17 }}>Readiness to expand</h2>
          <p style={{ margin: '10px 0 0', fontSize: 20, fontWeight: 700 }}>{readinessToExpand}</p>
          <p style={{ margin: '6px 0 0', color: '#475569' }}>
            Conservative recommendation based on drift, hard gate state, run state, constitutional alignment, confidence, and completeness.
          </p>
        </article>

        <article style={cardStyle}>
          <h2 style={{ margin: 0, fontSize: 17 }}>Operator notes / caveats</h2>
          <StringList items={caveats} emptyText='No active caveats.' />
        </article>
      </section>

      <section style={sectionStyle}>
        <article style={cardStyle}>
          <h2 style={{ margin: 0, fontSize: 17 }}>Repository snapshot</h2>
          <Field label='Files' value={counts.files_total ?? 0} />
          <Field label='Runtime modules' value={counts.runtime_modules ?? 0} />
          <Field label='Tests' value={counts.tests ?? 0} />
          <Field label='Contracts' value={counts.contracts_total ?? 0} />
          <Field label='Docs' value={counts.docs ?? 0} />
          <Field label='Run artifacts' value={counts.run_artifacts ?? 0} />
        </article>

        <article style={cardStyle}>
          <h2 style={{ margin: 0, fontSize: 17 }}>Snapshot metadata</h2>
          <Field label='Last refreshed' value={snapshotMeta?.last_refreshed_time} />
          <Field label='Snapshot size' value={snapshotMeta?.snapshot_size} />
          <Field label='Source state' value={snapshotMeta?.data_source_state} />
        </article>
      </section>

      <section style={sectionStyle}>
        <article style={cardStyle}>
          <h2 style={{ margin: 0, fontSize: 17 }}>Bottleneck</h2>
          <p style={{ margin: '8px 0 0', fontSize: 18, fontWeight: 700 }}>{bottleneck?.bottleneck_name ?? NOT_AVAILABLE}</p>
          <Field label='Explanation' value={bottleneck?.explanation} />
          <Field label='Impacted layers' value='' />
          <StringList items={safeArray(bottleneck?.impacted_layers)} />
          <Field label='Evidence' value='' />
          <StringList items={safeArray(bottleneck?.evidence)} />
        </article>

        <article style={cardStyle}>
          <h2 style={{ margin: 0, fontSize: 17 }}>Drift</h2>
          <p style={{ margin: '8px 0 0', fontSize: 18, fontWeight: 700 }}>{drift?.drift_classification ?? NOT_AVAILABLE}</p>
          <Field label='Trend' value={drift?.trend} />
          <Field label='Recommendation' value={drift?.short_recommendation} />
          <Field label='Key signals' value='' />
          <StringList items={safeArray(drift?.key_signals)} />
        </article>
      </section>

      <section style={sectionStyle}>
        <article style={cardStyle}>
          <h2 style={{ margin: 0, fontSize: 17 }}>Roadmap state</h2>
          <Field label='Primary phase' value={roadmapState?.primary_phase ?? maturityState?.primary_phase} />
          <Field label='Secondary phase' value={roadmapState?.secondary_phase ?? maturityState?.secondary_phase} />
          <Field label='Active batch' value={roadmapState?.active_batch} />
          <Field label='Next step' value={roadmapState?.next_step} />
          <Field label='Hard gate reference' value={hardGate?.gate_name} />
        </article>

        <article style={{ ...cardStyle, border: isTruthyStatus(hardGate?.readiness_status) ? '1px solid #bbf7d0' : '1px solid #fecaca' }}>
          <h2 style={{ margin: 0, fontSize: 17 }}>Hard gate</h2>
          <p style={{ margin: '8px 0 0', fontSize: 18, fontWeight: 700 }}>{hardGate?.gate_name ?? NOT_AVAILABLE}</p>
          <Field label='Readiness state' value={hardGate?.readiness_status} />
          <Field label='Required evidence' value='' />
          <StringList items={safeArray(hardGate?.required_evidence)} />
          <Field label='Falsification risks' value='' />
          <StringList items={safeArray(hardGate?.falsification_risks)} />
        </article>
      </section>

      <section style={sectionStyle}>
        <article style={cardStyle}>
          <h2 style={{ margin: 0, fontSize: 17 }}>Run state</h2>
          <p style={{ margin: '8px 0 0', fontSize: 18, fontWeight: 700 }}>{runState?.current_run_status ?? NOT_AVAILABLE}</p>
          <Field label='Last success' value={runState?.last_successful_cycle} />
          <Field label='Last blocked' value={runState?.last_blocked_cycle} />
          <Field label='Repair loop count' value={runState?.repair_loop_count} />
          <Field label='First-pass quality' value={runState?.first_pass_quality} />
        </article>

        <article style={cardStyle}>
          <h2 style={{ margin: 0, fontSize: 17 }}>Deferred items</h2>
          {deferredItems.length ? (
            deferredItems.map((item, index) => (
              <div key={`${item.item_id ?? item.item_name ?? 'deferred'}-${index}`} style={{ marginTop: index === 0 ? 10 : 14, paddingTop: index === 0 ? 0 : 12, borderTop: index === 0 ? 'none' : '1px solid #e2e8f0' }}>
                <p style={{ margin: 0, fontWeight: 700 }}>{item.item_name ?? item.item_id ?? NOT_AVAILABLE}</p>
                <Field label='Reason deferred' value={item.reason_deferred} />
                <Field label='Missing evidence' value='' />
                <StringList items={safeArray(item.missing_evidence)} />
                <Field label='Return condition' value={item.return_condition} />
                <Field label='Readiness signal' value={item.item_id ? deferredSignalById.get(item.item_id) : NOT_AVAILABLE} />
              </div>
            ))
          ) : (
            <p style={{ margin: '8px 0 0', color: '#64748b' }}>{NO_DEFERRED_ITEMS}</p>
          )}
        </article>
      </section>

      <section style={sectionStyle}>
        <article style={cardStyle}>
          <h2 style={{ margin: 0, fontSize: 17 }}>Constitutional alignment</h2>
          <div style={{ display: 'grid', gap: 10, marginTop: 10 }}>
            {constitutionPanels.map(({ title, payload }) => {
              const violations = safeArray(payload?.violations)
              const hasViolation = violations.length > 0 || isBlockedStatus(payload?.status)

              return (
                <div key={title} style={{ border: `1px solid ${hasViolation ? '#fecaca' : '#e2e8f0'}`, borderRadius: 12, padding: 12, background: hasViolation ? '#fef2f2' : '#ffffff' }}>
                  <p style={{ margin: 0, fontWeight: 700 }}>{title}</p>
                  <Field label='Result' value={payload?.status} />
                  <Field label='Summary' value={payload?.summary} />
                  <Field label='Violations' value='' />
                  <StringList items={violations} emptyText={NO_VIOLATIONS} />
                </div>
              )
            })}
          </div>
        </article>

        <article style={cardStyle}>
          <h2 style={{ margin: 0, fontSize: 17 }}>Runtime hotspots</h2>
          {snapshot.runtime_hotspots?.length ? (
            snapshot.runtime_hotspots.map((hotspot, index) => (
              <div key={`${hotspot.area ?? 'hotspot'}-${index}`} style={{ marginTop: index === 0 ? 10 : 14, paddingTop: index === 0 ? 0 : 12, borderTop: index === 0 ? 'none' : '1px solid #e2e8f0' }}>
                <Field label='Area' value={hotspot.area} />
                <Field label='Count' value={hotspot.count} />
                <Field label='Note' value={hotspot.note} />
              </div>
            ))
          ) : (
            <p style={{ margin: '8px 0 0', color: '#64748b' }}>{NOT_AVAILABLE}</p>
          )}
        </article>
      </section>

      <section style={sectionStyle}>
        <article style={cardStyle}>
          <h2 style={{ margin: 0, fontSize: 17 }}>Operational signals</h2>
          {snapshot.operational_signals?.length ? (
            snapshot.operational_signals.map((signal, index) => (
              <div key={`${signal.title ?? 'signal'}-${index}`} style={{ marginTop: index === 0 ? 10 : 14, paddingTop: index === 0 ? 0 : 12, borderTop: index === 0 ? 'none' : '1px solid #e2e8f0' }}>
                <Field label='Title' value={signal.title} />
                <Field label='Status' value={signal.status} />
                <Field label='Detail' value={signal.detail} />
              </div>
            ))
          ) : (
            <p style={{ margin: '8px 0 0', color: '#64748b' }}>{NOT_AVAILABLE}</p>
          )}
        </article>
      </section>
    </main>
  )
}
