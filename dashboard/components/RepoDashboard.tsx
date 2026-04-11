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
}

const fallbackSnapshot: Snapshot = {
  repo_name: 'spectrum-systems',
  root_counts: {
    files_total: 0,
    runtime_modules: 0,
    tests: 0,
    contracts_total: 0,
    docs: 0,
    run_artifacts: 0
  },
  runtime_hotspots: [],
  operational_signals: []
}

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
  return Array.isArray(value) ? value.map(String) : []
}

function isTruthyStatus(value?: string): boolean {
  const normalized = (value ?? '').toLowerCase()
  return ['pass', 'passed', 'ok', 'ready', 'healthy', 'satisfied', 'true'].some((token) => normalized.includes(token))
}

function isBlockedStatus(value?: string): boolean {
  const normalized = (value ?? '').toLowerCase()
  return ['block', 'repair', 'fail', 'stuck', 'degraded'].some((token) => normalized.includes(token))
}

function statusTone(value: string): { color: string; border: string; bg: string } {
  const v = value.toLowerCase()
  if (v.includes('at risk')) return { color: '#b91c1c', border: '#fecaca', bg: '#fef2f2' }
  if (v.includes('watch')) return { color: '#92400e', border: '#fde68a', bg: '#fffbeb' }
  if (v.includes('healthy')) return { color: '#166534', border: '#bbf7d0', bg: '#f0fdf4' }
  return { color: '#475569', border: '#cbd5e1', bg: '#f8fafc' }
}

function Field({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <div style={{ marginTop: 8 }}>
      <p style={{ margin: 0, fontSize: 12, color: '#64748b', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.3 }}>{label}</p>
      <p style={{ margin: '2px 0 0', fontSize: 15, color: '#0f172a' }}>{value ?? NOT_AVAILABLE}</p>
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

function computeHealthStatus({ runState, drift, hardGate, repairLoops, constitutionPanels }: {
  runState: RunState | null
  drift: DriftRecord | null
  hardGate: HardGateState | null
  repairLoops: number
  constitutionPanels: ConstitutionResult[]
}) {
  const runHealth = isBlockedStatus(runState?.current_run_status) ? 'At Risk' : runState?.current_run_status ? 'Healthy' : 'Unknown'

  const driftText = (drift?.drift_classification ?? '').toLowerCase()
  const driftState = !drift?.drift_classification ? 'Unknown' : driftText.includes('high') || driftText.includes('severe') ? 'At Risk' : driftText.includes('moderate') ? 'Watch' : 'Healthy'

  const fpq = (runState?.first_pass_quality ?? '').toLowerCase()
  const firstPassQuality = !runState?.first_pass_quality ? 'Unknown' : fpq.includes('low') || fpq.includes('poor') ? 'At Risk' : fpq.includes('medium') || fpq.includes('fair') ? 'Watch' : 'Healthy'

  const repairLoopPressure = repairLoops > 2 ? 'At Risk' : repairLoops > 0 ? 'Watch' : runState ? 'Healthy' : 'Unknown'

  const constitutionFail = constitutionPanels.some((panel) => isBlockedStatus(panel.status) || safeArray(panel.violations).length > 0)
  const constitutionalStatus = constitutionFail ? 'At Risk' : constitutionPanels.some((panel) => panel.status || panel.summary) ? 'Healthy' : 'Unknown'

  const hardGateReady = isTruthyStatus(hardGate?.readiness_status)
  const hardGateMissing = !!hardGate?.gate_name && !hardGateReady

  if (hardGateMissing && runHealth === 'Healthy') {
    return { runHealth: 'Watch', driftState, firstPassQuality, repairLoopPressure, constitutionalStatus }
  }

  return { runHealth, driftState, firstPassQuality, repairLoopPressure, constitutionalStatus }
}

function compareText(current?: string, previous?: string, labels?: { up: string; down: string; equal: string }): string {
  if (!current || !previous) return HISTORY_NOT_AVAILABLE
  if (current === previous) return labels?.equal ?? 'Unchanged'

  const parseTrend = (value: string) => {
    const lower = value.toLowerCase()
    if (lower.includes('improv') || lower.includes('decreas') || lower.includes('down')) return -1
    if (lower.includes('worse') || lower.includes('increas') || lower.includes('up')) return 1
    return 0
  }

  const currentScore = parseTrend(current)
  const previousScore = parseTrend(previous)
  const delta = currentScore - previousScore

  if (delta > 0) return labels?.up ?? 'Increased'
  if (delta < 0) return labels?.down ?? 'Decreased'
  return labels?.equal ?? 'Changed'
}

export default function RepoDashboard() {
  const [snapshot, setSnapshot] = useState<Snapshot>(fallbackSnapshot)
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

  useEffect(() => {
    let cancelled = false

    const retrieveArtifact = async <T,>(path: string): Promise<T | null> => {
      try {
        const response = await fetch(path)
        if (!response.ok) {
          return null
        }
        return (await response.json()) as T
      } catch {
        return null
      }
    }

    const retrieveAll = async () => {
      const snapshotData = await retrieveArtifact<Snapshot>('/repo_snapshot.json')
      if (!cancelled) setSnapshot(snapshotData ?? fallbackSnapshot)

      const snapshotMetaData = await retrieveArtifact<SnapshotMeta>('/repo_snapshot_meta.json')
      if (!cancelled) setSnapshotMeta(snapshotMetaData)

      const bottleneckData = await retrieveArtifact<BottleneckRecord>('/current_bottleneck_record.json')
      if (!cancelled) setBottleneck(bottleneckData)

      const driftData = await retrieveArtifact<DriftRecord>('/drift_trend_continuity_artifact.json')
      if (!cancelled) setDrift(driftData)

      const previousDriftData = await retrieveArtifact<DriftRecord>('/prior_drift_trend_continuity_artifact.json')
      if (!cancelled) setPreviousDrift(previousDriftData)

      const roadmapData = await retrieveArtifact<RoadmapState>('/canonical_roadmap_state_artifact.json')
      if (!cancelled) setRoadmapState(roadmapData)

      const maturityData = await retrieveArtifact<MaturityTracker>('/maturity_phase_tracker.json')
      if (!cancelled) setMaturityState(maturityData)

      const hardGateData = await retrieveArtifact<HardGateState>('/hard_gate_status_record.json')
      if (!cancelled) setHardGate(hardGateData)

      const previousHardGateData = await retrieveArtifact<HardGateState>('/prior_hard_gate_status_record.json')
      if (!cancelled) setPreviousHardGate(previousHardGateData)

      const runData = await retrieveArtifact<RunState>('/current_run_state_record.json')
      if (!cancelled) setRunState(runData)

      const previousRunData = await retrieveArtifact<RunState>('/prior_current_run_state_record.json')
      if (!cancelled) setPreviousRunState(previousRunData)

      const deferredData = await retrieveArtifact<{ items?: DeferredItem[] }>('/deferred_item_register.json')
      if (!cancelled) setDeferredItems(Array.isArray(deferredData?.items) ? deferredData.items : [])

      const trackerData = await retrieveArtifact<{ items?: DeferredReadiness[] }>('/deferred_return_tracker.json')
      if (!cancelled) setDeferredTracker(Array.isArray(trackerData?.items) ? trackerData.items : [])

      const constitutionData = await retrieveArtifact<ConstitutionResult>('/constitutional_drift_checker_result.json')
      if (!cancelled) setConstitutionDrift(constitutionData)

      const alignmentData = await retrieveArtifact<ConstitutionResult>('/roadmap_alignment_validator_result.json')
      if (!cancelled) setRoadmapAlignment(alignmentData)

      const serialData = await retrieveArtifact<ConstitutionResult>('/serial_bundle_validator_result.json')
      if (!cancelled) setSerialBundle(serialData)
    }

    retrieveAll()

    return () => {
      cancelled = true
    }
  }, [])

  const counts = useMemo(() => snapshot.root_counts ?? {}, [snapshot.root_counts])

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

  const nextAction = useMemo<NextAction | null>(() => {
    const readiness = (hardGate?.readiness_status ?? '').toLowerCase()
    const gateNotSatisfied = hardGate?.gate_name && !isTruthyStatus(readiness)
    if (gateNotSatisfied) {
      const missingEvidence = safeArray(hardGate?.required_evidence)[0]
      return {
        title: `Satisfy hard gate: ${hardGate?.gate_name}`,
        reason: missingEvidence ? `Missing evidence: ${missingEvidence}` : 'Hard gate readiness is not yet satisfied.',
        confidence: 'High',
        sourceBasis: 'hard gate'
      }
    }

    if (isBlockedStatus(runState?.current_run_status)) {
      return {
        title: `Run bounded repair for ${bottleneck?.bottleneck_name ?? 'active bottleneck'}`,
        reason: `Current run status is ${runState?.current_run_status ?? 'blocked'} with repair pressure present.`,
        confidence: 'High',
        sourceBasis: 'run state'
      }
    }

    if (bottleneck?.bottleneck_name) {
      return {
        title: `Address bottleneck: ${bottleneck.bottleneck_name}`,
        reason: bottleneck.explanation ?? 'Current bottleneck is defined and should be reduced before progressing phases.',
        confidence: 'Medium',
        sourceBasis: 'bottleneck'
      }
    }

    const readyDeferred = deferredItems.find((item) => {
      const signal = (item.item_id ? deferredSignalById.get(item.item_id) : '').toLowerCase()
      return signal.includes('ready') || signal.includes('revisit') || signal.includes('go')
    })

    if (readyDeferred) {
      return {
        title: `Revisit deferred item: ${readyDeferred.item_name ?? readyDeferred.item_id ?? 'deferred item'}`,
        reason: `Deferred readiness indicates return conditions are approaching satisfaction.`,
        confidence: 'Medium',
        sourceBasis: 'deferred'
      }
    }

    if (drift || runState || roadmapState) {
      return {
        title: 'Run next governed execution cycle',
        reason: 'No blocking gate or urgent bottleneck is active in current artifacts.',
        confidence: 'Low',
        sourceBasis: 'drift / run state'
      }
    }

    return null
  }, [hardGate, runState, bottleneck, deferredItems, deferredSignalById, drift, roadmapState])

  const health = useMemo(
    () =>
      computeHealthStatus({
        runState,
        drift,
        hardGate,
        repairLoops: runState?.repair_loop_count ?? 0,
        constitutionPanels: [constitutionDrift, roadmapAlignment, serialBundle].filter(Boolean) as ConstitutionResult[]
      }),
    [runState, drift, hardGate, constitutionDrift, roadmapAlignment, serialBundle]
  )

  const changeSummary = useMemo(
    () => ({
      bottleneck: compareText(bottleneck?.bottleneck_name, undefined, { equal: 'Unchanged' }),
      drift: compareText(drift?.trend, previousDrift?.trend, {
        up: 'Worsened',
        down: 'Improved',
        equal: 'Stable'
      }),
      repairLoops:
        typeof runState?.repair_loop_count === 'number' && typeof previousRunState?.repair_loop_count === 'number'
          ? runState.repair_loop_count > previousRunState.repair_loop_count
            ? 'Increased'
            : runState.repair_loop_count < previousRunState.repair_loop_count
              ? 'Decreased'
              : 'Flat'
          : HISTORY_NOT_AVAILABLE,
      hardGate: compareText(hardGate?.readiness_status, previousHardGate?.readiness_status, { equal: 'Unchanged' })
    }),
    [bottleneck, drift, previousDrift, runState, previousRunState, hardGate, previousHardGate]
  )

  const metaMissing = !snapshotMeta?.last_refreshed_time || !snapshotMeta?.snapshot_size || !snapshotMeta?.data_source_state

  return (
    <main style={pageStyle}>
      <header style={{ marginBottom: 10 }}>
        <h1 style={{ margin: 0, fontSize: 30, lineHeight: 1.15 }}>Operator Control Surface</h1>
        <p style={{ margin: '8px 0 0', color: '#475569', fontSize: 15 }}>
          Live governed execution view for <strong>{snapshot.repo_name ?? NOT_AVAILABLE}</strong>. Focus on current risk, next action, and artifact health.
        </p>
      </header>

      <section style={{ ...sectionStyle, gridTemplateColumns: '1fr' }}>
        <article style={prominentCardStyle}>
          <h2 style={{ margin: 0, fontSize: 18 }}>Next Action</h2>
          {nextAction ? (
            <>
              <p style={{ margin: '10px 0 0', fontSize: 20, fontWeight: 700, color: '#0f172a' }}>{nextAction.title}</p>
              <p style={{ margin: '6px 0 0', color: '#334155' }}>{nextAction.reason}</p>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 12 }}>
                <span style={{ padding: '4px 10px', borderRadius: 999, border: '1px solid #cbd5e1', fontSize: 12, fontWeight: 600 }}>
                  Confidence: {nextAction.confidence}
                </span>
                <span style={{ padding: '4px 10px', borderRadius: 999, border: '1px solid #cbd5e1', fontSize: 12, color: '#475569' }}>
                  Source basis: {nextAction.sourceBasis}
                </span>
              </div>
            </>
          ) : (
            <p style={{ margin: '8px 0 0', color: '#64748b' }}>{NOT_AVAILABLE}</p>
          )}
        </article>
      </section>

      <section style={sectionStyle}>
        <article style={cardStyle}>
          <h2 style={{ margin: 0, fontSize: 17 }}>System Health</h2>
          {[
            ['Current run health', health.runHealth],
            ['Drift state', health.driftState],
            ['First-pass quality', health.firstPassQuality],
            ['Repair loop pressure', health.repairLoopPressure],
            ['Constitutional status', health.constitutionalStatus]
          ].map(([label, value]) => {
            const tone = statusTone(value)
            return (
              <div key={label} style={{ marginTop: 10, display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'center' }}>
                <span style={{ color: '#334155', fontSize: 14 }}>{label}</span>
                <span style={{ color: tone.color, border: `1px solid ${tone.border}`, background: tone.bg, borderRadius: 999, padding: '3px 10px', fontSize: 12, fontWeight: 600 }}>
                  {value}
                </span>
              </div>
            )
          })}
        </article>

        <article style={cardStyle}>
          <h2 style={{ margin: 0, fontSize: 17 }}>What Changed</h2>
          <Field label='Bottleneck' value={changeSummary.bottleneck} />
          <Field label='Drift trend' value={changeSummary.drift} />
          <Field label='Repair loops' value={changeSummary.repairLoops} />
          <Field label='Hard gate' value={changeSummary.hardGate} />
          {Object.values(changeSummary).every((v) => v === HISTORY_NOT_AVAILABLE) ? (
            <p style={{ margin: '10px 0 0', color: '#64748b' }}>{HISTORY_NOT_AVAILABLE}</p>
          ) : null}
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

        <article style={{ ...cardStyle, border: metaMissing ? '1px solid #f59e0b' : cardStyle.border }}>
          <h2 style={{ margin: 0, fontSize: 17 }}>Snapshot metadata</h2>
          <Field label='Last refreshed' value={snapshotMeta?.last_refreshed_time} />
          <Field label='Snapshot size' value={snapshotMeta?.snapshot_size} />
          <Field label='Source state' value={snapshotMeta?.data_source_state} />
          {metaMissing ? <p style={{ margin: '10px 0 0', color: '#92400e' }}>Staleness risk: metadata incomplete.</p> : null}
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
