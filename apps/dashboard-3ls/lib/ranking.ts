// D3L-MASTER-01 Phase 3 — Top 3 / Top 10 / Full ranking helper.
//
// Reads the upstream priority artifact (TLS pipeline) and projects it
// against the registry contract. The dashboard NEVER re-ranks; it only
// filters and slices. The contract's ranking_universe is canonical:
//   * Active systems present in the priority artifact appear in their
//     artifact-declared order.
//   * Active systems NOT present in the priority artifact appear at the
//     end of the full list with rank=null and a missing-data marker so
//     the operator sees that the ranking is incomplete.
//   * Forbidden / future / deprecated ids are filtered and reported as
//     `excluded_from_priority` on the report.

import type { PriorityArtifact, RankedSystem } from './artifactLoader';
import type { D3LRegistryContract } from './systemRegistry';

export interface RankingRow {
  rank: number | null;
  system_id: string;
  classification: string;
  score: number | null;
  action: string;
  why_now: string;
  trust_gap_signals: string[];
  prerequisite_systems: string[];
  unlocks: string[];
  finish_definition: string;
  next_prompt: string;
  trust_state: string;
  is_in_priority_artifact: boolean;
  is_registry_active: true;
}

export interface RankingProjection {
  generated_at: string | null;
  ranking_universe_size: number;
  top_3: RankingRow[];
  top_10: RankingRow[];
  full: RankingRow[];
  excluded_from_priority: string[];
  missing_from_priority: string[];
  warnings: string[];
}

const EMPTY_PROJECTION: RankingProjection = {
  generated_at: null,
  ranking_universe_size: 0,
  top_3: [],
  top_10: [],
  full: [],
  excluded_from_priority: [],
  missing_from_priority: [],
  warnings: [],
};

function asArray<T>(value: T[] | undefined | null): T[] {
  return Array.isArray(value) ? value : [];
}

function rowFromRanked(row: RankedSystem, fallbackRank: number | null): RankingRow {
  return {
    rank: typeof row.rank === 'number' ? row.rank : fallbackRank,
    system_id: row.system_id,
    classification: row.classification ?? 'active_system',
    score: typeof row.score === 'number' ? row.score : null,
    action: row.action ?? '',
    why_now: row.why_now ?? '',
    trust_gap_signals: asArray(row.trust_gap_signals),
    prerequisite_systems: asArray(row.dependencies?.upstream),
    unlocks: asArray(row.unlocks),
    finish_definition: row.finish_definition ?? '',
    next_prompt: row.next_prompt ?? '',
    trust_state: row.trust_state ?? 'unknown_signal',
    is_in_priority_artifact: true,
    is_registry_active: true,
  };
}

function rowFromMissing(systemId: string): RankingRow {
  return {
    rank: null,
    system_id: systemId,
    classification: 'active_system',
    score: null,
    action: 'no recommendation in current priority artifact',
    why_now: 'system absent from priority artifact; recompute pipeline',
    trust_gap_signals: [],
    prerequisite_systems: [],
    unlocks: [],
    finish_definition: '',
    next_prompt: '',
    trust_state: 'unknown_signal',
    is_in_priority_artifact: false,
    is_registry_active: true,
  };
}

/**
 * Project the priority artifact onto the registry contract to produce
 * Top 3 / Top 10 / Full lists. Returns an empty projection when either
 * input is missing — callers must surface fail-closed banners then.
 */
export function projectRanking(
  priority: PriorityArtifact | null,
  contract: D3LRegistryContract | null,
): RankingProjection {
  if (!priority || !contract) {
    return {
      ...EMPTY_PROJECTION,
      warnings: !priority
        ? ['ranking_projection_skipped:priority_artifact_missing']
        : ['ranking_projection_skipped:contract_missing'],
    };
  }

  const universe = new Set(contract.ranking_universe);
  const universeArr = Array.from(contract.ranking_universe);
  const warnings: string[] = [];

  // Source order: prefer global_ranked_systems (full ranked list);
  // fall back to top_5 if global is empty.
  let source: RankedSystem[] = asArray(priority.global_ranked_systems);
  if (source.length === 0) {
    source = asArray(priority.top_5);
    warnings.push('global_ranked_systems_missing_using_top_5');
  }

  const excluded: string[] = [];
  const seen = new Set<string>();
  const admittedRows: RankingRow[] = [];
  let runningRank = 0;
  for (const row of source) {
    if (!row || typeof row.system_id !== 'string') continue;
    if (seen.has(row.system_id)) continue;
    if (!universe.has(row.system_id)) {
      excluded.push(row.system_id);
      continue;
    }
    seen.add(row.system_id);
    runningRank += 1;
    admittedRows.push(rowFromRanked(row, runningRank));
  }

  const missing: string[] = [];
  for (const id of universeArr) {
    if (!seen.has(id)) {
      missing.push(id);
      admittedRows.push(rowFromMissing(id));
    }
  }

  if (excluded.length > 0) {
    warnings.push(`excluded_non_active:${excluded.join(',')}`);
  }
  if (missing.length > 0) {
    warnings.push(`missing_from_priority:${missing.join(',')}`);
  }

  const top3 = admittedRows.filter((r) => r.is_in_priority_artifact).slice(0, 3);
  const top10 = admittedRows.filter((r) => r.is_in_priority_artifact).slice(0, 10);

  return {
    generated_at: priority.generated_at ?? null,
    ranking_universe_size: universeArr.length,
    top_3: top3,
    top_10: top10,
    full: admittedRows,
    excluded_from_priority: excluded,
    missing_from_priority: missing,
    warnings,
  };
}
