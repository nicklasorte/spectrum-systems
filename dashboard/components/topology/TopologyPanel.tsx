import { Card, SectionHeader } from '../primitives/ui'

export function TopologyPanel({ nodes }: { nodes: Array<{ node: string; status: string; provenance: string }> }) {
  return (
    <Card>
      <SectionHeader title='Operator topology' subtitle='Canonical role nodes with artifact-backed status.' />
      {nodes.map((node) => (
        <details key={node.node} style={{ marginBottom: 6 }}>
          <summary style={{ cursor: 'pointer' }}>{node.node} — {node.status}</summary>
          <p style={{ margin: '4px 0 0', color: '#475569' }}>provenance: {node.provenance}</p>
        </details>
      ))}
    </Card>
  )
}
