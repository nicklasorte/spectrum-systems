import { PANEL_CAPABILITY_MAP } from '../contracts/panel_capability_map'
import { DASHBOARD_SURFACE_CONTRACT_REGISTRY } from '../contracts/surface_contract_registry'
import { PANEL_FIELD_PROVENANCE_MAP } from '../provenance/field_provenance'

export function evaluateDashboardCertificationGate(): { status: 'pass' | 'blocked'; reasons: string[] } {
  const reasons: string[] = []

  const contractPanelIds = new Set(DASHBOARD_SURFACE_CONTRACT_REGISTRY.map((row) => row.panel_id))
  const capabilityPanelIds = new Set(PANEL_CAPABILITY_MAP.map((row) => row.panel_id))
  const provenancePanelIds = new Set(PANEL_FIELD_PROVENANCE_MAP.map((row) => row.panel_id))

  for (const panelId of contractPanelIds) {
    if (!capabilityPanelIds.has(panelId)) {
      reasons.push(`missing capability map entry: ${panelId}`)
    }
    if (!provenancePanelIds.has(panelId)) {
      reasons.push(`missing field provenance entry: ${panelId}`)
    }
  }

  for (const panelId of capabilityPanelIds) {
    if (!contractPanelIds.has(panelId)) {
      reasons.push(`capability map panel has no contract: ${panelId}`)
    }
  }

  for (const row of DASHBOARD_SURFACE_CONTRACT_REGISTRY) {
    if (!row.provenance_requirements.length) {
      reasons.push(`missing provenance requirements: ${row.panel_id}`)
    }
    if (!row.allowed_statuses.includes('blocked')) {
      reasons.push(`blocked status missing from contract: ${row.panel_id}`)
    }
  }

  if (PANEL_CAPABILITY_MAP.some((row) => row.decision_authority !== 'read_only')) {
    reasons.push('selector-side governance decision authority detected')
  }

  const blockedStateUntestedPanels = DASHBOARD_SURFACE_CONTRACT_REGISTRY
    .filter((row) => row.blocked_state_behavior !== 'render_blocked_diagnostic' && row.blocked_state_behavior !== 'hide_panel')
    .map((row) => row.panel_id)

  if (blockedStateUntestedPanels.length > 0) {
    reasons.push(`invalid blocked-state behavior contract: ${blockedStateUntestedPanels.join(', ')}`)
  }

  return {
    status: reasons.length > 0 ? 'blocked' : 'pass',
    reasons
  }
}
