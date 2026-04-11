import type { DashboardViewModel, Snapshot } from '../types/dashboard'
import { DashboardSections } from './sections/DashboardSections'
import { BlockedState } from './primitives/ui'

type RepoDashboardRenderGate =
  | { kind: 'renderable'; snapshot: Snapshot }
  | { kind: 'no_data' | 'incomplete_publication' | 'stale' | 'truth_violation' }

export default function RepoDashboard({ model }: { model: DashboardViewModel }) {
  const renderGate: RepoDashboardRenderGate =
    model.state.kind === 'renderable' && model.sections.snapshot.data
      ? { kind: 'renderable', snapshot: model.sections.snapshot.data }
      : { kind: model.state.kind === 'renderable' ? 'truth_violation' : model.state.kind }

  return (
    <main style={{ maxWidth: 1100, margin: '0 auto', padding: '20px 12px 40px' }}>
      <header>
        <h1 style={{ margin: 0 }}>Operator Surface</h1>
        <p style={{ color: '#475569' }}>Governed execution dashboard for {model.repoName}.</p>
      </header>

      {renderGate.kind !== 'renderable' ? (
        <BlockedState title={`Dashboard unavailable: ${model.state.kind}`} reason={model.state.reason} />
      ) : null}

      {renderGate.kind !== 'renderable' ? null : renderGate.snapshot.runtime_hotspots ? null : null}

      <DashboardSections model={model} />
    </main>
  )
}
