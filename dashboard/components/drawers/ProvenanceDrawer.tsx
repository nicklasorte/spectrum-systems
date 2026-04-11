import { Card, SectionHeader } from '../primitives/ui'

export function ProvenanceDrawer({ title, rows }: { title: string; rows: Array<{ artifact: string; path: string; keyFields: string[]; timestamp?: string }> }) {
  return (
    <details>
      <summary style={{ cursor: 'pointer', color: '#0f172a', fontWeight: 600 }}>Inspect provenance: {title}</summary>
      <Card>
        <SectionHeader title={`${title} provenance`} />
        {rows.map((row) => (
          <div key={`${row.artifact}-${row.path}`} style={{ marginTop: 8 }}>
            <p style={{ margin: 0, fontWeight: 600 }}>{row.artifact}</p>
            <p style={{ margin: '2px 0', color: '#475569' }}>{row.path}</p>
            <p style={{ margin: '2px 0', color: '#64748b' }}>keys: {row.keyFields.join(', ')}</p>
            <p style={{ margin: '2px 0', color: '#64748b' }}>timestamp: {row.timestamp ?? 'Not available yet'}</p>
          </div>
        ))}
      </Card>
    </details>
  )
}
