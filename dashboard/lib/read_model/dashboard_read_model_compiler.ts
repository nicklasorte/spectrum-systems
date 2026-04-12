import type { DashboardPanelSurface, DashboardPublication } from '../../types/dashboard'
import { normalizeDecisionStatus } from '../normalization/status_normalization'
import { PANEL_CAPABILITY_MAP } from '../contracts/panel_capability_map'

function blocked(panelId: string, summary: string): DashboardPanelSurface {
  return { panelId, title: panelId, status: 'blocked', summary, rows: [], blockedReason: summary }
}

function requireValidated(panelId: string, artifact: { exists: boolean; valid: boolean }): boolean {
  return artifact.exists && artifact.valid
}

export function compileDashboardReadModel(publication: DashboardPublication): DashboardPanelSurface[] {
  if (PANEL_CAPABILITY_MAP.some((capability) => capability.decision_authority !== 'read_only')) {
    return [blocked('dashboard_read_model', 'Capability map violated read-only contract.')]
  }

  const panels: DashboardPanelSurface[] = []

  if (!requireValidated('trust_posture', publication.freshnessStatus) || !requireValidated('trust_posture', publication.syncAudit)) {
    panels.push(blocked('trust_posture', 'Freshness/sync artifacts missing or invalid.'))
  } else {
    const freshness = publication.freshnessStatus.data
    const audit = publication.syncAudit.data
    panels.push({
      panelId: 'trust_posture',
      title: 'Trust posture',
      status: 'renderable',
      summary: 'Inspectable trust dimensions from governed artifacts.',
      rows: [
        ['freshness', freshness?.status ?? 'unknown'],
        ['validation coverage', String(audit?.required_artifact_count ?? 'unknown')],
        ['provenance completeness', String(audit?.records?.length ?? 0)],
        ['trace completeness', freshness?.trace_id ? 'trace-present' : 'trace-missing'],
        ['replay status', publication.serialValidator.data?.pass ? 'pass' : 'blocked'],
        ['renderability', publication.manifest.valid ? 'renderable' : 'blocked']
      ]
    })
  }

  const controlStatus = normalizeDecisionStatus(publication.publicationAttemptRecord.data?.decision)
  if (!requireValidated('control_decisions', publication.publicationAttemptRecord) || controlStatus === 'unknown_blocked') {
    panels.push(blocked('control_decisions', 'Control decision artifact missing/invalid or unknown decision code.'))
  } else {
    panels.push({
      panelId: 'control_decisions',
      title: 'Control decisions',
      status: 'renderable',
      summary: 'Read-only view of governed control decisions.',
      rows: [[controlStatus, (publication.publicationAttemptRecord.data?.reason_codes ?? []).join(', ') || 'none', publication.publicationAttemptRecord.data?.timestamp ?? 'unknown']]
    })
  }

  const judgment = publication.judgmentApplication.data
  panels.push(requireValidated('judgment_records', publication.judgmentApplication)
    ? {
        panelId: 'judgment_records',
        title: 'Judgment records',
        status: 'renderable',
        summary: 'Judgment artifacts and precedent references.',
        rows: [[judgment?.decision_id ?? 'unknown', (judgment?.judgment_ids ?? []).join(', ') || 'none', String(Boolean(judgment?.consumed_by_control))]]
      }
    : blocked('judgment_records', 'Judgment artifact missing or invalid.'))

  const overrides = publication.overrideCapture.data?.overrides ?? []
  panels.push(requireValidated('override_lifecycle', publication.overrideCapture)
    ? {
        panelId: 'override_lifecycle',
        title: 'Override lifecycle',
        status: 'renderable',
        summary: 'Override actor/scope/justification/expiry state from artifact.',
        rows: overrides.map((row) => [row.override_id ?? 'unknown', row.operator_action ?? 'unknown', row.reason ?? 'unknown'])
      }
    : blocked('override_lifecycle', 'Override artifact missing or invalid.'))

  const replayReady = requireValidated('replay_certification', publication.replayPack) && requireValidated('replay_certification', publication.serialValidator)
  panels.push(replayReady
    ? {
        panelId: 'replay_certification',
        title: 'Replay and certification',
        status: 'renderable',
        summary: 'Replay/certification posture from governed artifacts.',
        rows: [[String(publication.serialValidator.data?.pass), (publication.replayPack.data?.scenario_ids ?? []).join(', '), publication.promotionGate.data?.promotion_decision ?? 'unknown']]
      }
    : blocked('replay_certification', 'Replay/certification artifacts missing or invalid.'))

  const covered = new Set(publication.contractCoverage.data?.covered_artifacts ?? [])
  const required = publication.manifest.data?.required_files ?? []
  const uncovered = required.filter((name) => !covered.has(name.replace('.json', '')))
  const severityScore = uncovered.length * 5 + (publication.overrideCapture.data?.overrides?.length ?? 0) * 10
  panels.push(requireValidated('weighted_coverage', publication.contractCoverage)
    ? {
        panelId: 'weighted_coverage',
        title: 'Weighted coverage',
        status: uncovered.length > 0 ? 'blocked' : 'renderable',
        summary: 'Coverage by artifact, eval, panel with severity weighting.',
        rows: [['covered', String(covered.size)], ['required', String(required.length)], ['uncovered', uncovered.join(', ') || 'none'], ['severity_weight', String(severityScore)]]
      }
    : blocked('weighted_coverage', 'Coverage artifact missing or invalid.'))

  const freshnessAge = String(publication.freshnessStatus.data?.snapshot_age_hours ?? 'unknown')
  const publishSuccess = normalizeDecisionStatus(publication.publicationAttemptRecord.data?.decision)
  const mismatchRate = publication.serialValidator.data?.pass ? '0' : '1'
  panels.push({
    panelId: 'trend_control_charts',
    title: 'Trend control charts',
    status: publishSuccess === 'unknown_blocked' ? 'blocked' : 'renderable',
    summary: 'Threshold-aware trend traces.',
    rows: [['freshness_age_hours', freshnessAge], ['publish_success', publishSuccess], ['replay_mismatch_rate', mismatchRate], ['validator_fail_rate', publication.serialValidator.data?.pass ? '0' : '1'], ['override_rate', String(overrides.length)]]
  })

  const freshnessDecision = normalizeDecisionStatus(publication.freshnessStatus.data?.status)
  const publicationDecision = normalizeDecisionStatus(publication.publicationAttemptRecord.data?.decision)
  const disagreement = freshnessDecision !== 'unknown_blocked' && publicationDecision !== 'unknown_blocked' && freshnessDecision !== publicationDecision
  panels.push({
    panelId: 'reconciliation',
    title: 'High-risk reconciliation',
    status: disagreement ? 'blocked' : 'renderable',
    summary: disagreement ? 'Independent sources disagree; trust fails closed.' : 'Independent sources agree.',
    rows: [['freshness_status', freshnessDecision], ['publication_decision', publicationDecision], ['disagreement', disagreement ? 'true' : 'false']]
  })

  panels.push({
    panelId: 'postmortem_outage',
    title: 'Postmortem and outage',
    status: requireValidated('postmortem_outage', publication.refreshRunRecord) ? 'renderable' : 'blocked',
    summary: 'Stale trips/publication failures/incident trace links.',
    rows: [[publication.refreshRunRecord.data?.failure_class ?? 'none', publication.refreshRunRecord.data?.trace_id ?? 'none', publication.publicationAttemptRecord.data?.decision ?? 'unknown']]
  })

  const hasHashes = Boolean(publication.syncAudit.data?.records?.every((row) => Boolean(row.sha256)))
  panels.push({
    panelId: 'tamper_evident_ledger',
    title: 'Tamper-evident publication ledger',
    status: hasHashes ? 'renderable' : 'blocked',
    summary: hasHashes ? 'Verification evidence complete.' : 'Verification partial/unavailable.',
    rows: [['records', String(publication.syncAudit.data?.records?.length ?? 0)], ['hashes_complete', String(hasHashes)], ['validator_pass', String(Boolean(publication.serialValidator.data?.pass))]]
  })

  const deadPanels = PANEL_CAPABILITY_MAP.filter((panel) => panel.reads_from_artifacts.some((name) => !publication.declaredArtifactMap[name])).map((panel) => panel.panel_id)
  panels.push({
    panelId: 'maintain_drift',
    title: 'Maintain and drift',
    status: deadPanels.length > 0 ? 'blocked' : 'renderable',
    summary: 'Dead panel and contract-binding drift indicators.',
    rows: [['dead_panels', deadPanels.join(', ') || 'none'], ['override_count', String(overrides.length)], ['mismatch_signals', uncovered.length > 0 ? 'present' : 'none']]
  })

  const fixtureArtifact = publication.declaredArtifactMap['rq_next_24_01__umbrella_3__nx_17_failure_hotspot_simulation_pack.json']
  const fixtureScenarios = (fixtureArtifact?.data as { scenario_ids?: string[] } | undefined)?.scenario_ids ?? []
  panels.push(fixtureArtifact?.exists && fixtureArtifact.valid
    ? {
        panelId: 'scenario_simulator',
        title: 'Governed scenario simulator',
        status: 'renderable',
        summary: 'Fixture-only simulator.',
        rows: fixtureScenarios.map((id) => [id, 'governed_fixture'])
      }
    : blocked('scenario_simulator', 'Simulation fixture artifact missing or invalid.'))

  panels.push({
    panelId: 'mobile_semantics',
    title: 'Mobile operator semantics',
    status: 'renderable',
    summary: 'Narrow-screen blocked-state semantics remain interpretable.',
    rows: [['blocked_diagnostic', controlStatus === 'allow' ? 'clear' : 'elevated'], ['high_risk_warning', disagreement ? 'shown' : 'none']]
  })

  return panels
}
