'use client'

import { useEffect, useMemo, useState, type CSSProperties } from 'react'

type Snapshot = {
  repo_name?: string
  root_counts?: Record<string, number>
  core_areas?: string[]
  constitutional_center?: string[]
  runtime_hotspots?: string[]
  operational_signals?: string[]
}

const exampleSnapshot: Snapshot = {
  repo_name: 'spectrum-systems',
  root_counts: {
    files: 0,
    modules: 0,
    tests: 0,
    contracts: 0
  },
  core_areas: [],
  constitutional_center: [],
  runtime_hotspots: ['No runtime hotspots detected in example data.'],
  operational_signals: ['No operational signals available.']
}

const cardStyle: CSSProperties = {
  background: '#ffffff',
  borderRadius: 12,
  padding: 16,
  boxShadow: '0 1px 2px rgba(15, 23, 42, 0.08)',
  border: '1px solid #e2e8f0'
}

export default function RepoDashboard() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<Snapshot | null>(null)

  useEffect(() => {
    let cancelled = false

    const retrieveSnapshot = async () => {
      try {
        const response = await fetch('/repo_snapshot.json')
        if (!response.ok) {
          throw new Error(`Snapshot retrieve failed (${response.status})`)
        }
        const json = (await response.json()) as Snapshot
        if (!cancelled) {
          setData(json)
          setError(null)
        }
      } catch (err) {
        if (!cancelled) {
          setData(exampleSnapshot)
          setError(err instanceof Error ? err.message : 'Unknown retrieve failure')
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    retrieveSnapshot()

    return () => {
      cancelled = true
    }
  }, [])

  const snapshot = useMemo(() => data ?? exampleSnapshot, [data])
  const counts = snapshot.root_counts ?? {}

  const fileCount = counts.files ?? 0
  const moduleCount = counts.modules ?? 0
  const testCount = counts.tests ?? 0
  const contractCount = counts.contracts ?? 0

  return (
    <main
      style={{
        maxWidth: 960,
        margin: '0 auto',
        padding: '16px 12px 32px'
      }}
    >
      <header style={{ marginBottom: 16 }}>
        <h1 style={{ margin: '8px 0', fontSize: 26 }}>Repository Dashboard</h1>
        <p style={{ margin: 0, color: '#334155' }}>
          {loading
            ? 'Loading snapshot...'
            : `Repo: ${snapshot.repo_name ?? 'Unknown repository'}`}
        </p>
        {error ? (
          <p style={{ color: '#b91c1c', marginTop: 8 }}>
            Snapshot retrieve failure. Using fallback artifact. Details: {error}
          </p>
        ) : null}
      </header>

      <section
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
          gap: 12,
          marginBottom: 16
        }}
      >
        <article style={cardStyle}>
          <h2 style={{ margin: '0 0 8px', fontSize: 14, color: '#475569' }}>Files</h2>
          <strong style={{ fontSize: 24 }}>{fileCount}</strong>
        </article>
        <article style={cardStyle}>
          <h2 style={{ margin: '0 0 8px', fontSize: 14, color: '#475569' }}>Modules</h2>
          <strong style={{ fontSize: 24 }}>{moduleCount}</strong>
        </article>
        <article style={cardStyle}>
          <h2 style={{ margin: '0 0 8px', fontSize: 14, color: '#475569' }}>Tests</h2>
          <strong style={{ fontSize: 24 }}>{testCount}</strong>
        </article>
        <article style={cardStyle}>
          <h2 style={{ margin: '0 0 8px', fontSize: 14, color: '#475569' }}>Contracts</h2>
          <strong style={{ fontSize: 24 }}>{contractCount}</strong>
        </article>
      </section>

      <section style={{ ...cardStyle, marginBottom: 12 }}>
        <h2 style={{ marginTop: 0 }}>Runtime hotspots</h2>
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          {(snapshot.runtime_hotspots?.length
            ? snapshot.runtime_hotspots
            : ['None reported.']
          ).map((item, index) => (
            <li key={`hotspot-${index}`}>{item}</li>
          ))}
        </ul>
      </section>

      <section style={cardStyle}>
        <h2 style={{ marginTop: 0 }}>Operational signals</h2>
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          {(snapshot.operational_signals?.length
            ? snapshot.operational_signals
            : ['None reported.']
          ).map((item, index) => (
            <li key={`signal-${index}`}>{item}</li>
          ))}
        </ul>
      </section>
    </main>
  )
}
