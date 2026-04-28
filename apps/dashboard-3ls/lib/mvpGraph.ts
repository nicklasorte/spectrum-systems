// D3L-MASTER-01 Phase 6 — MVP graph helper.
//
// MVP boxes are PRODUCT-LEVEL capabilities (Transcript Ingestion, Multi-pass
// Extraction, …). They are NOT registry systems and MUST NEVER appear as
// nodes in the 3LS graph. Each box maps to one or more registry-active
// systems; mappings are validated against the contract so every mapped
// system_id is in active_system_ids.
//
// The dashboard exposes this as a separate view toggled by the operator;
// the 3LS graph and the MVP graph never share nodes.

import type { D3LRegistryContract } from './systemRegistry';

export interface MVPBoxDefinition {
  id: string;
  label: string;
  description: string;
  /** registry-active system_ids this MVP capability maps to. */
  maps_to_systems: string[];
}

export interface MVPEdge {
  from: string;
  to: string;
}

export interface MVPGraphResult {
  boxes: MVPBoxDefinition[];
  edges: MVPEdge[];
  /** Returned mapping rows after registry validation. */
  validated_mappings: Array<{
    box_id: string;
    admitted_systems: string[];
    rejected_systems: string[];
  }>;
  warnings: string[];
}

/**
 * Canonical MVP boxes for the spectrum-systems product. Order is the
 * left-to-right pipeline order in the prompt. Each box maps to bounded
 * registry-active systems; nothing else.
 */
export const MVP_BOXES: MVPBoxDefinition[] = [
  {
    id: 'transcript_ingestion',
    label: 'Transcript Ingestion',
    description: 'inbound transcript admission and validation',
    maps_to_systems: ['AEX', 'CTX'],
  },
  {
    id: 'multi_pass_extraction',
    label: 'Multi-pass Extraction',
    description: 'bounded extraction passes over context bundles',
    maps_to_systems: ['PQX', 'CTX'],
  },
  {
    id: 'context_builder',
    label: 'Context Builder',
    description: 'context bundle assembly + admission',
    maps_to_systems: ['CTX', 'PRM'],
  },
  {
    id: 'paper_generator',
    label: 'Paper Generator',
    description: 'governed paper synthesis with HOP-evaluated harness',
    maps_to_systems: ['PQX', 'HOP'],
  },
  {
    id: 'eval_system',
    label: 'Eval System',
    description: 'required eval coverage and gate signals',
    maps_to_systems: ['EVL'],
  },
  {
    id: 'judgment_engine',
    label: 'Judgment Engine',
    description: 'judgment artifact semantics and lifecycle',
    maps_to_systems: ['JDX', 'JSX'],
  },
  {
    id: 'control_loop',
    label: 'Control Loop',
    description: 'closure signals and trust/policy_observation',
    maps_to_systems: ['CDE', 'TPA', 'SEL'],
  },
  {
    id: 'learning_loop',
    label: 'Learning Loop',
    description: 'failure diagnosis + repair planning, feeds eval candidates',
    maps_to_systems: ['FRE', 'RIL', 'RAX'],
  },
  {
    id: 'slo_system',
    label: 'SLO System',
    description: 'observability + reliability error-budget governance',
    maps_to_systems: ['OBS', 'SLO'],
  },
];

const MVP_EDGES: MVPEdge[] = [
  { from: 'transcript_ingestion', to: 'multi_pass_extraction' },
  { from: 'multi_pass_extraction', to: 'context_builder' },
  { from: 'context_builder', to: 'paper_generator' },
  { from: 'paper_generator', to: 'eval_system' },
  { from: 'eval_system', to: 'judgment_engine' },
  { from: 'judgment_engine', to: 'control_loop' },
  { from: 'control_loop', to: 'learning_loop' },
  { from: 'learning_loop', to: 'slo_system' },
];

/**
 * Validate the MVP graph against the registry contract. Any
 * maps_to_systems entry NOT in active_system_ids is rejected and
 * surfaced as a warning. Even if validation rejects every mapping,
 * the MVP boxes themselves remain — they describe capabilities, not
 * registry systems.
 */
export function buildMVPGraph(contract: D3LRegistryContract | null): MVPGraphResult {
  const warnings: string[] = [];
  if (!contract) {
    warnings.push('mvp_graph_contract_missing:registry_contract_unavailable');
  }
  const active = new Set(contract?.active_system_ids ?? []);
  const validated: MVPGraphResult['validated_mappings'] = [];
  for (const box of MVP_BOXES) {
    const admitted: string[] = [];
    const rejected: string[] = [];
    for (const sid of box.maps_to_systems) {
      if (active.size === 0) {
        rejected.push(sid);
        continue;
      }
      if (active.has(sid)) admitted.push(sid);
      else rejected.push(sid);
    }
    validated.push({ box_id: box.id, admitted_systems: admitted, rejected_systems: rejected });
    if (rejected.length > 0) {
      warnings.push(`mvp_box_rejected_mapping:${box.id}:${rejected.join(',')}`);
    }
  }
  return {
    boxes: MVP_BOXES.map((box) => ({ ...box })),
    edges: MVP_EDGES.map((edge) => ({ ...edge })),
    validated_mappings: validated,
    warnings,
  };
}

/**
 * Returns true iff `nodeId` is an MVP box (NOT a registry system).
 * Used to defensively assert the 3LS graph never accidentally renders
 * an MVP capability as a registry node.
 */
export function isMVPBoxId(nodeId: string): boolean {
  return MVP_BOXES.some((box) => box.id === nodeId);
}
