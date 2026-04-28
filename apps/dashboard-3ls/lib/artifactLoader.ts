import fs from 'fs';
import path from 'path';

// Resolve the repo root that contains the artifacts/ directory.
//
// On Vercel, set REPO_ROOT to the absolute path of the monorepo root inside the
// serverless function bundle (e.g. /var/task) so artifact paths resolve correctly.
// In local dev and CI, process.cwd() is apps/dashboard-3ls, so ../.. is the repo root.
export function getRepoRoot(): string {
  if (process.env.REPO_ROOT) {
    return process.env.REPO_ROOT;
  }
  return path.resolve(process.cwd(), '../..');
}

export function loadArtifact<T>(relativePath: string): T | null {
  try {
    const fullPath = path.join(getRepoRoot(), relativePath);
    const raw = fs.readFileSync(fullPath, 'utf-8');
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// TLS-04 dependency-priority artifact loader (D3L-01).
//
// Strict load contract: dashboard MUST NOT compute ranking. All ranking is
// produced by the governed TLS pipeline upstream and read here as-is. The
// loader returns one of:
//   { state: 'ok', payload }              — schema-shape passed
//   { state: 'missing' }                  — file not present
//   { state: 'stale', generated_at}       — file present but older than threshold
//   { state: 'invalid_schema' }           — file present but did not match shape
//   { state: 'blocked_signal' }           — observer-safe halt signal from artifact
//   { state: 'freeze_signal' }            — observer-safe freeze signal from artifact
//
// Note: TLS produces signals only. Canonical owners (CDE/SEL/GOV) evaluate,
// enforce, and certify based on these signals; the dashboard never applies authority.
// ---------------------------------------------------------------------------

export type PriorityArtifactState =
  | 'ok'
  | 'missing'
  | 'stale'
  | 'invalid_schema'
  | 'blocked_signal'
  | 'freeze_signal';

export interface RankedSystem {
  rank: number;
  system_id: string;
  classification: string;
  score: number;
  action: string;
  why_now: string;
  trust_gap_signals: string[];
  dependencies: { upstream: string[]; downstream: string[] };
  unlocks: string[];
  finish_definition: string;
  next_prompt: string;
  trust_state: string;
  unknown_justification?: string;
}

export interface RequestedCandidateRow {
  requested_rank: number;
  global_rank?: number | null;
  system_id: string;
  classification: string;
  score?: number | null;
  recommended_action: string;
  why_now: string;
  prerequisite_systems: string[];
  trust_gap_signals: string[];
  finish_definition: string;
  risk_if_built_before_prerequisites: string;
  rank_explanation: string;
  prerequisite_explanation: string;
  safe_next_action: string;
  build_now_assessment:
    | 'ready_signal'
    | 'caution_signal'
    | 'blocked_signal'
    | 'unknown_signal'
    | 'prerequisite_signal'
    | 'recommendation'
    | 'prioritization'
    | 'finding'
    | 'observation';
  why_not_higher: string;
  why_not_lower: string;
  minimum_safe_prompt_scope: string;
  dependency_warning_level:
    | 'ready_signal'
    | 'caution_signal'
    | 'blocked_signal'
    | 'unknown_signal'
    | 'prerequisite_signal'
    | 'recommendation'
    | 'prioritization'
    | 'finding'
    | 'observation';
  evidence_summary: string;
  ambiguity_reason?: string;
}

export interface PriorityArtifact {
  schema_version: string;
  phase: string;
  priority_order: string[];
  penalties: string[];
  ranked_systems: RankedSystem[];
  global_ranked_systems: RankedSystem[];
  top_5: RankedSystem[];
  requested_candidate_set: string[];
  requested_candidate_ranking: RequestedCandidateRow[];
  ambiguous_requested_candidates: Array<{ system_id: string; ambiguity_reason: string }>;
  generated_at?: string;
  control_signal?: 'ready_signal' | 'warn' | 'freeze_signal' | 'blocked_signal';
}

export interface PriorityArtifactLoadResult {
  state: PriorityArtifactState;
  payload: PriorityArtifact | null;
  generated_at?: string;
  reason?: string;
  /**
   * Records which on-disk path the dashboard actually loaded the artifact
   * from. The canonical top-level path is preferred; if that is missing,
   * the dashboard falls back to the TLS sibling path so a freshly built
   * TLS pipeline still publishes Top 3 instead of failing closed.
   */
  source_path?: string;
  /**
   * Exact command an operator can run to regenerate the priority artifact
   * if the dashboard reports it missing or invalid. Surfaced to the UI so
   * fail-closed never becomes a dead end.
   */
  recompute_command?: string;
}

const PRIORITY_REPORT_PATH = 'artifacts/system_dependency_priority_report.json';
const PRIORITY_REPORT_TLS_FALLBACK_PATH = 'artifacts/tls/system_dependency_priority_report.json';
const TLS_INTEGRATION_PATH = 'artifacts/tls/system_graph_integration_report.json';

// 14 days. The artifact is build-time; older than this and the dashboard must
// surface a stale state instead of misleading the operator.
const STALE_THRESHOLD_MS = 14 * 24 * 60 * 60 * 1000;

// Accepted schema_version / phase values. Newer TLS pipeline iterations
// (tls-06.v1, tls-05.v1, tls-04.v1) all share the same observable shape used
// by the dashboard. Adding a strict newest-only check would lock the
// dashboard out of the published TLS report; we instead pin the *shape*
// fields the dashboard reads and accept any tls-* schema_version that
// matches.
const ACCEPTED_SCHEMA_VERSION_PREFIX = 'tls-';
const ACCEPTED_PHASE_PREFIX = 'TLS-';

function isPriorityArtifact(value: unknown): value is PriorityArtifact {
  if (!value || typeof value !== 'object') return false;
  const obj = value as Record<string, unknown>;
  if (typeof obj.schema_version !== 'string' || !obj.schema_version.startsWith(ACCEPTED_SCHEMA_VERSION_PREFIX)) {
    return false;
  }
  if (typeof obj.phase !== 'string' || !obj.phase.startsWith(ACCEPTED_PHASE_PREFIX)) {
    return false;
  }
  if (!Array.isArray(obj.ranked_systems)) return false;
  if (!Array.isArray(obj.global_ranked_systems)) return false;
  if (!Array.isArray(obj.top_5)) return false;
  if (!Array.isArray(obj.requested_candidate_set)) return false;
  if (!Array.isArray(obj.requested_candidate_ranking)) return false;
  if (!Array.isArray(obj.ambiguous_requested_candidates)) return false;
  for (const entry of obj.top_5 as unknown[]) {
    if (!entry || typeof entry !== 'object') return false;
    const e = entry as Record<string, unknown>;
    if (typeof e.rank !== 'number') return false;
    if (typeof e.system_id !== 'string') return false;
    if (typeof e.action !== 'string') return false;
    if (typeof e.why_now !== 'string') return false;
    if (!Array.isArray(e.trust_gap_signals)) return false;
    if (!Array.isArray(e.unlocks)) return false;
    if (!e.dependencies || typeof e.dependencies !== 'object') return false;
  }
  return true;
}

/**
 * Recompute command surfaced to the operator when the priority artifact
 * cannot be loaded. The dashboard never re-ranks; a fail-closed banner
 * tells the operator how to regenerate the artifact upstream.
 */
export const PRIORITY_RECOMPUTE_COMMAND =
  'python scripts/build_tls_dependency_priority.py --candidates H01,RFX,HOP,MET,METS --fail-if-missing && python scripts/build_dashboard_3ls_with_tls.py';

interface AttemptResult {
  state: 'ok' | 'invalid_schema' | 'missing';
  payload: PriorityArtifact | null;
  reason?: string;
  generated_at?: string;
  source_path?: string;
  control_signal?: 'blocked_signal' | 'freeze_signal';
}

function attemptLoad(relativePath: string): AttemptResult {
  const repoRoot = getRepoRoot();
  const fullPath = path.join(repoRoot, relativePath);
  let stat: fs.Stats;
  try {
    stat = fs.statSync(fullPath);
  } catch {
    return { state: 'missing', payload: null, reason: `not_found:${relativePath}` };
  }

  let raw: string;
  try {
    raw = fs.readFileSync(fullPath, 'utf-8');
  } catch (err) {
    return {
      state: 'invalid_schema',
      payload: null,
      reason: `read_failed:${(err as Error).message}`,
      source_path: relativePath,
    };
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    return {
      state: 'invalid_schema',
      payload: null,
      reason: `parse_failed:${(err as Error).message}`,
      source_path: relativePath,
    };
  }

  if (!isPriorityArtifact(parsed)) {
    return { state: 'invalid_schema', payload: null, reason: 'shape_mismatch', source_path: relativePath };
  }

  const generated_at = parsed.generated_at ?? stat.mtime.toISOString();
  return {
    state: 'ok',
    payload: parsed,
    generated_at,
    source_path: relativePath,
    control_signal: parsed.control_signal === 'blocked_signal' || parsed.control_signal === 'freeze_signal'
      ? parsed.control_signal
      : undefined,
  };
}

export function loadPriorityArtifact(
  relativePath: string = PRIORITY_REPORT_PATH,
  now: Date = new Date(),
): PriorityArtifactLoadResult {
  // Strict mode: caller asked for a specific path. Honor it without fallback.
  if (relativePath !== PRIORITY_REPORT_PATH) {
    return finalizeLoad(attemptLoad(relativePath), now);
  }

  // Default mode: prefer the canonical top-level path; if the artifact is
  // missing there, fall back to the TLS sibling path that the upstream
  // pipeline produces. This is the Phase 1 fix — Top 3 never reads
  // "unavailable" purely because the publish step has not copied the
  // artifact up to the canonical path yet.
  const primary = attemptLoad(PRIORITY_REPORT_PATH);
  if (primary.state === 'missing') {
    const fallback = attemptLoad(PRIORITY_REPORT_TLS_FALLBACK_PATH);
    if (fallback.state !== 'missing') {
      return finalizeLoad(fallback, now);
    }
    // Both missing: surface the missing-state with the recompute command.
    return {
      state: 'missing',
      payload: null,
      reason: `not_found:${PRIORITY_REPORT_PATH} and not_found:${PRIORITY_REPORT_TLS_FALLBACK_PATH}`,
      recompute_command: PRIORITY_RECOMPUTE_COMMAND,
    };
  }
  return finalizeLoad(primary, now);
}

function finalizeLoad(attempt: AttemptResult, now: Date): PriorityArtifactLoadResult {
  if (attempt.state === 'missing') {
    return {
      state: 'missing',
      payload: null,
      reason: attempt.reason,
      recompute_command: PRIORITY_RECOMPUTE_COMMAND,
    };
  }
  if (attempt.state === 'invalid_schema') {
    return {
      state: 'invalid_schema',
      payload: null,
      reason: attempt.reason ?? 'shape_mismatch',
      source_path: attempt.source_path,
      recompute_command: PRIORITY_RECOMPUTE_COMMAND,
    };
  }

  const payload = attempt.payload!;
  const generated_at = attempt.generated_at!;

  if (attempt.control_signal === 'blocked_signal') {
    return {
      state: 'blocked_signal',
      payload,
      generated_at,
      reason: 'control_signal=blocked_signal',
      source_path: attempt.source_path,
    };
  }
  if (attempt.control_signal === 'freeze_signal') {
    return {
      state: 'freeze_signal',
      payload,
      generated_at,
      reason: 'control_signal=freeze_signal',
      source_path: attempt.source_path,
    };
  }

  const generatedMs = Date.parse(generated_at);
  if (!Number.isNaN(generatedMs) && now.getTime() - generatedMs > STALE_THRESHOLD_MS) {
    return {
      state: 'stale',
      payload,
      generated_at,
      reason: 'older_than_threshold',
      source_path: attempt.source_path,
    };
  }

  return { state: 'ok', payload, generated_at, source_path: attempt.source_path };
}

export interface TLSIntegratedSystem {
  system_id: string;
  classification: string;
  in_repo_registry: boolean;
  data_source: 'artifact_store' | 'repo_registry' | 'stub_fallback';
  status: 'healthy' | 'warning' | 'critical' | 'unknown';
  trust_gap_signals: string[];
  eval_coverage_status: 'present' | 'missing';
  missing_eval_signals: string[];
  dependency_edges: {
    upstream: string[];
    downstream: string[];
  };
}

export interface TLSIntegrationReport {
  artifact_type: 'tls_system_graph_integration_report';
  phase: 'TLS-INT-01';
  generated_at: string;
  trust_posture: 'FREEZE' | 'WARN';
  freeze_reasons: string[];
  source_mix: {
    counts: Record<string, number>;
    percentages: Record<string, number>;
  };
  repo_registry_count: number;
  graph: {
    system_count: number;
    systems: TLSIntegratedSystem[];
  };
}

function isTLSIntegrationReport(value: unknown): value is TLSIntegrationReport {
  if (!value || typeof value !== 'object') return false;
  const obj = value as Record<string, unknown>;
  if (obj.artifact_type !== 'tls_system_graph_integration_report') return false;
  if (obj.phase !== 'TLS-INT-01') return false;
  if (!obj.graph || typeof obj.graph !== 'object') return false;
  const graph = obj.graph as Record<string, unknown>;
  if (!Array.isArray(graph.systems)) return false;
  return true;
}

export function loadTLSIntegrationArtifact(
  relativePath: string = TLS_INTEGRATION_PATH,
): TLSIntegrationReport | null {
  const payload = loadArtifact<unknown>(relativePath);
  if (!isTLSIntegrationReport(payload)) return null;
  return payload;
}
