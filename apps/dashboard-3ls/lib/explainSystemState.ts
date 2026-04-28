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
    /** Short, human-readable reason. Not a list of signals. */
    reason: string;
    explanation: string;
    /** True when root_cause.system_id and reason came from a real artifact. */
    artifact_backed: boolean;
  };
  /** Signals that contributed evidence to the root-cause classification. */
  missing_signals: string[];
  /** Downstream registry systems impacted by the root cause / failure path. */
  downstream_impact: string[];
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
  reason: string;
  explanation: string;
  artifact_backed: boolean;
} {
  if (!graph) {
    return {
      system_id: null,
      taxonomy: 'unknown',
      reason: 'graph artifact missing',
      explanation: 'graph artifact missing — root cause cannot be determined',
      artifact_backed: false,
    };
  }

  const failurePath = graph.failure_path ?? [];
  if (failurePath.length === 0) {
    return {
      system_id: null,
      taxonomy: 'none',
      reason: 'no failure path declared',
      explanation: 'no failure path declared by graph artifact',
      artifact_backed: true,
    };
  }

  // Root cause = first node in the failure path that has no upstream blocker
  // also on the failure path. If we cannot establish that, return root cause
  // Unknown rather than guessing — the operator must know it is undetermined.
  const rootCandidates = failurePath.filter((systemId) => {
    const node = graph.nodes.find((n) => n.system_id === systemId);
    if (!node) return false;
    const upstreamBlockers = (node.upstream_blockers ?? []).filter((id) => failurePath.includes(id));
    return upstreamBlockers.length === 0;
  });

  if (rootCandidates.length === 0) {
    return {
      system_id: null,
      taxonomy: 'unknown',
      reason: 'every failure-path node has upstream blockers also on the path',
      explanation: 'root cause indeterminate from current graph; observed blockers are circular or insufficient — see propagation path and missing_signals separately',
      artifact_backed: false,
    };
  }

  const rootId = rootCandidates[0];
  const rootNode = graph.nodes.find((n) => n.system_id === rootId);
  const evidenceSignals = rootNode
    ? [
        ...(rootNode.failed_evals ?? []),
        ...(rootNode.trace_gaps ?? []),
        ...(rootNode.missing_artifacts ?? []),
        ...(rootNode.trust_gap_signals ?? []),
      ]
    : [];
  const taxonomy = mapSignalsToTaxonomy(evidenceSignals);
  const reason = rootNode?.why_blocked ?? 'no detailed blocker reason recorded on root node';
  return {
    system_id: rootId,
    taxonomy,
    reason,
    explanation: `${rootId}: ${reason} (taxonomy: ${taxonomyLabel(taxonomy)})`,
    artifact_backed: !!rootNode && evidenceSignals.length > 0,
  };
}

/** Collect missing-signal evidence across every failure-path node. These are
 * NOT root cause; they are the signals the failure path lights up so the
 * operator can reason about what evidence to gather. */
function collectMissingSignals(graph: SystemGraphPayload | null): string[] {
  if (!graph) return [];
  const failurePath = graph.failure_path ?? [];
  if (failurePath.length === 0) return [];
  const signals = new Set<string>();
  for (const systemId of failurePath) {
    const node = graph.nodes.find((n) => n.system_id === systemId);
    if (!node) continue;
    for (const s of node.failed_evals ?? []) signals.add(s);
    for (const s of node.trace_gaps ?? []) signals.add(s);
    for (const s of node.missing_artifacts ?? []) signals.add(`missing_artifact:${s}`);
    for (const s of node.trust_gap_signals ?? []) signals.add(s);
  }
  return Array.from(signals);
}

/** Downstream impact = registry systems on the failure path other than the
 * root cause. Operators use this to scope blast radius. */
function downstreamImpactFromGraph(graph: SystemGraphPayload | null, rootId: string | null): string[] {
  if (!graph) return [];
  const failurePath = graph.failure_path ?? [];
  return failurePath.filter((id) => id !== rootId);
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
  const missingSignals = collectMissingSignals(graph);
  const downstreamImpact = downstreamImpactFromGraph(graph, root.system_id);
  const top = topThreeFixes(priority, contract);
  const next = nextSafeAction(priority, contract);
  const missing = missingData(graph, priority, contract);
  const propagation = graph?.failure_path ?? [];
  const notes: string[] = [];
  if (priority?.state === 'blocked_signal') notes.push('priority artifact carries control_signal=blocked_signal');
  if (priority?.state === 'freeze_signal') notes.push('priority artifact carries control_signal=freeze_signal');
  if (priority?.state === 'stale') notes.push('priority artifact stale: top-3 fix targets reflect last-known ranking only');
  if (priority?.state === 'invalid_timestamp') notes.push('priority artifact missing or unparseable generated_at — fail-closed; regenerate before acting');
  if (priority?.state === 'future_timestamp') notes.push('priority artifact generated_at in the future — fail-closed; regenerate before acting');
  if (top.some((row) => !row.is_registry_backed)) notes.push('one or more top-3 entries are non-registry (not in registry-active set); render them as text-only recommendations, not graph nodes');
  return {
    trust_state: graph?.trust_posture ?? 'unknown',
    generated_at: graph?.generated_at ?? priority?.generated_at ?? UNAVAILABLE,
    root_cause: root,
    missing_signals: missingSignals,
    downstream_impact: downstreamImpact,
    propagation_path: propagation,
    top_three_fix_targets: top,
    next_safe_action: next,
    missing_data: missing,
    notes,
  };
}
