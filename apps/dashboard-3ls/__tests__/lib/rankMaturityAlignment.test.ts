/**
 * D3L-MASTER-01 Phase 5 — ranking ↔ maturity alignment tests.
 *
 * Mismatch ⇒ warning, never a re-ranking. The helper must NOT mutate or
 * reorder either Top 3 or maturity rows.
 */
import { evaluateRankMaturityAlignment } from '@/lib/rankMaturityAlignment';
import type { RankingRow } from '@/lib/ranking';
import type { MaturityRow } from '@/lib/maturity';

function row(system_id: string, rank = 1): RankingRow {
  return {
    rank,
    system_id,
    classification: 'active_system',
    score: 0,
    action: '',
    why_now: '',
    trust_gap_signals: [],
    prerequisite_systems: [],
    unlocks: [],
    finish_definition: '',
    next_prompt: '',
    trust_state: 'caution_signal',
    is_in_priority_artifact: true,
    is_registry_active: true,
  };
}

function mat(system_id: string, level: 0 | 1 | 2 | 3 | 4): MaturityRow {
  return {
    system_id,
    level,
    level_label: ['Unknown', 'Emerging', 'Developing', 'Stable', 'Trusted'][level],
    status: level === 4 ? 'ready_signal' : 'caution_signal',
    evidence_count: 1,
    has_evidence: true,
    failing_signals: [],
    failing_structural_signals: [],
    trust_state: 'ready_signal',
    freshness_ok: true,
    key_gap: 'none',
    blocking_reasons: [],
  };
}

describe('evaluateRankMaturityAlignment', () => {
  it('aligned: Top 3 contains the lowest-maturity systems ⇒ ok=true, no warning', () => {
    const top3 = [row('AEX'), row('EVL', 2), row('CDE', 3)];
    const m = [mat('AEX', 1), mat('EVL', 1), mat('CDE', 1), mat('SEL', 4)];
    const r = evaluateRankMaturityAlignment(top3, m);
    expect(r.ok).toBe(true);
    expect(r.warning).toBeNull();
  });

  it('mismatch: Top 3 above lowest ⇒ warning, but Top 3 unchanged', () => {
    const top3 = [row('AEX'), row('EVL', 2), row('CDE', 3)];
    const m = [mat('AEX', 3), mat('EVL', 4), mat('CDE', 4), mat('SEL', 0)];
    const r = evaluateRankMaturityAlignment(top3, m);
    expect(r.ok).toBe(false);
    expect(r.warning).not.toBeNull();
    expect(r.top_3_above_lowest_maturity).toEqual(['AEX', 'EVL', 'CDE']);
    expect(r.lowest_maturity_level).toBe(0);
    // Verify input rows are untouched.
    expect(top3.map((row) => row.system_id)).toEqual(['AEX', 'EVL', 'CDE']);
  });

  it('Top 3 without maturity row ⇒ warning notes the missing data', () => {
    const top3 = [row('AEX')];
    const m = [mat('SEL', 1)];
    const r = evaluateRankMaturityAlignment(top3, m);
    expect(r.ok).toBe(false);
    expect(r.notes.some((n) => n.includes('top_3_without_maturity:AEX'))).toBe(true);
  });

  it('empty Top 3 or empty maturity ⇒ ok=true with notes (not a mismatch)', () => {
    expect(evaluateRankMaturityAlignment([], [mat('AEX', 1)]).ok).toBe(true);
    expect(evaluateRankMaturityAlignment([row('AEX')], []).ok).toBe(true);
  });

  it('does not mutate inputs even when warning is set', () => {
    const top3 = [row('AEX'), row('EVL', 2), row('CDE', 3)];
    const before = top3.map((r) => r.system_id);
    const m = [mat('AEX', 4), mat('EVL', 4), mat('CDE', 4), mat('SEL', 0)];
    evaluateRankMaturityAlignment(top3, m);
    expect(top3.map((r) => r.system_id)).toEqual(before);
  });
});
