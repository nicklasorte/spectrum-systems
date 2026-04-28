/**
 * D3L-MASTER-01 Phase 3 — ranking projection tests.
 *
 * Pins:
 *   - active universe is canonical (full list contains every active system)
 *   - non-active ids (H01, ABX, HNX) are excluded with rejection bookkeeping
 *   - missing-from-priority systems appear at the tail with rank=null
 *   - Top 3 / Top 10 are slices, not separately ranked
 *   - dashboard does not invent or re-order
 */
import { projectRanking, type RankingProjection } from '@/lib/ranking';
import type { D3LRegistryContract } from '@/lib/systemRegistry';
import type { PriorityArtifact } from '@/lib/artifactLoader';

const ACTIVE = ['EVL', 'CDE', 'TPA', 'SEL', 'OBS', 'AEX', 'PQX', 'LIN', 'REP', 'SLO', 'PRA', 'GOV'];

const CONTRACT: D3LRegistryContract = {
  artifact_type: 'd3l_registry_contract',
  phase: 'D3L-MASTER-01',
  schema_version: 'd3l-master-01.v1',
  source_artifact: 'artifacts/tls/system_registry_dependency_graph.json',
  active_system_ids: ACTIVE,
  future_system_ids: ['ABX'],
  deprecated_or_merged_system_ids: ['HNX'],
  excluded_ids: ['ABX', 'HNX'],
  ranking_universe: ACTIVE,
  maturity_universe: ACTIVE,
  forbidden_node_examples: ['H01'],
  rules: [],
};

function makeRow(systemId: string, rank: number, score = 100 - rank): {
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
} {
  return {
    rank,
    system_id: systemId,
    classification: 'active_system',
    score,
    action: `harden ${systemId}`,
    why_now: `${systemId} on canonical loop`,
    trust_gap_signals: [],
    dependencies: { upstream: [], downstream: [] },
    unlocks: [],
    finish_definition: '',
    next_prompt: `Run TLS-FIX-${systemId}`,
    trust_state: 'caution_signal',
  };
}

function priority(rows: ReturnType<typeof makeRow>[]): PriorityArtifact {
  return {
    schema_version: 'tls-04.v1',
    phase: 'TLS-04',
    priority_order: [],
    penalties: [],
    ranked_systems: [],
    global_ranked_systems: rows,
    top_5: rows.slice(0, 5),
    requested_candidate_set: [],
    requested_candidate_ranking: [],
    ambiguous_requested_candidates: [],
    generated_at: '2026-04-28T07:00:00Z',
  };
}

describe('projectRanking', () => {
  it('returns empty projection when priority artifact is missing', () => {
    const p = projectRanking(null, CONTRACT);
    expect(p.full).toEqual([]);
    expect(p.warnings.some((w) => w.includes('priority_artifact_missing'))).toBe(true);
  });

  it('returns empty projection when contract is missing', () => {
    const p = projectRanking(priority([]), null);
    expect(p.full).toEqual([]);
    expect(p.warnings.some((w) => w.includes('contract_missing'))).toBe(true);
  });

  it('preserves artifact ordering — never re-ranks', () => {
    const rows = [makeRow('EVL', 1), makeRow('CDE', 2), makeRow('TPA', 3)];
    const p = projectRanking(priority(rows), CONTRACT);
    expect(p.top_3.map((r) => r.system_id)).toEqual(['EVL', 'CDE', 'TPA']);
  });

  it('excludes non-active ids (H01, ABX, HNX) and reports them', () => {
    const rows = [
      makeRow('EVL', 1),
      makeRow('H01', 2),
      makeRow('CDE', 3),
      makeRow('ABX', 4),
      makeRow('HNX', 5),
    ];
    const p = projectRanking(priority(rows), CONTRACT);
    expect(p.full.map((r) => r.system_id).slice(0, 2)).toEqual(['EVL', 'CDE']);
    expect(p.excluded_from_priority).toEqual(['H01', 'ABX', 'HNX']);
    expect(p.warnings.some((w) => w.includes('excluded_non_active'))).toBe(true);
  });

  it('full list contains every active system; missing systems appear with rank=null', () => {
    const rows = [makeRow('EVL', 1), makeRow('CDE', 2)];
    const p = projectRanking(priority(rows), CONTRACT);
    expect(p.full.length).toBe(ACTIVE.length);
    const fullIds = p.full.map((r) => r.system_id);
    for (const id of ACTIVE) expect(fullIds).toContain(id);

    const missing = p.full.filter((r) => !r.is_in_priority_artifact);
    expect(missing.length).toBe(ACTIVE.length - 2);
    for (const r of missing) expect(r.rank).toBeNull();
  });

  it('Top 10 is a slice of artifact-present rows; Top 3 is its prefix', () => {
    const rows = ACTIVE.slice(0, 12).map((id, i) => makeRow(id, i + 1));
    const p = projectRanking(priority(rows), CONTRACT);
    expect(p.top_10.length).toBe(10);
    expect(p.top_3).toEqual(p.top_10.slice(0, 3));
  });

  it('flags missing-from-priority systems even when artifact is otherwise valid', () => {
    const rows = [makeRow('EVL', 1)];
    const p = projectRanking(priority(rows), CONTRACT);
    expect(p.missing_from_priority).toEqual(ACTIVE.filter((id) => id !== 'EVL'));
  });

  it('falls back to top_5 when global_ranked_systems is empty', () => {
    const fallback: PriorityArtifact = {
      ...priority([]),
      global_ranked_systems: [],
      top_5: [makeRow('EVL', 1), makeRow('CDE', 2)],
    };
    const p: RankingProjection = projectRanking(fallback, CONTRACT);
    expect(p.warnings.some((w) => w.includes('using_top_5'))).toBe(true);
    expect(p.top_3.map((r) => r.system_id)).toEqual(['EVL', 'CDE']);
  });
});
