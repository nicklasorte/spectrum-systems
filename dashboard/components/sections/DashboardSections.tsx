import React from 'react'
import type { DashboardViewModel, SectionInput } from '../../types/dashboard'
import { Card, EmptyState, KeyValueList, SectionHeader, StatusBadge } from '../primitives/ui'
import { ArtifactChip, Table, Timeline, TrendPanel, StateStrip } from '../primitives/data_views'
import { ProvenanceDrawer } from '../drawers/ProvenanceDrawer'
import { TopologyPanel } from '../topology/TopologyPanel'
import { ReviewQueuePanel } from '../review/ReviewQueuePanel'

function SectionShell<T>({ section, render }: { section: SectionInput<T>; render: (data: T) => React.ReactNode }) {
  if (section.state !== 'renderable' || !section.data) {
    return (
      <Card tone={section.state === 'truth_violation' ? 'danger' : 'muted'}>
        <SectionHeader title={section.title} subtitle={`${section.state}: ${section.reason ?? 'Unavailable'}`} />
        <EmptyState text='Section unavailable by governed render state.' />
        <ProvenanceDrawer title={section.title} rows={section.provenance} />
      </Card>
    )
  }
  return (
    <Card>
      <SectionHeader title={section.title} />
      {render(section.data)}
      <ProvenanceDrawer title={section.title} rows={section.provenance} />
    </Card>
  )
}

export function DashboardSections({ model }: { model: DashboardViewModel }) {
  return (
    <div style={{ display: 'grid', gap: 12 }}>
      <StateStrip items={[
        { label: 'publication', value: model.integrity.publicationState },
        { label: 'freshness', value: model.freshness.status },
        { label: 'last refresh', value: model.freshness.lastRefresh },
        { label: 'integrity', value: model.integrity.manifestCompleteness },
        { label: 'reason codes', value: model.state.truthViolationReasons.join(', ') || 'none' }
      ]} />

      <Card tone={model.state.kind === 'renderable' ? 'default' : 'danger'}>
        <SectionHeader title='Next action recommendation' subtitle={model.recommendation.reason} />
        <div style={{ display: 'flex', gap: 8 }}>
          <StatusBadge label={`confidence: ${model.recommendation.confidence}`} />
          <StatusBadge label={`source: ${model.recommendation.sourceBasis}`} />
        </div>
        <p>{model.recommendation.title}</p>
        <Timeline title='Why this' items={model.recommendation.why} />
        <Timeline title='What changes' items={model.recommendation.whatChanges} />
        <ProvenanceDrawer title='recommendation' rows={model.recommendation.provenance} />
      </Card>

      <TopologyPanel nodes={model.topology} />

      <TrendPanel items={model.trends} />

      <Table title='Current vs prior comparison' rows={Object.entries(model.comparison).map(([k, v]) => [k, v])} />

      <Table title='Artifact explorer' rows={model.artifactExplorer.map((a) => [a.family, a.name, a.status, a.path])} />

      <Table title='Artifact-family health scorecards' rows={model.healthScorecards.map((h) => [h.family, String(h.score), h.grade, h.rule])} />

      <ReviewQueuePanel items={model.reviewQueue} />

      <SectionShell section={model.sections.snapshot} render={(data) => <KeyValueList pairs={[{ key: 'repo', value: data.repo_name ?? 'Not available yet' }, { key: 'files', value: data.root_counts?.files_total ?? 0 }, { key: 'runtime modules', value: data.root_counts?.runtime_modules ?? 0 }]} />} />

      <SectionShell section={model.sections.bottleneck} render={(data) => <KeyValueList pairs={[{ key: 'name', value: data.bottleneck_name ?? 'Not available yet' }, { key: 'explanation', value: data.explanation ?? 'Not available yet' }]} />} />

      <SectionShell section={model.sections.drift} render={(data) => <KeyValueList pairs={[{ key: 'classification', value: data.drift_classification ?? 'Not available yet' }, { key: 'trend', value: data.trend ?? 'Not available yet' }]} />} />

      <SectionShell section={model.sections.hardGate} render={(data) => <KeyValueList pairs={[{ key: 'gate', value: data.gate_name ?? 'Not available yet' }, { key: 'readiness', value: data.readiness_status ?? 'Not available yet' }]} />} />

      <SectionShell section={model.sections.runState} render={(data) => <KeyValueList pairs={[{ key: 'status', value: data.current_run_status ?? 'Not available yet' }, { key: 'repair loops', value: data.repair_loop_count ?? 'Not available yet' }]} />} />

      <SectionShell section={model.sections.deferred} render={(data) => <Table title='Deferred items' rows={data.items.map((item) => [item.item_name ?? item.item_id ?? 'item', item.reason_deferred ?? 'not available'])} />} />

      <SectionShell section={model.sections.constitutional} render={(data) => <Timeline title='Constitutional checks' items={data.violations?.length ? data.violations : ['No violations detected']} />} />

      <Card>
        <SectionHeader title='Publication integrity' subtitle='Manifest completeness, stale/missing artifacts, and sync audit visibility.' />
        <KeyValueList pairs={[{ key: 'manifest completeness', value: model.integrity.manifestCompleteness }, { key: 'publication state', value: model.integrity.publicationState }, { key: 'sync audit state', value: model.integrity.syncAuditState }, { key: 'declared artifacts', value: model.integrity.declaredCount }, { key: 'loaded declared artifacts', value: model.integrity.loadedCount }, { key: 'valid loaded declared artifacts', value: model.integrity.validLoadedCount }]} />
        <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {model.provenance.map((p) => <ArtifactChip key={p.name} name={p.name} status={p.status} />)}
        </div>
      </Card>


      <Card tone={model.certificationGate.status === 'pass' ? 'default' : 'danger'}>
        <SectionHeader title='Dashboard certification gate' subtitle={`status: ${model.certificationGate.status}`} />
        <Timeline title='Gate reasons' items={model.certificationGate.reasons.length ? model.certificationGate.reasons : ['all panel contracts satisfied']} />
      </Card>

      {model.operatorPanels.map((panel) => (
        <Card key={panel.panelId} tone={panel.status === 'renderable' ? 'default' : 'danger'}>
          <SectionHeader title={panel.title} subtitle={`${panel.status}: ${panel.summary}`} />
          <Table title={panel.panelId} rows={panel.rows.length ? panel.rows : [[panel.blockedReason ?? 'blocked']]} />
        </Card>
      ))}

            <Table title='History + replay' rows={model.history.entries.map((entry) => [model.history.status, entry])} />
    </div>
  )
}
