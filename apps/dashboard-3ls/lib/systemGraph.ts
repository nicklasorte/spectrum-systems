import type { DataSource } from '@/lib/types';

export type GraphLayer = 'core' | 'overlay' | 'support' | 'candidate' | 'unknown';
export type GraphState = 'trusted_signal' | 'caution_signal' | 'freeze_signal' | 'blocked_signal' | 'degraded_signal';

export type NodeSourceType = 'artifact_store' | 'repo_registry' | 'derived' | 'stub_fallback' | 'missing';

export type DebugNodeStatus =
  | 'OK'
  | 'MISSING'
  | 'STALE'
  | 'FAILED'
  | 'FALLBACK'
  | 'BLOCKING'
  | 'UNKNOWN';

export type DebugMode = 'normal' | 'blockers' | 'lineage' | 'control' | 'freshness';

export interface SystemGraphNode {
  system_id: string;
  label: string;
  layer: GraphLayer;
  role: string;
  trust_state: string;
  artifact_backed_percent: number;
  source_type: NodeSourceType;
  trust_gap_signals: string[];
  upstream: string[];
  downstream: string[];
  source_artifact_refs: string[];
  warning_count: number;
  is_focus: boolean;
  is_fallback_backed: boolean;
  is_disconnected: boolean;
  // Debugger-only fields. Fail-closed: missing means missing, never synthesised.
  debug_status?: DebugNodeStatus;
  why_blocked?: string | null;
  missing_artifacts?: string[];
  failed_evals?: string[];
  trace_gaps?: string[];
  upstream_blockers?: string[];
  downstream_dependents?: string[];
  schema_paths?: string[];
  producing_script?: string | null;
  last_recompute?: string | null;
}

export interface SystemGraphEdge {
  from: string;
  to: string;
  edge_type: 'dependency' | 'overlay' | 'support' | 'candidate' | 'unknown';
  source_type: NodeSourceType;
  source_artifact_ref: string;
  confidence: number;
  is_failure_path: boolean;
  is_broken: boolean;
  // Debugger-only edge fields.
  dependency_type?: string;
  artifact_backed?: boolean;
  last_validated?: string | null;
  related_signal?: string | null;
}

export interface SystemGraphPayload {
  graph_state: GraphState;
  generated_at: string;
  source_mix: Record<NodeSourceType, number>;
  trust_posture: string;
  nodes: SystemGraphNode[];
  edges: SystemGraphEdge[];
  focus_systems: string[];
  failure_path: string[];
  missing_artifacts: string[];
  warnings: string[];
  replay_commands: string[];
}

export function dataSourceToNodeSourceType(dataSource: DataSource | null | undefined): NodeSourceType {
  if (dataSource === 'artifact_store') return 'artifact_store';
  if (dataSource === 'repo_registry') return 'repo_registry';
  if (dataSource === 'derived' || dataSource === 'derived_estimate') return 'derived';
  if (dataSource === 'stub_fallback') return 'stub_fallback';
  return 'missing';
}

export function deriveDebugStatus(node: Pick<SystemGraphNode, 'trust_state' | 'source_type' | 'trust_gap_signals' | 'is_disconnected'>): DebugNodeStatus {
  if (node.source_type === 'missing') return 'MISSING';
  if (node.source_type === 'stub_fallback') return 'FALLBACK';
  if (node.trust_state === 'blocked_signal') return 'BLOCKING';
  if (node.trust_state === 'freeze_signal') return 'FAILED';
  if (node.trust_state === 'unknown_signal') return 'UNKNOWN';
  if (node.trust_state === 'caution_signal' && (node.trust_gap_signals?.length ?? 0) > 0) return 'STALE';
  if (node.trust_state === 'trusted_signal') return 'OK';
  return 'UNKNOWN';
}

export const DEBUG_MODES: ReadonlyArray<{ value: DebugMode; label: string; description: string }> = [
  { value: 'normal', label: 'Normal', description: 'clean layered graph' },
  { value: 'blockers', label: 'Blockers', description: 'emphasise failed/missing/stale/blocking systems' },
  { value: 'lineage', label: 'Lineage', description: 'emphasise artifact dependencies and source paths' },
  { value: 'control', label: 'Control', description: 'emphasise eval → control → enforcement path' },
  { value: 'freshness', label: 'Freshness', description: 'emphasise stale / missing artifacts and recompute age' },
];

export const CONTROL_PATH_SYSTEMS: ReadonlyArray<string> = ['EVL', 'TPA', 'CDE', 'SEL'];
