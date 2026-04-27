import type { DataSource } from '@/lib/types';

export type GraphLayer = 'core' | 'overlay' | 'support' | 'candidate' | 'unknown';
export type GraphState = 'trusted_signal' | 'caution_signal' | 'freeze_signal' | 'blocked_signal' | 'degraded_signal';

export type NodeSourceType = 'artifact_store' | 'repo_registry' | 'derived' | 'stub_fallback' | 'missing';

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
