import type { DashboardViewModel, Snapshot } from '../types/dashboard'
import { DashboardSections } from './sections/DashboardSections'
import { BlockedState, Card, SectionHeader } from './primitives/ui'
import { StateStrip } from './primitives/data_views'

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
        <div style={{ display: 'grid', gap: 12 }}>
          <BlockedState title={`Dashboard unavailable: ${model.state.kind}`} reason={model.state.reason} />

          <StateStrip items={[
            { label: 'publication', value: model.integrity.publicationState },
            { label: 'freshness', value: model.freshness.status },
            { label: 'integrity', value: model.integrity.manifestCompleteness },
            { label: 'reason codes', value: model.state.truthViolationReasons.join(', ') || 'none' }
          ]} />

          <Card tone='muted'>
            <SectionHeader title='Blocked-state provenance/debug (non-operational)' subtitle='Surface intentionally excludes operational sections while truth gates are blocked.' />
            <p style={{ margin: 0, color: '#334155' }}>Missing artifacts: {model.state.missingArtifacts.join(', ') || 'none'}</p>
            <p style={{ margin: '6px 0 0', color: '#334155' }}>Stale artifacts: {model.state.staleArtifacts.join(', ') || 'none'}</p>
          </Card>
        </div>
      ) : (
        <DashboardSections model={model} />
      )}
    </main>
  )
}
