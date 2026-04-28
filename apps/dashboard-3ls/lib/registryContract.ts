// D3L-REGISTRY-01 — Registry contract parser.
//
// Single source of truth for which system_ids the dashboard is allowed to
// render as graph nodes. Reads the parsed registry artifact (produced by
// scripts/build_system_registry_artifact.py) at
//   artifacts/tls/system_registry_dependency_graph.json
// and exposes contracts that downstream graph/UI code consults to fail-closed
// on unknown / non-system labels (H01, D3L-FIX-*, TLS-BND-*, roadmap labels).
//
// Hard rule: a graph node is admissible only if its system_id appears in the
// registry. Roadmap labels, prompt labels, batch IDs, candidate labels,
// red-team report IDs, etc. are NEVER nodes.

import { loadArtifact } from './artifactLoader';

export type RegistryClassification =
  | 'active'
  | 'future'
  | 'demoted'
  | 'deprecated'
  | 'merged'
  | 'unknown';

export interface RegistrySystemRow {
  system_id: string;
  status: string;
  classification: RegistryClassification;
  purpose: string;
  upstream: string[];
  downstream: string[];
  artifacts_owned: string[];
  primary_code_paths: string[];
}

export interface RegistryGraphContract {
  /** All registry-active system IDs, the only admissible default graph nodes. */
  allowed_active_node_ids: string[];
  /** Future / placeholder system IDs (only render when an explicit layer is enabled). */
  allowed_future_node_ids: string[];
  /** Demoted / deprecated / merged system IDs (only render in support/deprecated view). */
  demoted_or_deprecated_ids: string[];
  /**
   * Examples of labels that MUST NOT become graph nodes. These are documented
   * as forbidden so red-team tests can assert rejection.
   */
  forbidden_unknown_node_examples: string[];
  /** Active system rows, indexed by system_id for fast lookup. */
  active_systems: RegistrySystemRow[];
  /** Future / placeholder rows. */
  future_systems: RegistrySystemRow[];
  /** Demoted / deprecated rows. */
  demoted_systems: RegistrySystemRow[];
  /** Canonical-loop ordering for the default graph row. */
  canonical_loop: string[];
  /** Canonical overlay system IDs (REP, LIN, OBS, SLO). */
  canonical_overlays: string[];
  /** Default graph rows. Each row is registry-backed only. */
  graph_rows: GraphRowDefinition[];
  /** Edge classes used by the graph renderer. */
  edge_classes: EdgeClassDefinition[];
  /** Validation rules the contract must enforce. */
  validation_rules: ValidationRule[];
}

export interface GraphRowDefinition {
  key: string;
  label: string;
  description: string;
  expected_systems: string[];
}

export interface EdgeClassDefinition {
  key: string;
  label: string;
  visibility: 'default' | 'overlay' | 'failure_only' | 'full_only';
  description: string;
}

export interface ValidationRule {
  rule_id: string;
  description: string;
}

export interface RegistryValidationFinding {
  rule_id: string;
  severity: 'error' | 'warning';
  detail: string;
  offending: string[];
}

export interface RegistryValidationResult {
  ok: boolean;
  findings: RegistryValidationFinding[];
}

interface RawGraphArtifactRow {
  system_id?: unknown;
  status?: unknown;
  purpose?: unknown;
  upstream?: unknown;
  downstream?: unknown;
  artifacts_owned?: unknown;
  primary_code_paths?: unknown;
}

interface RawGraphArtifact {
  active_systems?: RawGraphArtifactRow[];
  future_systems?: RawGraphArtifactRow[];
  merged_or_demoted?: RawGraphArtifactRow[];
  canonical_loop?: unknown;
  canonical_overlays?: unknown;
}

export const REGISTRY_GRAPH_ARTIFACT_PATH =
  'artifacts/tls/system_registry_dependency_graph.json';

/**
 * Default registry-active fixture. Test code uses this as expected output
 * when the parsed artifact matches; it is NOT the authority — the registry
 * artifact remains canonical and the parser must agree with it.
 */
export const EXPECTED_ACTIVE_SYSTEMS_FIXTURE: ReadonlyArray<string> = [
  'AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL',
  'REP', 'LIN', 'OBS', 'SLO',
  'CTX', 'PRM', 'POL', 'TLC', 'RIL', 'FRE',
  'RAX', 'RSM', 'CAP', 'SEC',
  'JDX', 'JSX', 'PRA', 'GOV', 'MAP', 'HOP',
];

/**
 * Examples of labels that MUST NOT be rendered as graph nodes. These are
 * roadmap / batch / candidate / prompt / fix-loop labels — not system owners.
 */
export const FORBIDDEN_UNKNOWN_NODE_EXAMPLES: ReadonlyArray<string> = [
  'H01',
  'RFX',
  'MET',
  'METS',
  'D3L-FIX-01',
  'D3L-FIX-02',
  'TLS-BND-01',
  'TLS-BND-02',
  'TLS-FIX-EVL',
  'TLS-04',
  'TLS-06',
  'BUNDLE-01',
  'BUNDLE-02',
  'BUNDLE-03',
  'roadmap_label',
  'prompt_label',
  'red_team_report_id',
];

const DEFAULT_GRAPH_ROWS: GraphRowDefinition[] = [
  {
    key: 'overlay_proof',
    label: 'Trust / Proof Overlays',
    description: 'replay, lineage, observability, slo overlays',
    expected_systems: ['REP', 'LIN', 'OBS', 'SLO'],
  },
  {
    key: 'core_loop',
    label: 'Core Operating Loop',
    description: 'AEX → PQX → EVL → TPA → CDE → SEL',
    expected_systems: ['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL'],
  },
  {
    key: 'input_routing_support',
    label: 'Input / Routing / Support',
    description: 'context, prompt, orchestration, interpretation, repair, policy, security, capacity, reconciliation, candidate signal, map',
    expected_systems: ['CTX', 'PRM', 'TLC', 'RIL', 'FRE', 'POL', 'SEC', 'CAP', 'RSM', 'RAX', 'MAP'],
  },
  {
    key: 'judgment_promotion',
    label: 'Judgment / Promotion / Certification',
    description: 'JDX → JSX, CDE → PRA → GOV → SEL',
    expected_systems: ['JDX', 'JSX', 'PRA', 'GOV'],
  },
  {
    key: 'extension',
    label: 'Active Specialized / Extension Systems',
    description: 'harness optimization substrate',
    expected_systems: ['HOP'],
  },
];

const DEFAULT_EDGE_CLASSES: EdgeClassDefinition[] = [
  { key: 'primary', label: 'primary', visibility: 'default', description: 'core loop dependency edges' },
  { key: 'overlay', label: 'overlay', visibility: 'overlay', description: 'overlay-influence edges' },
  { key: 'governance', label: 'governance', visibility: 'default', description: 'judgment/promotion/certification edges' },
  { key: 'failure_path', label: 'failure_path', visibility: 'failure_only', description: 'edges currently on the failure path' },
  { key: 'selected_context', label: 'selected_context', visibility: 'overlay', description: 'edges adjacent to a selected node' },
  { key: 'secondary', label: 'secondary', visibility: 'full_only', description: 'secondary support edges hidden by default' },
  { key: 'weak_observed', label: 'weak_observed', visibility: 'full_only', description: 'low-confidence observed edges hidden by default' },
];

const DEFAULT_VALIDATION_RULES: ValidationRule[] = [
  { rule_id: 'reject_unknown_node', description: 'graph payload may not contain a system_id absent from the registry contract' },
  { rule_id: 'reject_demoted_in_default', description: 'demoted/deprecated systems must not render in the default active graph' },
  { rule_id: 'reject_future_in_default', description: 'future placeholders must not render unless the future layer is enabled' },
  { rule_id: 'reject_roadmap_label_node', description: 'roadmap / batch / candidate labels (e.g. H01, D3L-FIX-*, TLS-BND-*) must never become nodes' },
  { rule_id: 'reject_unknown_edge', description: 'every edge endpoint must be a known registry node' },
  { rule_id: 'reject_dashboard_ranking', description: 'dashboard must not compute or re-order ranking; it consumes priority artifact verbatim' },
];

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((entry): entry is string => typeof entry === 'string');
}

function rowFromRaw(raw: RawGraphArtifactRow, fallbackClassification: RegistryClassification): RegistrySystemRow | null {
  if (!raw || typeof raw.system_id !== 'string') return null;
  const status = typeof raw.status === 'string' ? raw.status : 'unknown';
  const classification = classifyStatus(status, fallbackClassification);
  return {
    system_id: raw.system_id,
    status,
    classification,
    purpose: typeof raw.purpose === 'string' ? raw.purpose : '',
    upstream: asStringArray(raw.upstream),
    downstream: asStringArray(raw.downstream),
    artifacts_owned: asStringArray(raw.artifacts_owned),
    primary_code_paths: asStringArray(raw.primary_code_paths),
  };
}

function classifyStatus(status: string, fallback: RegistryClassification): RegistryClassification {
  const lower = status.toLowerCase();
  if (lower === 'active') return 'active';
  if (lower === 'future' || lower === 'placeholder') return 'future';
  if (lower === 'demoted') return 'demoted';
  if (lower === 'deprecated') return 'deprecated';
  if (lower === 'merged') return 'merged';
  return fallback;
}

/**
 * Parse the registry contract from the canonical registry artifact.
 *
 * Fail-closed: if the artifact is missing or malformed, return an empty
 * contract so the dashboard refuses to render synthetic nodes. Callers
 * (graph builder, API routes) must surface the missing-artifact warning
 * to the operator.
 */
export function parseRegistryContractFromArtifact(
  raw: RawGraphArtifact | null | undefined,
): RegistryGraphContract {
  const empty: RegistryGraphContract = {
    allowed_active_node_ids: [],
    allowed_future_node_ids: [],
    demoted_or_deprecated_ids: [],
    forbidden_unknown_node_examples: Array.from(FORBIDDEN_UNKNOWN_NODE_EXAMPLES),
    active_systems: [],
    future_systems: [],
    demoted_systems: [],
    canonical_loop: [],
    canonical_overlays: [],
    graph_rows: DEFAULT_GRAPH_ROWS,
    edge_classes: DEFAULT_EDGE_CLASSES,
    validation_rules: DEFAULT_VALIDATION_RULES,
  };
  if (!raw) return empty;

  const active: RegistrySystemRow[] = [];
  for (const row of raw.active_systems ?? []) {
    const parsed = rowFromRaw(row, 'active');
    if (parsed) active.push(parsed);
  }

  const future: RegistrySystemRow[] = [];
  for (const row of raw.future_systems ?? []) {
    const parsed = rowFromRaw(row, 'future');
    if (parsed) future.push(parsed);
  }

  const demoted: RegistrySystemRow[] = [];
  for (const row of raw.merged_or_demoted ?? []) {
    const parsed = rowFromRaw(row, 'demoted');
    if (parsed) demoted.push(parsed);
  }

  return {
    allowed_active_node_ids: active.map((row) => row.system_id),
    allowed_future_node_ids: future.map((row) => row.system_id),
    demoted_or_deprecated_ids: demoted.map((row) => row.system_id),
    forbidden_unknown_node_examples: Array.from(FORBIDDEN_UNKNOWN_NODE_EXAMPLES),
    active_systems: active,
    future_systems: future,
    demoted_systems: demoted,
    canonical_loop: asStringArray(raw.canonical_loop),
    canonical_overlays: asStringArray(raw.canonical_overlays),
    graph_rows: DEFAULT_GRAPH_ROWS,
    edge_classes: DEFAULT_EDGE_CLASSES,
    validation_rules: DEFAULT_VALIDATION_RULES,
  };
}

/**
 * Load the registry contract from disk. Returns an empty contract if the
 * artifact is missing — caller is responsible for surfacing the warning.
 */
export function loadRegistryContract(): RegistryGraphContract {
  const raw = loadArtifact<RawGraphArtifact>(REGISTRY_GRAPH_ARTIFACT_PATH);
  return parseRegistryContractFromArtifact(raw ?? null);
}

/** Returns true iff system_id is in the registry-active allowlist. */
export function isAllowedActiveNode(contract: RegistryGraphContract, systemId: string): boolean {
  return contract.allowed_active_node_ids.includes(systemId);
}

/** Returns true iff system_id is registry-known in any layer (active / future / demoted). */
export function isKnownRegistrySystem(contract: RegistryGraphContract, systemId: string): boolean {
  return (
    contract.allowed_active_node_ids.includes(systemId) ||
    contract.allowed_future_node_ids.includes(systemId) ||
    contract.demoted_or_deprecated_ids.includes(systemId)
  );
}

/**
 * Validate a candidate graph payload against the registry contract.
 * Used both at build time (graph builder rejects unknowns) and as a
 * red-team check on a freshly produced graph artifact.
 */
export function validateGraphAgainstContract(
  contract: RegistryGraphContract,
  graph: { nodes: Array<{ system_id: string }>; edges: Array<{ from: string; to: string }> },
  options: { allowFutureLayer?: boolean; allowDemotedLayer?: boolean } = {},
): RegistryValidationResult {
  const findings: RegistryValidationFinding[] = [];
  const seen = new Set<string>();
  const unknownNodes: string[] = [];
  const futureLeaks: string[] = [];
  const demotedLeaks: string[] = [];

  for (const node of graph.nodes) {
    const id = node.system_id;
    if (seen.has(id)) continue;
    seen.add(id);
    if (contract.allowed_active_node_ids.includes(id)) continue;
    if (contract.allowed_future_node_ids.includes(id)) {
      if (!options.allowFutureLayer) futureLeaks.push(id);
      continue;
    }
    if (contract.demoted_or_deprecated_ids.includes(id)) {
      if (!options.allowDemotedLayer) demotedLeaks.push(id);
      continue;
    }
    unknownNodes.push(id);
  }

  if (unknownNodes.length > 0) {
    findings.push({
      rule_id: 'reject_unknown_node',
      severity: 'error',
      detail: 'graph payload contains node ids absent from the system registry',
      offending: unknownNodes,
    });
  }
  if (futureLeaks.length > 0) {
    findings.push({
      rule_id: 'reject_future_in_default',
      severity: 'error',
      detail: 'future / placeholder systems leaked into default graph view',
      offending: futureLeaks,
    });
  }
  if (demotedLeaks.length > 0) {
    findings.push({
      rule_id: 'reject_demoted_in_default',
      severity: 'error',
      detail: 'demoted / deprecated systems leaked into default graph view',
      offending: demotedLeaks,
    });
  }

  const validIds = new Set([
    ...contract.allowed_active_node_ids,
    ...(options.allowFutureLayer ? contract.allowed_future_node_ids : []),
    ...(options.allowDemotedLayer ? contract.demoted_or_deprecated_ids : []),
  ]);
  const unknownEdges: string[] = [];
  for (const edge of graph.edges) {
    if (!validIds.has(edge.from) || !validIds.has(edge.to)) {
      unknownEdges.push(`${edge.from}->${edge.to}`);
    }
  }
  if (unknownEdges.length > 0) {
    findings.push({
      rule_id: 'reject_unknown_edge',
      severity: 'error',
      detail: 'edge endpoint references a non-registry system_id',
      offending: unknownEdges,
    });
  }

  return { ok: findings.length === 0, findings };
}

/**
 * Filter a candidate set (e.g. Top 3 ranking rows) into registry-backed
 * vs non-registry-backed entries. Non-registry entries must render as
 * text-only recommendations, never as graph nodes.
 */
export function partitionCandidatesByRegistry<T extends { system_id: string }>(
  contract: RegistryGraphContract,
  rows: T[],
): { registry_backed: T[]; non_registry: T[] } {
  const registry_backed: T[] = [];
  const non_registry: T[] = [];
  for (const row of rows) {
    if (contract.allowed_active_node_ids.includes(row.system_id)) {
      registry_backed.push(row);
    } else {
      non_registry.push(row);
    }
  }
  return { registry_backed, non_registry };
}
