import type { ReactNode } from 'react'

export function Card({ children, tone = 'default' }: { children: ReactNode; tone?: 'default' | 'danger' | 'muted' }) {
  const border = tone === 'danger' ? '#fecaca' : tone === 'muted' ? '#cbd5e1' : '#e2e8f0'
  const background = tone === 'danger' ? '#fef2f2' : '#ffffff'
  return <article style={{ background, border: `1px solid ${border}`, borderRadius: 12, padding: 14 }}>{children}</article>
}

export function SectionHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <h2 style={{ margin: 0, fontSize: 18 }}>{title}</h2>
      {subtitle ? <p style={{ margin: '6px 0 0', color: '#475569', fontSize: 14 }}>{subtitle}</p> : null}
    </div>
  )
}

export function StatusBadge({ label }: { label: string }) {
  return <span style={{ border: '1px solid #cbd5e1', borderRadius: 999, padding: '3px 10px', fontSize: 12 }}>{label}</span>
}

export function KeyValueList({ pairs }: { pairs: Array<{ key: string; value: string | number }> }) {
  return (
    <div style={{ display: 'grid', gap: 6 }}>
      {pairs.map((pair) => (
        <div key={pair.key} style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
          <span style={{ color: '#475569' }}>{pair.key}</span>
          <span>{pair.value}</span>
        </div>
      ))}
    </div>
  )
}

export function EmptyState({ text }: { text: string }) {
  return <p style={{ margin: 0, color: '#64748b' }}>{text}</p>
}

export function BlockedState({ title, reason }: { title: string; reason: string }) {
  return (
    <Card tone='danger'>
      <SectionHeader title={title} subtitle={reason} />
    </Card>
  )
}
