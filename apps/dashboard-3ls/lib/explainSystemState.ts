// D3L-REGISTRY-01 — Deterministic Explain System State.
//
// Builds a fixed-shape, registry-backed explanation of the current trust
// state. Same inputs → same output. No free-form LLM text. No guessed
// root cause. Used by both the Explain panel and the system-state tests.

import type { PriorityArtifactLoadResult, RankedSystem } from './artifactLoader';
import type { SystemGraphPayload } from './systemGraph';
import type { RegistryGraphContract } from './registryContract';
import { mapSignalsToTaxonomy, taxonomyLabel, type FailureTaxonomy } from './failureTaxonomy';

export interface ExplainSystemStateInputs {
  graph: SystemGraphPayload | null;
  priority: PriorityArtifactLoadResult | null;
  contract: RegistryGraphContract;
}

export interface ExplainTopFix {
  rank: number;
  system_id: string;
  is_registry_backed: boolean;
  what_to_fix: string;
  why_now: string;
}

export interface ExplainSystemStateResult {
  trust_state: string;
  generated_at: string;
  root_cause: {
    system_id: string | null;
    taxonomy: FailureTaxonomy;
    explanation: string;
  };
  propagation_path: string[];
  top_three_fix_targets: ExplainTopFix[];
  next_safe_action: string;
  missing_data: string[];
  notes: string[];
}

const UNAVAILABLE = 'unavailable';

function describeRootCause(graph: SystemGraphPayload | null): {
  system_id: string | null;
  taxonomy: FailureTaxonomy;
  explanation: string;
} {
  if (!graph) {
    return {
      system_id: null,
      taxonomy: 'unknown',
      explanation: 'graph artifact missing — root cause cannot be determined',
    };
  }

  const failurePath = graph.failure_path ?? [];
  if (failurePath.length === 0) {
    return {
      system_id: null,
      taxonomy: 'none',
      explanation: 'no failure path declared by graph artifact',
    };
  }

  // Root cause = first node in the failure path that has no upstream blocker
  // also on the failure path. If we cannot establish that, return the first
  // failure-path node with explicit Unknown taxonomy on the explanation.
  const rootCandidates = failurePath.filter((systemId) => {
    const node = graph.nodes.find((n) => n.system_id === systemId);
    if (!node) return false;
    const upstreamBlockers = (node.upstream_blockers ?? []).filter((id) => failurePath.includes(id));
    return upstreamBlockers.length === 0;
  });

  if (rootCandidates.length === 0) {
    const fallback = failurePath[0];
    return {
      system_id: fallback,
      taxonomy: 'unknown',
      explanation: `root cause indeterminate; first failure-path node is ${fallback} but every node has upstream blockers also on the path`,
    };
  }

  const rootId = rootCandidates[0];
  const rootNode = graph.nodes.find((n) => n.system_id === rootId);
  const taxonomy = rootNode
    ? mapSignalsToTaxonomy([
        ...(rootNode.failed_evals ?? []),
        ...(rootNode.trace_gaps ?? []),
        ...(rootNode.missing_artifacts ?? []),
        ...(rootNode.trust_gap_signals ?? []),
      ])
    : 'unknown';

  const reason = rootNode?.why_blocked ?? 'no detailed blocker reason recorded on root node';
  return {
    system_id: rootId,
    taxonomy,
    explanation: `${rootId}: ${reason} (taxonomy: ${taxonomyLabel(taxonomy)})`,
  };
}

function topThreeFixes(
  priority: PriorityArtifactLoadResult | null,
  contract: RegistryGraphContract,
): ExplainTopFix[] {
  if (!priority || priority.state !== 'ok' || !priority.payload) return [];
  const top: RankedSystem[] = (priority.payload.top_5 ?? []).slice(0, 3);
  return top.map((row) => ({
    rank: row.rank,
    system_id: row.system_id,
    is_registry_backed: contract.allowed_active_node_ids.includes(row.system_id),
    what_to_fix: row.action,
    why_now: row.why_now,
  }));
}

function nextSafeAction(
  priority: PriorityArtifactLoadResult | null,
  contract: RegistryGraphContract,
): string {
  if (!priority || priority.state !== 'ok' || !priority.payload) {
    return 'regenerate priority artifact: run scripts/build_tls_dependency_priority.py and scripts/build_dashboard_3ls_with_tls.py';
  }
  const first = priority.payload.top_5?.[0];
  if (!first) return 'priority artifact has no top_5 entries — verify upstream pipeline output';
  const registryBacked = contract.allowed_active_node_ids.includes(first.system_id);
  if (!registryBacked) {
    return `Top 1 (${first.system_id}) is not a registry-active system; treat as text-only recommendation and verify scope before acting`;
  }
  return `address ${first.system_id}: ${first.action}`;
}

function missingData(
  graph: SystemGraphPayload | null,
  priority: PriorityArtifactLoadResult | null,
  contract: RegistryGraphContract,
): string[] {
  const out: string[] = [];
  if (!graph) out.push('system graph payload missing');
  if (!priority) out.push('priority load result missing');
  else if (priority.state === 'missing') out.push(`priority artifact missing: ${priority.reason ?? 'unknown'}`);
  else if (priority.state === 'invalid_schema') out.push(`priority artifact invalid: ${priority.reason ?? 'shape_mismatch'}`);
  else if (priority.state === 'stale') out.push(`priority artifact stale: generated_at=${priority.generated_at ?? UNAVAILABLE}`);
  if (contract.allowed_active_node_ids.length === 0) out.push('registry contract empty — registry artifact missing or unreadable');
  return out;
}

export function explainSystemState(inputs: ExplainSystemStateInputs): ExplainSystemStateResult {
  const { graph, priority, contract } = inputs;
  const root = describeRootCause(graph);
  const top = topThreeFixes(priority, contract);
  const next = nextSafeAction(priority, contract);
  const missing = missingData(graph, priority, contract);
  const propagation = graph?.failure_path ?? [];
  const notes: string[] = [];
  if (priority?.state === 'blocked_signal') notes.push('priority artifact carries control_signal=blocked_signal');
  if (priority?.state === 'freeze_signal') notes.push('priority artifact carries control_signal=freeze_signal');
  if (top.some((row) => !row.is_registry_backed)) notes.push('one or more top-3 entries are non-registry (not in registry-active set); render them as text-only recommendations, not graph nodes');
  return {
    trust_state: graph?.trust_posture ?? 'unknown',
    generated_at: graph?.generated_at ?? priority?.generated_at ?? UNAVAILABLE,
    root_cause: root,
    propagation_path: propagation,
    top_three_fix_targets: top,
    next_safe_action: next,
    missing_data: missing,
    notes,
  };
}
