// AEX-PQX-DASH-01-REFINE — AI programming core-loop proof.
//
// Observation-only utilities. The dashboard reports what is artifact-backed.
// It does not claim authority outcomes for AEX/PQX/EVL/TPA/CDE/SEL.
//
// The legs are read in canonical order:
//   AEX → PQX → EVL → TPA → CDE → SEL
//
// MET-only role: read each leg's observation field and surface counts,
// first_missing_leg, weakest_leg, blocked work items, and per-leg coverage.
// MET does not claim ownership of any leg.

export const CORE_LOOP_LEGS = [
  'AEX',
  'PQX',
  'EVL',
  'TPA',
  'CDE',
  'SEL',
] as const;

export type CoreLoopLeg = (typeof CORE_LOOP_LEGS)[number];

export type LegObservationState = 'present' | 'partial' | 'missing' | 'unknown';

export interface LegObservation {
  observation: LegObservationState;
  source_artifacts_used: string[];
  reason_codes: string[];
}

export interface AiProgrammingWorkItem {
  work_item_id: string;
  agent: 'codex' | 'claude' | string;
  title: string;
  repo_mutating?: boolean;
  core_loop_observations: Record<CoreLoopLeg, LegObservation>;
  first_missing_leg?: CoreLoopLeg | null;
  weakest_leg?: CoreLoopLeg | null;
  core_loop_complete?: boolean;
  hard_block_reason?: string | null;
  next_recommended_input?: string | null;
}

export interface AiProgrammingGovernedPathRecord {
  schema_version?: string;
  artifact_type?: string;
  data_source?: string;
  source_artifacts_used?: string[];
  warnings?: string[];
  ai_programming_work_items?: AiProgrammingWorkItem[];
}

export type WorkItemStatus = 'PASS' | 'WARN' | 'BLOCK' | 'UNKNOWN';

const OBSERVATION_RANK: Record<LegObservationState, number> = {
  missing: 0,
  unknown: 1,
  partial: 2,
  present: 3,
};

function isLegObservationState(value: unknown): value is LegObservationState {
  return value === 'present' || value === 'partial' || value === 'missing' || value === 'unknown';
}

function safeLegObservation(raw: LegObservation | undefined): LegObservation {
  if (raw && isLegObservationState(raw.observation)) {
    return {
      observation: raw.observation,
      source_artifacts_used: Array.isArray(raw.source_artifacts_used)
        ? raw.source_artifacts_used.filter((s): s is string => typeof s === 'string')
        : [],
      reason_codes: Array.isArray(raw.reason_codes)
        ? raw.reason_codes.filter((s): s is string => typeof s === 'string')
        : [],
    };
  }
  return {
    observation: 'unknown',
    source_artifacts_used: [],
    reason_codes: ['leg_observation_missing_or_invalid'],
  };
}

export function getOrderedLegObservations(item: AiProgrammingWorkItem): Array<{
  leg: CoreLoopLeg;
  observation: LegObservation;
}> {
  return CORE_LOOP_LEGS.map((leg) => ({
    leg,
    observation: safeLegObservation(item.core_loop_observations?.[leg]),
  }));
}

export function computeFirstMissingLeg(item: AiProgrammingWorkItem): CoreLoopLeg | null {
  for (const { leg, observation } of getOrderedLegObservations(item)) {
    if (observation.observation === 'missing') {
      return leg;
    }
  }
  return null;
}

export function computeWeakestLeg(item: AiProgrammingWorkItem): CoreLoopLeg | null {
  let weakest: { leg: CoreLoopLeg; rank: number } | null = null;
  for (const { leg, observation } of getOrderedLegObservations(item)) {
    const rank = OBSERVATION_RANK[observation.observation];
    if (weakest === null || rank < weakest.rank) {
      weakest = { leg, rank };
    }
  }
  return weakest?.leg ?? null;
}

export function isCoreLoopComplete(item: AiProgrammingWorkItem): boolean {
  return getOrderedLegObservations(item).every(
    ({ observation }) => observation.observation === 'present',
  );
}

export function deriveWorkItemStatus(item: AiProgrammingWorkItem): {
  status: WorkItemStatus;
  hard_block_reason: string | null;
} {
  const ordered = getOrderedLegObservations(item);
  const aex = ordered.find((entry) => entry.leg === 'AEX')?.observation.observation;
  const pqx = ordered.find((entry) => entry.leg === 'PQX')?.observation.observation;
  if (aex === 'missing') {
    return { status: 'BLOCK', hard_block_reason: 'AEX_signal_absent' };
  }
  if (pqx === 'missing') {
    return { status: 'BLOCK', hard_block_reason: 'PQX_signal_absent' };
  }
  for (const leg of ['EVL', 'TPA', 'CDE', 'SEL'] as const) {
    const obs = ordered.find((entry) => entry.leg === leg)?.observation.observation;
    if (obs === 'missing') {
      return { status: 'BLOCK', hard_block_reason: `${leg}_signal_absent` };
    }
  }
  const repoMutating = item.repo_mutating === true;
  let hasUnknown = false;
  let hasPartial = false;
  for (const { observation } of ordered) {
    if (observation.observation === 'unknown') hasUnknown = true;
    if (observation.observation === 'partial') hasPartial = true;
  }
  if (hasUnknown && repoMutating) {
    return { status: 'WARN', hard_block_reason: null };
  }
  if (hasPartial) {
    return { status: 'WARN', hard_block_reason: null };
  }
  if (hasUnknown) {
    return { status: 'WARN', hard_block_reason: null };
  }
  return { status: 'PASS', hard_block_reason: null };
}

export interface CoreLoopWorkItemSummary {
  work_item_id: string;
  agent: string;
  title: string;
  status: WorkItemStatus;
  first_missing_leg: CoreLoopLeg | null;
  weakest_leg: CoreLoopLeg | null;
  core_loop_complete: boolean;
  hard_block_reason: string | null;
  next_recommended_input: string | null;
  legs: Array<{
    leg: CoreLoopLeg;
    observation: LegObservationState;
    source_artifacts_used: string[];
    reason_codes: string[];
  }>;
}

export interface CoreLoopCounts {
  aex_present_count: number;
  pqx_present_count: number;
  evl_present_count: number;
  tpa_present_count: number;
  cde_present_count: number;
  sel_present_count: number;
}

export interface CoreLoopMissingByLeg {
  AEX: number;
  PQX: number;
  EVL: number;
  TPA: number;
  CDE: number;
  SEL: number;
}

export interface CoreLoopSummary {
  data_source: string;
  source_artifacts_used: string[];
  warnings: string[];
  total_work_item_count: number;
  codex_work_item_count: number;
  claude_work_item_count: number;
  pass_count: number;
  warn_count: number;
  block_count: number;
  core_loop_complete_count: number;
  weakest_leg: CoreLoopLeg | null;
  counts_by_leg: CoreLoopCounts;
  missing_by_leg: CoreLoopMissingByLeg;
  blocked_work_items: CoreLoopWorkItemSummary[];
  work_items: CoreLoopWorkItemSummary[];
  overall_status: WorkItemStatus;
}

function summarizeWorkItem(item: AiProgrammingWorkItem): CoreLoopWorkItemSummary {
  const ordered = getOrderedLegObservations(item);
  const { status, hard_block_reason } = deriveWorkItemStatus(item);
  return {
    work_item_id: item.work_item_id,
    agent: item.agent,
    title: item.title,
    status,
    first_missing_leg: computeFirstMissingLeg(item),
    weakest_leg: computeWeakestLeg(item),
    core_loop_complete: isCoreLoopComplete(item),
    hard_block_reason: item.hard_block_reason ?? hard_block_reason,
    next_recommended_input: item.next_recommended_input ?? null,
    legs: ordered.map(({ leg, observation }) => ({
      leg,
      observation: observation.observation,
      source_artifacts_used: observation.source_artifacts_used,
      reason_codes: observation.reason_codes,
    })),
  };
}

function pickWeakestAcrossWorkItems(
  workItems: CoreLoopWorkItemSummary[],
): CoreLoopLeg | null {
  let best: { leg: CoreLoopLeg; missingCount: number; rankSum: number } | null = null;
  const tally: Record<CoreLoopLeg, { missingCount: number; rankSum: number }> = {
    AEX: { missingCount: 0, rankSum: 0 },
    PQX: { missingCount: 0, rankSum: 0 },
    EVL: { missingCount: 0, rankSum: 0 },
    TPA: { missingCount: 0, rankSum: 0 },
    CDE: { missingCount: 0, rankSum: 0 },
    SEL: { missingCount: 0, rankSum: 0 },
  };
  for (const item of workItems) {
    for (const entry of item.legs) {
      tally[entry.leg].rankSum += OBSERVATION_RANK[entry.observation];
      if (entry.observation === 'missing') {
        tally[entry.leg].missingCount += 1;
      }
    }
  }
  for (const leg of CORE_LOOP_LEGS) {
    const t = tally[leg];
    if (
      best === null ||
      t.missingCount > best.missingCount ||
      (t.missingCount === best.missingCount && t.rankSum < best.rankSum)
    ) {
      best = { leg, missingCount: t.missingCount, rankSum: t.rankSum };
    }
  }
  if (!best) return null;
  // If no leg has any missing/partial/unknown observation, no weakest leg
  // is meaningful — every leg is fully present.
  const maxRank = OBSERVATION_RANK.present * workItems.length;
  if (best.missingCount === 0 && best.rankSum === maxRank) {
    return null;
  }
  return best.leg;
}

export function computeCoreLoopSummary(
  record: AiProgrammingGovernedPathRecord | null,
  unavailableWarning: string,
): CoreLoopSummary {
  if (!record || !Array.isArray(record.ai_programming_work_items)) {
    return {
      data_source: 'unknown',
      source_artifacts_used: [],
      warnings: [unavailableWarning],
      total_work_item_count: 0,
      codex_work_item_count: 0,
      claude_work_item_count: 0,
      pass_count: 0,
      warn_count: 0,
      block_count: 0,
      core_loop_complete_count: 0,
      weakest_leg: null,
      counts_by_leg: {
        aex_present_count: 0,
        pqx_present_count: 0,
        evl_present_count: 0,
        tpa_present_count: 0,
        cde_present_count: 0,
        sel_present_count: 0,
      },
      missing_by_leg: { AEX: 0, PQX: 0, EVL: 0, TPA: 0, CDE: 0, SEL: 0 },
      blocked_work_items: [],
      work_items: [],
      overall_status: 'UNKNOWN',
    };
  }

  const workItems = record.ai_programming_work_items.map(summarizeWorkItem);

  const counts_by_leg: CoreLoopCounts = {
    aex_present_count: 0,
    pqx_present_count: 0,
    evl_present_count: 0,
    tpa_present_count: 0,
    cde_present_count: 0,
    sel_present_count: 0,
  };
  const missing_by_leg: CoreLoopMissingByLeg = {
    AEX: 0,
    PQX: 0,
    EVL: 0,
    TPA: 0,
    CDE: 0,
    SEL: 0,
  };

  const presentKey: Record<CoreLoopLeg, keyof CoreLoopCounts> = {
    AEX: 'aex_present_count',
    PQX: 'pqx_present_count',
    EVL: 'evl_present_count',
    TPA: 'tpa_present_count',
    CDE: 'cde_present_count',
    SEL: 'sel_present_count',
  };

  for (const item of workItems) {
    for (const entry of item.legs) {
      if (entry.observation === 'present') {
        counts_by_leg[presentKey[entry.leg]] += 1;
      }
      if (entry.observation === 'missing') {
        missing_by_leg[entry.leg] += 1;
      }
    }
  }

  const codex_work_item_count = workItems.filter((w) => w.agent === 'codex').length;
  const claude_work_item_count = workItems.filter((w) => w.agent === 'claude').length;
  const pass_count = workItems.filter((w) => w.status === 'PASS').length;
  const warn_count = workItems.filter((w) => w.status === 'WARN').length;
  const block_count = workItems.filter((w) => w.status === 'BLOCK').length;
  const core_loop_complete_count = workItems.filter((w) => w.core_loop_complete).length;
  const blocked_work_items = workItems.filter((w) => w.status === 'BLOCK');
  const weakest_leg = pickWeakestAcrossWorkItems(workItems);

  const overall_status: WorkItemStatus =
    block_count > 0
      ? 'BLOCK'
      : warn_count > 0
        ? 'WARN'
        : workItems.length === 0
          ? 'UNKNOWN'
          : 'PASS';

  return {
    data_source: record.data_source ?? 'unknown',
    source_artifacts_used: record.source_artifacts_used ?? [],
    warnings: record.warnings ?? [],
    total_work_item_count: workItems.length,
    codex_work_item_count,
    claude_work_item_count,
    pass_count,
    warn_count,
    block_count,
    core_loop_complete_count,
    weakest_leg,
    counts_by_leg,
    missing_by_leg,
    blocked_work_items,
    work_items: workItems,
    overall_status,
  };
}
