import type { DashboardViewModel } from '../types/dashboard'
import { DashboardSections } from './sections/DashboardSections'
import { BlockedState } from './primitives/ui'

export default function RepoDashboard({ model }: { model: DashboardViewModel }) {
  return (
    <main style={{ maxWidth: 1100, margin: '0 auto', padding: '20px 12px 40px' }}>
      <header>
        <h1 style={{ margin: 0 }}>Operator Surface</h1>
        <p style={{ color: '#475569' }}>Governed execution dashboard for {model.repoName}.</p>
      </header>

      {model.state.kind !== 'renderable' ? (
        <BlockedState title={`Dashboard unavailable: ${model.state.kind}`} reason={model.state.reason} />
      ) : null}

      <DashboardSections model={model} />
    </main>
  )
}
