'use client'

import { useEffect, useMemo, useState, type CSSProperties } from 'react'

type RootCounts = {
  files_total?: number
  runtime_modules?: number
  tests?: number
  contracts_total?: number
  schemas?: number
  examples?: number
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

type CoreArea = {
  name?: string
  description?: string
}

type Snapshot = {
  repo_name?: string
  root_counts?: RootCounts
  core_areas?: CoreArea[]
  constitutional_center?: string[]
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

const fallbackSnapshot: Snapshot = {
  repo_name: 'spectrum-systems',
  root_counts: {
    files_total: 0,
    runtime_modules: 0,
    tests: 0,
    contracts_total: 0,
    schemas: 0,
    examples: 0,
    docs: 0,
    run_artifacts: 0
  },
  core_areas: [],
  constitutional_center: [],
  runtime_hotspots: [],
  operational_signals: []
}

const notAvailable = 'Not available yet'

const pageStyle: CSSProperties = {
  maxWidth: 1024,
  margin: '0 auto',
  padding: '16px 12px 32px'
}

const gridStyle: CSSProperties = {
  display: 'grid',
  gap: 12,
  gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))'
}

const cardStyle: CSSProperties = {
  background: '#ffffff',
  borderRadius: 12,
  padding: 14,
  boxShadow: '0 1px 2px rgba(15, 23, 42, 0.08)',
  border: '1px solid #e2e8f0'
}

const sectionTitleStyle: CSSProperties = {
  margin: '0 0 8px',
  fontSize: 16,
  color: '#0f172a'
}

function safeArray(input: unknown): string[] {
  return Array.isArray(input) ? input.map(String) : []
}

function Field({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <p style={{ margin: '4px 0', color: '#1e293b', fontSize: 14 }}>
      <strong>{label}: </strong>
      <span>{value ?? notAvailable}</span>
    </p>
  )
}

function StringList({ items }: { items: string[] }) {
  if (!items.length) {
    return <p style={{ margin: '6px 0', color: '#64748b' }}>{notAvailable}</p>
  }

  return (
    <ul style={{ margin: '6px 0', paddingLeft: 18 }}>
      {items.map((item, index) => (
        <li key={`${item}-${index}`} style={{ marginBottom: 4 }}>
          {item}
        </li>
      ))}
    </ul>
  )
}

export default function RepoDashboard() {
  const [snapshot, setSnapshot] = useState<Snapshot>(fallbackSnapshot)
  const [snapshotMeta, setSnapshotMeta] = useState<SnapshotMeta | null>(null)
  const [bottleneck, setBottleneck] = useState<BottleneckRecord | null>(null)
  const [drift, setDrift] = useState<DriftRecord | null>(null)
  const [roadmapState, setRoadmapState] = useState<RoadmapState | null>(null)
  const [maturityState, setMaturityState] = useState<MaturityTracker | null>(null)
  const [hardGate, setHardGate] = useState<HardGateState | null>(null)
  const [runState, setRunState] = useState<RunState | null>(null)
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
      const [
        snapshotData,
        snapshotMetaData,
        bottleneckData,
        driftData,
        roadmapData,
        maturityData,
        hardGateData,
        runData,
        deferredData,
        trackerData,
        constitutionData,
        alignmentData,
        serialData
      ] = await Promise.all([
        retrieveArtifact<Snapshot>('/repo_snapshot.json'),
        retrieveArtifact<SnapshotMeta>('/repo_snapshot_meta.json'),
        retrieveArtifact<BottleneckRecord>('/current_bottleneck_record.json'),
        retrieveArtifact<DriftRecord>('/drift_trend_continuity_artifact.json'),
        retrieveArtifact<RoadmapState>('/canonical_roadmap_state_artifact.json'),
        retrieveArtifact<MaturityTracker>('/maturity_phase_tracker.json'),
        retrieveArtifact<HardGateState>('/hard_gate_status_record.json'),
        retrieveArtifact<RunState>('/current_run_state_record.json'),
        retrieveArtifact<{ items?: DeferredItem[] }>('/deferred_item_register.json'),
        retrieveArtifact<{ items?: DeferredReadiness[] }>('/deferred_return_tracker.json'),
        retrieveArtifact<ConstitutionResult>('/constitutional_drift_checker_result.json'),
        retrieveArtifact<ConstitutionResult>('/roadmap_alignment_validator_result.json'),
        retrieveArtifact<ConstitutionResult>('/serial_bundle_validator_result.json')
      ])

      if (cancelled) {
        return
      }

      setSnapshot(snapshotData ?? fallbackSnapshot)
      setSnapshotMeta(snapshotMetaData)
      setBottleneck(bottleneckData)
      setDrift(driftData)
      setRoadmapState(roadmapData)
      setMaturityState(maturityData)
      setHardGate(hardGateData)
      setRunState(runData)
      setDeferredItems(Array.isArray(deferredData?.items) ? deferredData.items : [])
      setDeferredTracker(Array.isArray(trackerData?.items) ? trackerData.items : [])
      setConstitutionDrift(constitutionData)
      setRoadmapAlignment(alignmentData)
      setSerialBundle(serialData)
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
      if (item.item_id) {
        map.set(item.item_id, item.readiness_signal ?? notAvailable)
      }
    })
    return map
  }, [deferredTracker])

  const constitutionPanels = [
    { title: 'Drift checker', payload: constitutionDrift },
    { title: 'Alignment validator', payload: roadmapAlignment },
    { title: 'Serial bundle validator', payload: serialBundle }
  ]

  return (
    <main style={pageStyle}>
      <header style={{ marginBottom: 12 }}>
        <h1 style={{ margin: '0 0 8px', fontSize: 24 }}>Operational Dashboard</h1>
        <p style={{ margin: 0, color: '#334155' }}>Repo: {snapshot.repo_name ?? notAvailable}</p>
      </header>

      <section style={{ ...gridStyle, marginBottom: 12 }}>
        <article style={cardStyle}>
          <h2 style={sectionTitleStyle}>Repository snapshot</h2>
          <Field label='Files' value={counts.files_total ?? 0} />
          <Field label='Runtime modules' value={counts.runtime_modules ?? 0} />
          <Field label='Tests' value={counts.tests ?? 0} />
          <Field label='Contracts' value={counts.contracts_total ?? 0} />
          <Field label='Docs' value={counts.docs ?? 0} />
          <Field label='Run artifacts' value={counts.run_artifacts ?? 0} />
        </article>

        <article style={cardStyle}>
          <h2 style={sectionTitleStyle}>Snapshot metadata</h2>
          <Field label='Last refreshed time' value={snapshotMeta?.last_refreshed_time} />
          <Field label='Snapshot size' value={snapshotMeta?.snapshot_size} />
          <Field label='Data source state' value={snapshotMeta?.data_source_state} />
        </article>
      </section>

      <section style={{ ...gridStyle, marginBottom: 12 }}>
        <article style={cardStyle}>
          <h2 style={sectionTitleStyle}>Bottleneck</h2>
          <Field label='Name' value={bottleneck?.bottleneck_name} />
          <Field label='Explanation' value={bottleneck?.explanation} />
          <p style={{ margin: '8px 0 4px' }}><strong>Impacted layers</strong></p>
          <StringList items={safeArray(bottleneck?.impacted_layers)} />
          <p style={{ margin: '8px 0 4px' }}><strong>Evidence</strong></p>
          <StringList items={safeArray(bottleneck?.evidence)} />
        </article>

        <article style={cardStyle}>
          <h2 style={sectionTitleStyle}>Drift</h2>
          <Field label='Classification' value={drift?.drift_classification} />
          <Field label='Trend' value={drift?.trend} />
          <p style={{ margin: '8px 0 4px' }}><strong>Key signals</strong></p>
          <StringList items={safeArray(drift?.key_signals)} />
          <Field label='Recommendation' value={drift?.short_recommendation} />
        </article>
      </section>

      <section style={{ ...gridStyle, marginBottom: 12 }}>
        <article style={cardStyle}>
          <h2 style={sectionTitleStyle}>Roadmap state</h2>
          <Field label='Primary phase' value={roadmapState?.primary_phase ?? maturityState?.primary_phase} />
          <Field label='Secondary phase' value={roadmapState?.secondary_phase ?? maturityState?.secondary_phase} />
          <Field label='Active batch' value={roadmapState?.active_batch} />
          <Field label='Next step' value={roadmapState?.next_step} />
        </article>

        <article style={cardStyle}>
          <h2 style={sectionTitleStyle}>Hard gate</h2>
          <Field label='Gate name' value={hardGate?.gate_name} />
          <Field label='Readiness status' value={hardGate?.readiness_status} />
          <p style={{ margin: '8px 0 4px' }}><strong>Required evidence</strong></p>
          <StringList items={safeArray(hardGate?.required_evidence)} />
          <p style={{ margin: '8px 0 4px' }}><strong>Falsification risks</strong></p>
          <StringList items={safeArray(hardGate?.falsification_risks)} />
        </article>
      </section>

      <section style={{ ...gridStyle, marginBottom: 12 }}>
        <article style={cardStyle}>
          <h2 style={sectionTitleStyle}>Run state</h2>
          <Field label='Current run status' value={runState?.current_run_status} />
          <Field label='Last successful cycle' value={runState?.last_successful_cycle} />
          <Field label='Last blocked cycle' value={runState?.last_blocked_cycle} />
          <Field label='Repair loop count' value={runState?.repair_loop_count} />
          <Field label='First-pass quality' value={runState?.first_pass_quality} />
        </article>

        <article style={cardStyle}>
          <h2 style={sectionTitleStyle}>Deferred items</h2>
          {deferredItems.length ? (
            deferredItems.map((item, index) => (
              <div key={`${item.item_id ?? item.item_name ?? 'deferred'}-${index}`} style={{ marginBottom: 10 }}>
                <Field label='Item' value={item.item_name ?? item.item_id} />
                <Field label='Reason deferred' value={item.reason_deferred} />
                <p style={{ margin: '8px 0 4px' }}><strong>Missing evidence</strong></p>
                <StringList items={safeArray(item.missing_evidence)} />
                <Field label='Return condition' value={item.return_condition} />
                <Field label='Readiness signal' value={item.item_id ? deferredSignalById.get(item.item_id) : notAvailable} />
              </div>
            ))
          ) : (
            <p style={{ margin: 0, color: '#64748b' }}>{notAvailable}</p>
          )}
        </article>
      </section>

      <section style={{ ...cardStyle, marginBottom: 12 }}>
        <h2 style={sectionTitleStyle}>Constitutional alignment</h2>
        <div style={gridStyle}>
          {constitutionPanels.map(({ title, payload }) => {
            const violations = safeArray(payload?.violations)
            const hasViolation = violations.length > 0 || (payload?.status ?? '').toLowerCase() === 'fail'
            return (
              <article
                key={title}
                style={{
                  ...cardStyle,
                  border: hasViolation ? '1px solid #dc2626' : '1px solid #e2e8f0',
                  boxShadow: 'none'
                }}
              >
                <h3 style={{ margin: '0 0 8px', fontSize: 15 }}>{title}</h3>
                <Field label='Result' value={payload?.status} />
                <Field label='Summary' value={payload?.summary} />
                <p style={{ margin: '8px 0 4px', color: hasViolation ? '#b91c1c' : '#1e293b' }}>
                  <strong>Violations</strong>
                </p>
                <StringList items={violations} />
              </article>
            )
          })}
        </div>
      </section>

      <section style={gridStyle}>
        <article style={cardStyle}>
          <h2 style={sectionTitleStyle}>Runtime hotspots</h2>
          {snapshot.runtime_hotspots?.length ? (
            snapshot.runtime_hotspots.map((hotspot, index) => (
              <div key={`${hotspot.area ?? 'hotspot'}-${index}`} style={{ marginBottom: 10 }}>
                <Field label='Area' value={hotspot.area} />
                <Field label='Count' value={hotspot.count} />
                <Field label='Note' value={hotspot.note} />
              </div>
            ))
          ) : (
            <p style={{ margin: '6px 0', color: '#64748b' }}>{notAvailable}</p>
          )}
        </article>
        <article style={cardStyle}>
          <h2 style={sectionTitleStyle}>Operational signals</h2>
          {snapshot.operational_signals?.length ? (
            snapshot.operational_signals.map((signal, index) => (
              <div key={`${signal.title ?? 'signal'}-${index}`} style={{ marginBottom: 10 }}>
                <Field label='Title' value={signal.title} />
                <Field label='Status' value={signal.status} />
                <Field label='Detail' value={signal.detail} />
              </div>
            ))
          ) : (
            <p style={{ margin: '6px 0', color: '#64748b' }}>{notAvailable}</p>
          )}
        </article>
      </section>
    </main>
  )
}
