// AEX-PQX-DASH-01 — AI programming governed-path helper.
//
// MET observation only. The dashboard does not admit, execute, eval, decide,
// or enforce. AEX owns admission. PQX owns execution. EVL owns eval.
// CDE owns control. SEL owns enforcement.
//
// This helper normalises agent identification and computes a fail-closed
// summary: missing artifact remains unknown, repo-mutating Codex/Claude
// work without AEX or PQX evidence renders BLOCK, never green.

export type AgentType = 'codex' | 'claude' | 'unknown_ai_agent';

export type GovernancePresence = 'present' | 'missing' | 'partial' | 'unknown';

export type RepoMutating = true | false | 'unknown';

export type BypassRisk =
  | 'none'
  | 'aex_missing'
  | 'pqx_missing'
  | 'eval_missing'
  | 'lineage_missing'
  | 'unknown';

export type GovernedPathStatus = 'pass' | 'warn' | 'block' | 'unknown';

export interface AiProgrammingWorkItem {
  work_item_id: string;
  agent_type: AgentType;
  source_ref?: string;
  pr_ref?: string;
  branch_ref?: string;
  changed_files_count?: number | 'unknown';
  repo_mutating: RepoMutating;
  aex_admission_observation: GovernancePresence;
  pqx_execution_observation: GovernancePresence;
  eval_observation: GovernancePresence;
  control_signal_observation: GovernancePresence;
  enforcement_or_readiness_signal_observation: GovernancePresence;
  lineage_observation: GovernancePresence;
  bypass_risk: BypassRisk;
  next_recommended_input?: string;
  source_artifacts_used?: string[];
}

export interface AiProgrammingGovernedPathRecord {
  artifact_type?: string;
  schema_version?: string;
  record_id?: string;
  created_at?: string;
  owner_system?: string;
  data_source?: string;
  status?: 'warn' | 'block' | 'unknown' | 'pass';
  source_artifacts_used?: string[];
  warnings?: string[];
  reason_codes?: string[];
  failure_prevented?: string;
  signal_improved?: string;
  ai_programming_work_items?: AiProgrammingWorkItem[];
}

export interface GovernedPathSummary {
  status: GovernedPathStatus;
  data_source: string;
  source_artifacts_used: string[];
  warnings: string[];
  reason_codes: string[];
  failure_prevented: string | null;
  signal_improved: string | null;
  total_ai_programming_work_items: number | 'unknown';
  codex_work_count: number | 'unknown';
  claude_work_count: number | 'unknown';
  governed_work_count: number | 'unknown';
  bypass_risk_count: number | 'unknown';
  unknown_path_count: number | 'unknown';
  aex_present_count: number | 'unknown';
  pqx_present_count: number | 'unknown';
  ai_programming_work_items: AiProgrammingWorkItem[];
  top_attention_items: AiProgrammingWorkItem[];
}

const VALID_PRESENCE: ReadonlySet<GovernancePresence> = new Set([
  'present',
  'missing',
  'partial',
  'unknown',
]);

export function normalizeAgentType(raw: unknown): AgentType {
  if (typeof raw !== 'string') return 'unknown_ai_agent';
  const value = raw.trim().toLowerCase();
  if (value === 'codex') return 'codex';
  if (value === 'claude') return 'claude';
  return 'unknown_ai_agent';
}

function normalizePresence(raw: unknown): GovernancePresence {
  if (typeof raw !== 'string') return 'unknown';
  const value = raw.trim().toLowerCase();
  if (VALID_PRESENCE.has(value as GovernancePresence)) {
    return value as GovernancePresence;
  }
  return 'unknown';
}

function normalizeRepoMutating(raw: unknown): RepoMutating {
  if (raw === true) return true;
  if (raw === false) return false;
  return 'unknown';
}

function normalizeBypassRisk(raw: unknown): BypassRisk {
  if (typeof raw !== 'string') return 'unknown';
  const value = raw.trim().toLowerCase();
  switch (value) {
    case 'none':
    case 'aex_missing':
    case 'pqx_missing':
    case 'eval_missing':
    case 'lineage_missing':
    case 'unknown':
      return value;
    default:
      return 'unknown';
  }
}

export function normalizeWorkItem(raw: unknown): AiProgrammingWorkItem | null {
  if (!raw || typeof raw !== 'object') return null;
  const r = raw as Record<string, unknown>;
  const id = typeof r.work_item_id === 'string' ? r.work_item_id : null;
  if (!id) return null;
  return {
    work_item_id: id,
    agent_type: normalizeAgentType(r.agent_type),
    source_ref: typeof r.source_ref === 'string' ? r.source_ref : undefined,
    pr_ref: typeof r.pr_ref === 'string' ? r.pr_ref : undefined,
    branch_ref: typeof r.branch_ref === 'string' ? r.branch_ref : undefined,
    changed_files_count:
      typeof r.changed_files_count === 'number'
        ? r.changed_files_count
        : 'unknown',
    repo_mutating: normalizeRepoMutating(r.repo_mutating),
    aex_admission_observation: normalizePresence(r.aex_admission_observation),
    pqx_execution_observation: normalizePresence(r.pqx_execution_observation),
    eval_observation: normalizePresence(r.eval_observation),
    control_signal_observation: normalizePresence(r.control_signal_observation),
    enforcement_or_readiness_signal_observation: normalizePresence(
      r.enforcement_or_readiness_signal_observation,
    ),
    lineage_observation: normalizePresence(r.lineage_observation),
    bypass_risk: normalizeBypassRisk(r.bypass_risk),
    next_recommended_input:
      typeof r.next_recommended_input === 'string' ? r.next_recommended_input : undefined,
    source_artifacts_used: Array.isArray(r.source_artifacts_used)
      ? (r.source_artifacts_used.filter((s) => typeof s === 'string') as string[])
      : [],
  };
}

function isRepoMutating(item: AiProgrammingWorkItem): boolean {
  return item.repo_mutating === true;
}

function isProofMissing(value: GovernancePresence): boolean {
  return value === 'missing' || value === 'unknown';
}

// Anything short of 'present' counts as incomplete evidence. After the
// 'missing' branch returns 'block' the caller has only present/partial/unknown
// to consider; both 'partial' and 'unknown' must downgrade the item to 'warn'.
function isProofIncomplete(value: GovernancePresence): boolean {
  return value !== 'present';
}

// Compute a status for a single work item using the AEX-PQX-DASH-01 rules.
//
// Rules (fail-closed):
//   - If repo_mutating is unknown and the item is a known AI agent, treat as warn.
//   - If repo_mutating is true and the agent is codex|claude:
//       * AEX missing -> block
//       * PQX missing -> block
//       * AEX or PQX partial/unknown -> warn
//   - If repo_mutating is true and the agent is unknown_ai_agent:
//       * AEX missing or PQX missing -> block
//       * Otherwise warn (because unknown agent + repo mutation is itself a
//         bypass-risk surface)
//   - If repo_mutating is false, fall back to whatever bypass_risk is reported
//     (none -> pass, otherwise warn).
export function computeWorkItemStatus(item: AiProgrammingWorkItem): GovernedPathStatus {
  if (item.repo_mutating === 'unknown') {
    return 'warn';
  }
  if (item.repo_mutating === false) {
    return item.bypass_risk === 'none' ? 'pass' : 'warn';
  }
  // repo_mutating === true
  if (item.agent_type === 'unknown_ai_agent') {
    if (
      item.aex_admission_observation === 'missing' ||
      item.pqx_execution_observation === 'missing'
    ) {
      return 'block';
    }
    return 'warn';
  }
  // codex or claude with repo mutation
  if (
    item.aex_admission_observation === 'missing' ||
    item.pqx_execution_observation === 'missing'
  ) {
    return 'block';
  }
  if (
    isProofIncomplete(item.aex_admission_observation) ||
    isProofIncomplete(item.pqx_execution_observation)
  ) {
    return 'warn';
  }
  if (item.bypass_risk !== 'none') {
    return 'warn';
  }
  return 'pass';
}

function aggregateStatus(statuses: GovernedPathStatus[]): GovernedPathStatus {
  if (statuses.includes('block')) return 'block';
  if (statuses.includes('warn')) return 'warn';
  if (statuses.length === 0) return 'unknown';
  if (statuses.every((s) => s === 'pass')) return 'pass';
  return 'unknown';
}

function coerceStringArray(raw: unknown): string[] {
  if (!Array.isArray(raw)) return [];
  return raw.filter((v): v is string => typeof v === 'string');
}

const ARTIFACT_PATH = 'artifacts/dashboard_metrics/ai_programming_governed_path_record.json';

export function computeGovernedPathSummary(
  record: AiProgrammingGovernedPathRecord | null,
): GovernedPathSummary {
  if (!record) {
    return {
      status: 'unknown',
      data_source: 'unknown',
      source_artifacts_used: [],
      warnings: [`${ARTIFACT_PATH} unavailable; AI programming governed path reported as unknown.`],
      reason_codes: ['ai_programming_governed_path_record_missing'],
      failure_prevented: null,
      signal_improved: null,
      total_ai_programming_work_items: 'unknown',
      codex_work_count: 'unknown',
      claude_work_count: 'unknown',
      governed_work_count: 'unknown',
      bypass_risk_count: 'unknown',
      unknown_path_count: 'unknown',
      aex_present_count: 'unknown',
      pqx_present_count: 'unknown',
      ai_programming_work_items: [],
      top_attention_items: [],
    };
  }

  const rawItems = Array.isArray(record.ai_programming_work_items)
    ? record.ai_programming_work_items
    : [];
  const items = rawItems
    .map(normalizeWorkItem)
    .filter((i): i is AiProgrammingWorkItem => i !== null);

  const codex_work_count = items.filter((i) => i.agent_type === 'codex').length;
  const claude_work_count = items.filter((i) => i.agent_type === 'claude').length;
  const aex_present_count = items.filter((i) => i.aex_admission_observation === 'present').length;
  const pqx_present_count = items.filter((i) => i.pqx_execution_observation === 'present').length;
  const governed_work_count = items.filter(
    (i) =>
      i.aex_admission_observation === 'present' &&
      i.pqx_execution_observation === 'present',
  ).length;
  const bypass_risk_count = items.filter(
    (i) => i.bypass_risk !== 'none' && i.bypass_risk !== 'unknown',
  ).length;
  const unknown_path_count = items.filter(
    (i) =>
      i.aex_admission_observation === 'unknown' ||
      i.pqx_execution_observation === 'unknown' ||
      i.bypass_risk === 'unknown',
  ).length;

  const statuses = items.map(computeWorkItemStatus);
  const status = aggregateStatus(statuses);

  const rank: Record<GovernedPathStatus, number> = {
    block: 0,
    warn: 1,
    unknown: 2,
    pass: 3,
  };
  const enriched = items.map((item, idx) => ({ item, status: statuses[idx] }));
  enriched.sort((a, b) => rank[a.status] - rank[b.status]);
  const top_attention_items = enriched
    .filter((e) => e.status !== 'pass')
    .slice(0, 3)
    .map((e) => e.item);

  return {
    status,
    data_source: typeof record.data_source === 'string' ? record.data_source : 'unknown',
    source_artifacts_used: coerceStringArray(record.source_artifacts_used),
    warnings: coerceStringArray(record.warnings),
    reason_codes: coerceStringArray(record.reason_codes),
    failure_prevented: record.failure_prevented ?? null,
    signal_improved: record.signal_improved ?? null,
    total_ai_programming_work_items: items.length,
    codex_work_count,
    claude_work_count,
    governed_work_count,
    bypass_risk_count,
    unknown_path_count,
    aex_present_count,
    pqx_present_count,
    ai_programming_work_items: items,
    top_attention_items,
  };
}

export const AI_PROGRAMMING_GOVERNED_PATH_ARTIFACT_PATH = ARTIFACT_PATH;
