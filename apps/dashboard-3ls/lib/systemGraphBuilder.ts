import { loadArtifact } from '@/lib/artifactLoader';
import type { SystemGraphEdge, SystemGraphNode, SystemGraphPayload, GraphLayer, GraphState, NodeSourceType } from '@/lib/systemGraph';

const ARTIFACTS = {
  registryGraph: 'artifacts/tls/system_registry_dependency_graph.json',
  graphValidation: 'artifacts/tls/system_graph_validation_report.json',
  priority: 'artifacts/system_dependency_priority_report.json',
  trustGap: 'artifacts/tls/system_trust_gap_report.json',
  candidateClass: 'artifacts/tls/system_candidate_classification.json',
  evidenceAttachment: 'artifacts/tls/system_evidence_attachment.json',
} as const;

function asArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function toLayer(systemId: string, canonicalLoop: string[], overlays: string[], classification?: string): GraphLayer {
  if (canonicalLoop.includes(systemId)) return 'core';
  if (overlays.includes(systemId)) return 'overlay';
  if (classification === 'support_capability') return 'support';
  if (classification === 'h_slice' || classification === 'r_slice' || classification === 'future') return 'candidate';
  return 'unknown';
}

function mapTrustToGraphState(trustPosture: string, missingGraph: boolean): GraphState {
  if (missingGraph) return 'degraded_signal';
  if (trustPosture === 'blocked_signal') return 'blocked_signal';
  if (trustPosture === 'freeze_signal') return 'freeze_signal';
  if (trustPosture === 'caution_signal') return 'caution_signal';
  return 'trusted_signal';
}

export function buildSystemGraphPayload(nowIso: string = new Date().toISOString()): SystemGraphPayload {
  const warnings: string[] = [];
  const missingArtifacts: string[] = [];

  const registry = loadArtifact<Record<string, unknown>>(ARTIFACTS.registryGraph);
  const validation = loadArtifact<Record<string, unknown>>(ARTIFACTS.graphValidation);
  const priority = loadArtifact<Record<string, unknown>>(ARTIFACTS.priority);
  const trustGap = loadArtifact<Record<string, unknown>>(ARTIFACTS.trustGap);
  const candidates = loadArtifact<Record<string, unknown>>(ARTIFACTS.candidateClass);
  const evidence = loadArtifact<Record<string, unknown>>(ARTIFACTS.evidenceAttachment);

  for (const [key, path] of Object.entries(ARTIFACTS)) {
    const has = (key === 'registryGraph' && registry) || (key === 'graphValidation' && validation) || (key === 'priority' && priority) || (key === 'trustGap' && trustGap) || (key === 'candidateClass' && candidates) || (key === 'evidenceAttachment' && evidence);
    if (!has) {
      missingArtifacts.push(path);
      warnings.push(`missing_artifact:${path}`);
    }
  }

  const activeSystems = asArray<Record<string, unknown>>(registry?.active_systems);
  const canonicalLoop = asArray<string>(registry?.canonical_loop);
  const overlays = asArray<string>(registry?.canonical_overlays);
  const trustBySystem = new Map(asArray<Record<string, unknown>>(trustGap?.systems).map((row) => [String(row.system_id), { trust_state: String(row.trust_state ?? 'unknown_signal'), failing_signals: asArray<string>(row.failing_signals) }]));
  const candidateBySystem = new Map(asArray<Record<string, unknown>>(candidates?.candidates).map((row) => [String(row.system_id), String(row.classification ?? 'unknown')]));
  const evidenceBySystem = new Map(asArray<Record<string, unknown>>(evidence?.systems).map((row) => [String(row.system_id), row]));
  const priorityRows = asArray<Record<string, unknown>>(priority?.top_5);
  const focusTop = priorityRows.slice(0, 3).map((row) => String(row.system_id));

  let trustPosture = 'trusted_signal';
  if (priorityRows.some((row) => String(row.trust_state) === 'blocked_signal')) trustPosture = 'blocked_signal';
  else if (priorityRows.some((row) => String(row.trust_state) === 'freeze_signal')) trustPosture = 'freeze_signal';
  else if (warnings.length > 0) trustPosture = 'caution_signal';

  const failurePathFromValidation = asArray<string>(validation?.failure_path);
  const failurePath = failurePathFromValidation.length > 0 ? failurePathFromValidation : trustPosture === 'freeze_signal' || trustPosture === 'blocked_signal' ? canonicalLoop.filter((systemId) => {
    const trust = trustBySystem.get(systemId)?.trust_state ?? 'trusted_signal';
    return trust === 'blocked_signal' || trust === 'freeze_signal';
  }) : [];
  const focusSystems = failurePath.length > 0 ? failurePath.slice(0, 3) : focusTop;

  const systemIds = new Set<string>();
  for (const row of activeSystems) systemIds.add(String(row.system_id));
  for (const id of focusSystems) systemIds.add(id);
  for (const id of canonicalLoop) systemIds.add(id);
  for (const id of overlays) systemIds.add(id);

  const nodes: SystemGraphNode[] = Array.from(systemIds).map((systemId) => {
    const registryRow = activeSystems.find((row) => String(row.system_id) === systemId) ?? null;
    const upstream = asArray<string>(registryRow?.upstream);
    const downstream = asArray<string>(registryRow?.downstream);
    const trust = trustBySystem.get(systemId);
    const classification = candidateBySystem.get(systemId);
    const hasEvidence = evidenceBySystem.has(systemId);
    const sourceType: NodeSourceType = registryRow ? 'artifact_store' : hasEvidence ? 'derived' : 'missing';
    const nodeWarnings = [!registryRow, !trust, !hasEvidence].filter(Boolean).length;
    return {
      system_id: systemId,
      label: systemId,
      layer: toLayer(systemId, canonicalLoop, overlays, classification),
      role: String(registryRow?.purpose ?? classification ?? 'unknown_role'),
      trust_state: trust?.trust_state ?? 'unknown_signal',
      artifact_backed_percent: sourceType === 'artifact_store' ? 100 : sourceType === 'derived' ? 50 : 0,
      source_type: sourceType,
      trust_gap_signals: trust?.failing_signals ?? [],
      upstream,
      downstream,
      source_artifact_refs: [ARTIFACTS.registryGraph, ARTIFACTS.trustGap, ARTIFACTS.evidenceAttachment],
      warning_count: nodeWarnings,
      is_focus: focusSystems.includes(systemId),
      is_fallback_backed: sourceType === 'missing',
      is_disconnected: upstream.length === 0 && downstream.length === 0,
    };
  });

  const edges: SystemGraphEdge[] = [];
  const seen = new Set<string>();
  for (const node of nodes) {
    for (const to of node.downstream) {
      const key = `${node.system_id}->${to}`;
      if (seen.has(key)) continue;
      seen.add(key);
      const target = nodes.find((n) => n.system_id === to);
      edges.push({
        from: node.system_id,
        to,
        edge_type: node.layer === 'overlay' || target?.layer === 'overlay' ? 'overlay' : node.layer === 'support' || target?.layer === 'support' ? 'support' : node.layer === 'candidate' || target?.layer === 'candidate' ? 'candidate' : 'dependency',
        source_type: node.source_type,
        source_artifact_ref: ARTIFACTS.registryGraph,
        confidence: node.source_type === 'artifact_store' ? 1 : 0.6,
        is_failure_path: failurePath.includes(node.system_id) && failurePath.includes(to),
        is_broken: !target,
      });
    }
  }

  return {
    graph_state: mapTrustToGraphState(trustPosture, !registry),
    generated_at: String(priority?.generated_at ?? nowIso),
    source_mix: {
      artifact_store: nodes.filter((n) => n.source_type === 'artifact_store').length,
      repo_registry: nodes.filter((n) => n.source_type === 'repo_registry').length,
      derived: nodes.filter((n) => n.source_type === 'derived').length,
      stub_fallback: nodes.filter((n) => n.source_type === 'stub_fallback').length,
      missing: nodes.filter((n) => n.source_type === 'missing').length,
    },
    trust_posture: trustPosture,
    nodes,
    edges,
    focus_systems: focusSystems,
    failure_path: failurePath,
    missing_artifacts: missingArtifacts,
    warnings,
    replay_commands: ['python scripts/build_tls_dependency_priority.py --candidates H01,RFX,HOP,MET,METS --fail-if-missing', 'python scripts/build_dashboard_3ls_with_tls.py'],
  };
}
