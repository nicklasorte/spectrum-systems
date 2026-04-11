import { Card, SectionHeader, EmptyState } from './ui'

export function StateStrip({ items }: { items: Array<{ label: string; value: string }> }) {
  return (
    <Card tone='muted'>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {items.map((item) => (
          <span key={item.label} style={{ border: '1px solid #cbd5e1', borderRadius: 999, padding: '4px 10px', fontSize: 12 }}>
            {item.label}: {item.value}
          </span>
        ))}
      </div>
    </Card>
  )
}

export function ArtifactChip({ name, status }: { name: string; status: string }) {
  return <span style={{ border: '1px solid #cbd5e1', borderRadius: 8, padding: '2px 8px', fontSize: 12 }}>{name} · {status}</span>
}

export function Table({ title, rows }: { title: string; rows: Array<Array<string>> }) {
  return (
    <Card>
      <SectionHeader title={title} />
      {rows.length === 0 ? <EmptyState text='No rows.' /> : (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}><tbody>{rows.map((row, idx) => <tr key={idx}>{row.map((cell, cidx) => <td key={cidx} style={{ borderTop: '1px solid #e2e8f0', padding: '6px 4px' }}>{cell}</td>)}</tr>)}</tbody></table>
      )}
    </Card>
  )
}

export function Timeline({ title, items }: { title: string; items: string[] }) {
  return <Table title={title} rows={items.map((item) => [item])} />
}

export function TrendPanel({ items }: { items: Array<{ label: string; value: string }> }) {
  return <Table title='Trend intelligence' rows={items.map((i) => [i.label, i.value])} />
}
