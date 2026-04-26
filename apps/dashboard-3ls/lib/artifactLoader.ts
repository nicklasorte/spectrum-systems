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
// Note: TLS produces signals only. Canonical owners (CDE/SEL/GOV) decide,
// enforce, and certify based on these signals; the dashboard never decides.
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
}

const PRIORITY_REPORT_PATH = 'artifacts/system_dependency_priority_report.json';

// 14 days. The artifact is build-time; older than this and the dashboard must
// surface a stale state instead of misleading the operator.
const STALE_THRESHOLD_MS = 14 * 24 * 60 * 60 * 1000;

function isPriorityArtifact(value: unknown): value is PriorityArtifact {
  if (!value || typeof value !== 'object') return false;
  const obj = value as Record<string, unknown>;
  if (obj.schema_version !== 'tls-04.v1') return false;
  if (obj.phase !== 'TLS-04') return false;
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

export function loadPriorityArtifact(
  relativePath: string = PRIORITY_REPORT_PATH,
  now: Date = new Date(),
): PriorityArtifactLoadResult {
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
    };
  }

  if (!isPriorityArtifact(parsed)) {
    return { state: 'invalid_schema', payload: null, reason: 'shape_mismatch' };
  }

  const payload = parsed;
  const generated_at = payload.generated_at ?? stat.mtime.toISOString();

  if (payload.control_signal === 'blocked_signal') {
    return {
      state: 'blocked_signal',
      payload,
      generated_at,
      reason: 'control_signal=blocked_signal',
    };
  }
  if (payload.control_signal === 'freeze_signal') {
    return {
      state: 'freeze_signal',
      payload,
      generated_at,
      reason: 'control_signal=freeze_signal',
    };
  }

  const generatedMs = Date.parse(generated_at);
  if (!Number.isNaN(generatedMs) && now.getTime() - generatedMs > STALE_THRESHOLD_MS) {
    return { state: 'stale', payload, generated_at, reason: 'older_than_threshold' };
  }

  return { state: 'ok', payload, generated_at };
}
