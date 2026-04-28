import { loadArtifact } from '@/lib/artifactLoader';
import {
  deriveDebugStatus,
  type SystemGraphEdge,
  type SystemGraphNode,
  type SystemGraphPayload,
  type GraphLayer,
  type GraphState,
  type NodeSourceType,
} from '@/lib/systemGraph';
import { loadRegistryContract, validateGraphAgainstContract } from '@/lib/registryContract';

const ARTIFACTS = {
  registryGraph: 'artifacts/tls/system_registry_dependency_graph.json',
  graphValidation: 'artifacts/tls/system_graph_validation_report.json',
  priority: 'artifacts/system_dependency_priority_report.json',
  trustGap: 'artifacts/tls/system_trust_gap_report.json',
  candidateClass: 'artifacts/tls/system_candidate_classification.json',
  evidenceAttachment: 'artifacts/tls/system_evidence_attachment.json',
} as const;

const SCHEMA_PATHS_BY_ARTIFACT: Record<string, string> = {
  [ARTIFACTS.registryGraph]: 'schemas/tls/system_registry_dependency_graph.schema.json',
  [ARTIFACTS.graphValidation]: 'schemas/tls/system_graph_validation_report.schema.json',
  [ARTIFACTS.priority]: 'schemas/tls/system_dependency_priority_report.schema.json',
  [ARTIFACTS.trustGap]: 'schemas/tls/system_trust_gap_report.schema.json',
  [ARTIFACTS.candidateClass]: 'schemas/tls/system_candidate_classification.schema.json',
  [ARTIFACTS.evidenceAttachment]: 'schemas/tls/system_evidence_attachment.schema.json',
};

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

  // Registry contract is the single allowlist for graph nodes. Everything
  // else (roadmap labels, candidate IDs, prompt labels) must NOT become
  // a graph node. The contract is parsed from the registry artifact so
  // the dashboard never invents systems.
  const contract = loadRegistryContract();
  const allowedActive = new Set(contract.allowed_active_node_ids);

  const activeSystems = asArray<Record<string, unknown>>(registry?.active_systems);
  const canonicalLoop = asArray<string>(registry?.canonical_loop);
  const overlays = asArray<string>(registry?.canonical_overlays);
  const trustBySystem = new Map(asArray<Record<string, unknown>>(trustGap?.systems).map((row) => [String(row.system_id), { trust_state: String(row.trust_state ?? 'unknown_signal'), failing_signals: asArray<string>(row.failing_signals), gap_count: typeof row.gap_count === 'number' ? row.gap_count : null }]));
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
  const rejectedNodeIds: string[] = [];
  const acceptIfAllowed = (id: string) => {
    if (!id) return;
    if (allowedActive.size > 0 && !allowedActive.has(id)) {
      // Registry contract rejects non-registry-active labels (e.g. H01,
      // RFX, MET, roadmap bundle IDs). Track them so the warnings panel
      // can surface what was filtered.
      if (!rejectedNodeIds.includes(id)) rejectedNodeIds.push(id);
      return;
    }
    systemIds.add(id);
  };
  for (const row of activeSystems) acceptIfAllowed(String(row.system_id));
  for (const id of focusSystems) acceptIfAllowed(id);
  for (const id of canonicalLoop) acceptIfAllowed(id);
  for (const id of overlays) acceptIfAllowed(id);
  if (rejectedNodeIds.length > 0) {
    warnings.push(`registry_contract_rejected_nodes:${rejectedNodeIds.join(',')}`);
  }

  const generatedAt = String(priority?.generated_at ?? nowIso);
  const replayCommands: string[] = [
    'python scripts/build_tls_dependency_priority.py --candidates H01,RFX,HOP,MET,METS --fail-if-missing',
    'python scripts/build_dashboard_3ls_with_tls.py',
  ];

  const nodes: SystemGraphNode[] = Array.from(systemIds).map((systemId) => {
    const registryRow = activeSystems.find((row) => String(row.system_id) === systemId) ?? null;
    const upstream = asArray<string>(registryRow?.upstream);
    const downstream = asArray<string>(registryRow?.downstream);
    const trust = trustBySystem.get(systemId);
    const classification = candidateBySystem.get(systemId);
    const hasEvidence = evidenceBySystem.has(systemId);
    const sourceType: NodeSourceType = registryRow ? 'artifact_store' : hasEvidence ? 'derived' : 'missing';
    const nodeWarnings = [!registryRow, !trust, !hasEvidence].filter(Boolean).length;
    const failingSignals = trust?.failing_signals ?? [];
    const isDisconnected = upstream.length === 0 && downstream.length === 0;
    const sourceArtifactRefs: string[] = [];
    if (registryRow) sourceArtifactRefs.push(ARTIFACTS.registryGraph);
    if (trust) sourceArtifactRefs.push(ARTIFACTS.trustGap);
    if (hasEvidence) sourceArtifactRefs.push(ARTIFACTS.evidenceAttachment);
    const schemaPaths = sourceArtifactRefs.map((ref) => SCHEMA_PATHS_BY_ARTIFACT[ref]).filter(Boolean);
    const upstreamBlockers = upstream.filter((id) => {
      if (failurePath.includes(id)) return true;
      const t = trustBySystem.get(id)?.trust_state;
      return t === 'blocked_signal' || t === 'freeze_signal';
    });
    const trustState = trust?.trust_state ?? 'unknown_signal';
    const baseNode = {
      system_id: systemId,
      label: systemId,
      trust_state: trustState,
      source_type: sourceType,
      trust_gap_signals: failingSignals,
      is_disconnected: isDisconnected,
    };
    const debugStatus = deriveDebugStatus(baseNode);
    const whyBlockedReasons: string[] = [];
    if (upstreamBlockers.length > 0) whyBlockedReasons.push(`upstream blocked: ${upstreamBlockers.join(', ')}`);
    if (failingSignals.length > 0) whyBlockedReasons.push(`failing signals: ${failingSignals.join(', ')}`);
    if (sourceType === 'missing') whyBlockedReasons.push('source artifact missing');
    if ((sourceType as NodeSourceType) === 'stub_fallback') whyBlockedReasons.push('only stub fallback present');
    const isBlockingStatus = debugStatus === 'BLOCKING' || debugStatus === 'FAILED' || debugStatus === 'MISSING' || debugStatus === 'FALLBACK';
    return {
      system_id: systemId,
      label: systemId,
      layer: toLayer(systemId, canonicalLoop, overlays, classification),
      role: String(registryRow?.purpose ?? classification ?? 'unknown_role'),
      trust_state: trustState,
      artifact_backed_percent: sourceType === 'artifact_store' ? 100 : sourceType === 'derived' ? 50 : 0,
      source_type: sourceType,
      trust_gap_signals: failingSignals,
      upstream,
      downstream,
      source_artifact_refs: sourceArtifactRefs.length > 0 ? sourceArtifactRefs : [ARTIFACTS.registryGraph],
      warning_count: nodeWarnings,
      is_focus: focusSystems.includes(systemId),
      is_fallback_backed: sourceType === 'missing',
      is_disconnected: isDisconnected,
      debug_status: debugStatus,
      why_blocked: isBlockingStatus && whyBlockedReasons.length > 0 ? whyBlockedReasons.join('; ') : null,
      missing_artifacts: sourceType === 'missing'
        ? [ARTIFACTS.registryGraph]
        : !trust
          ? [ARTIFACTS.trustGap]
          : [],
      failed_evals: failingSignals,
      trace_gaps: !hasEvidence ? ['evidence_attachment_missing'] : [],
      upstream_blockers: upstreamBlockers,
      downstream_dependents: downstream,
      schema_paths: schemaPaths,
      producing_script: registryRow ? replayCommands[0] : null,
      last_recompute: generatedAt,
    };
  });

  const edges: SystemGraphEdge[] = [];
  const seen = new Set<string>();
  for (const node of nodes) {
    for (const to of node.downstream) {
      // Drop edges whose endpoint is not in the registry contract.
      // Otherwise the graph could carry an edge to a label like H01
      // even if the node was rejected.
      if (allowedActive.size > 0 && !allowedActive.has(to)) {
        if (!rejectedNodeIds.includes(to)) rejectedNodeIds.push(to);
        continue;
      }
      const key = `${node.system_id}->${to}`;
      if (seen.has(key)) continue;
      seen.add(key);
      const target = nodes.find((n) => n.system_id === to);
      const isFailureEdge = failurePath.includes(node.system_id) && failurePath.includes(to);
      const edgeType = node.layer === 'overlay' || target?.layer === 'overlay'
        ? 'overlay'
        : node.layer === 'support' || target?.layer === 'support'
          ? 'support'
          : node.layer === 'candidate' || target?.layer === 'candidate'
            ? 'candidate'
            : 'dependency';
      const sourceType = node.source_type;
      edges.push({
        from: node.system_id,
        to,
        edge_type: edgeType,
        source_type: sourceType,
        source_artifact_ref: ARTIFACTS.registryGraph,
        confidence: sourceType === 'artifact_store' ? 1 : 0.6,
        is_failure_path: isFailureEdge,
        is_broken: !target,
        dependency_type: edgeType,
        artifact_backed: sourceType === 'artifact_store' || sourceType === 'repo_registry',
        last_validated: validation ? generatedAt : null,
        related_signal: isFailureEdge
          ? 'failure_path_signal'
          : target?.failed_evals?.[0]
            ? `target_failing:${target.failed_evals[0]}`
            : null,
      });
    }
  }

  // Final defense-in-depth: assert the produced payload contains only
  // registry-active node ids. If any unknown / future / demoted leaks
  // through (e.g. via a code path we missed), record a warning and drop
  // it from the payload. Fail-closed.
  const contractValidation = validateGraphAgainstContract(contract, { nodes, edges });
  let safeNodes = nodes;
  let safeEdges = edges;
  if (!contractValidation.ok) {
    for (const finding of contractValidation.findings) {
      warnings.push(`graph_contract_violation:${finding.rule_id}:${finding.offending.join(',')}`);
    }
    const offendingIds = new Set<string>(
      contractValidation.findings
        .filter((f) => f.rule_id === 'reject_unknown_node' || f.rule_id === 'reject_future_in_default' || f.rule_id === 'reject_demoted_in_default')
        .flatMap((f) => f.offending),
    );
    if (offendingIds.size > 0) {
      safeNodes = safeNodes.filter((node) => !offendingIds.has(node.system_id));
      safeEdges = safeEdges.filter((edge) => !offendingIds.has(edge.from) && !offendingIds.has(edge.to));
    }
    const unknownEdgeKeys = new Set<string>(
      contractValidation.findings.filter((f) => f.rule_id === 'reject_unknown_edge').flatMap((f) => f.offending),
    );
    if (unknownEdgeKeys.size > 0) {
      safeEdges = safeEdges.filter((edge) => !unknownEdgeKeys.has(`${edge.from}->${edge.to}`));
    }
  }

  return {
    graph_state: mapTrustToGraphState(trustPosture, !registry),
    generated_at: generatedAt,
    source_mix: {
      artifact_store: safeNodes.filter((n) => n.source_type === 'artifact_store').length,
      repo_registry: safeNodes.filter((n) => n.source_type === 'repo_registry').length,
      derived: safeNodes.filter((n) => n.source_type === 'derived').length,
      stub_fallback: safeNodes.filter((n) => n.source_type === 'stub_fallback').length,
      missing: safeNodes.filter((n) => n.source_type === 'missing').length,
    },
    trust_posture: trustPosture,
    nodes: safeNodes,
    edges: safeEdges,
    focus_systems: focusSystems.filter((id) => allowedActive.size === 0 || allowedActive.has(id)),
    failure_path: failurePath.filter((id) => allowedActive.size === 0 || allowedActive.has(id)),
    missing_artifacts: missingArtifacts,
    warnings,
    replay_commands: replayCommands,
  };
}
