// D3L-REGISTRY-01 — Decision Layer view definitions.
//
// View-only grouping of registry-active systems into the canonical
// Signal → Evaluation → Policy → Control → Enforcement axis. This is NOT
// a new system or new graph — it is a projection over the existing
// registry-active set used by the Decision Layer tab.
//
// CDE remains the sole control-decision authority and SEL the sole
// enforcement authority. The grouping below is descriptive routing of
// where each registry system sits in the decision pipeline.

export type DecisionLayer =
  | 'signal'
  | 'evaluation'
  | 'policy'
  | 'control'
  | 'enforcement'
  | 'proof_governance'
  | 'judgment'
  | 'context_routing'
  | 'repair_reconciliation';

export interface DecisionLayerGroup {
  layer: DecisionLayer;
  label: string;
  description: string;
  systems: string[];
}

export const DECISION_LAYER_GROUPS: ReadonlyArray<DecisionLayerGroup> = [
  {
    layer: 'signal',
    label: 'Signal',
    description: 'execution / observability / candidate-signal sources',
    systems: ['PQX', 'OBS', 'RAX'],
  },
  {
    layer: 'evaluation',
    label: 'Evaluation',
    description: 'required eval coverage and gate signals',
    systems: ['EVL'],
  },
  {
    layer: 'policy',
    label: 'Policy',
    description: 'trust and policy adjudication, slo and security policy',
    systems: ['TPA', 'POL', 'SLO', 'SEC'],
  },
  {
    layer: 'control',
    label: 'Control',
    description: 'closure / promotion-readiness control authority',
    systems: ['CDE'],
  },
  {
    layer: 'enforcement',
    label: 'Enforcement',
    description: 'fail-closed runtime enforcement',
    systems: ['SEL'],
  },
  {
    layer: 'proof_governance',
    label: 'Proof / Governance',
    description: 'replay, lineage, promotion-readiness, certification',
    systems: ['REP', 'LIN', 'PRA', 'GOV'],
  },
  {
    layer: 'judgment',
    label: 'Judgment',
    description: 'judgment semantics and lifecycle authority',
    systems: ['JDX', 'JSX'],
  },
  {
    layer: 'context_routing',
    label: 'Context / Routing',
    description: 'context bundles, prompt registry, orchestration, system-map projection',
    systems: ['CTX', 'PRM', 'TLC', 'MAP'],
  },
  {
    layer: 'repair_reconciliation',
    label: 'Repair / Reconciliation',
    description: 'interpretation, failure diagnosis, drift reconciliation, capacity governance',
    systems: ['RIL', 'FRE', 'RSM', 'CAP'],
  },
];

/**
 * Filter the static decision-layer grouping to only include systems that
 * are currently registry-active. This is the safety belt that keeps the
 * Decision Layer view from inventing or stranded-referencing a system if
 * the registry changes.
 */
export function filterDecisionLayersByRegistry(
  allowedActiveNodeIds: ReadonlyArray<string>,
): DecisionLayerGroup[] {
  const allowed = new Set(allowedActiveNodeIds);
  return DECISION_LAYER_GROUPS
    .map((group) => ({
      ...group,
      systems: group.systems.filter((systemId) => allowed.has(systemId)),
    }))
    .filter((group) => group.systems.length > 0);
}

/**
 * Returns the decision layer for a given system_id, or null if it is not
 * placed in the canonical decision-layer projection.
 */
export function decisionLayerForSystem(systemId: string): DecisionLayer | null {
  for (const group of DECISION_LAYER_GROUPS) {
    if (group.systems.includes(systemId)) return group.layer;
  }
  return null;
}
