/**
 * D3L-REGISTRY-01 — Top 3 extraction tests.
 *
 * The dashboard never re-ranks. Cards must preserve artifact order. Cards
 * whose system_id is not registry-active must be marked text-only and
 * never drive the graph overlay.
 */
import { extractTopThreeRecommendations, buildLeverageQueueFromRoadmap } from '@/lib/dashboardSimplified';
import { parseRegistryContractFromArtifact } from '@/lib/registryContract';
import type { PriorityArtifactLoadResult } from '@/lib/artifactLoader';

const CONTRACT = parseRegistryContractFromArtifact({
  active_systems: ['EVL', 'TPA', 'CDE', 'SEL', 'LIN', 'AEX', 'PQX'].map((id) => ({
    system_id: id,
    status: 'active',
    purpose: '',
    upstream: [],
    downstream: [],
  })),
  future_systems: [],
  merged_or_demoted: [],
  canonical_loop: [],
  canonical_overlays: [],
});

function priorityResult(payloadOverrides: Record<string, unknown>): PriorityArtifactLoadResult {
  return {
    state: 'ok',
    generated_at: '2026-04-28T00:00:00.000Z',
    payload: {
      schema_version: 'tls-06.v1',
      phase: 'TLS-06',
      priority_order: [],
      penalties: [],
      ranked_systems: [],
      global_ranked_systems: [],
      top_5: [],
      requested_candidate_set: [],
      requested_candidate_ranking: [],
      ambiguous_requested_candidates: [],
      ...payloadOverrides,
    } as never,
  };
}

const REGISTRY_TOP3 = [
  { rank: 1, system_id: 'EVL', classification: 'active_system', score: 100, action: 'harden', why_now: 'eval', trust_gap_signals: [], dependencies: { upstream: [], downstream: [] }, unlocks: [], finish_definition: '', next_prompt: '', trust_state: 'blocked_signal' },
  { rank: 2, system_id: 'TPA', classification: 'active_system', score: 90, action: 'harden', why_now: 'tpa', trust_gap_signals: [], dependencies: { upstream: [], downstream: [] }, unlocks: [], finish_definition: '', next_prompt: '', trust_state: 'blocked_signal' },
  { rank: 3, system_id: 'CDE', classification: 'active_system', score: 80, action: 'harden', why_now: 'cde', trust_gap_signals: [], dependencies: { upstream: [], downstream: [] }, unlocks: [], finish_definition: '', next_prompt: '', trust_state: 'blocked_signal' },
];

describe('extractTopThreeRecommendations', () => {
  it('preserves artifact ordering — dashboard does not re-rank', () => {
    const result = extractTopThreeRecommendations(priorityResult({ top_5: REGISTRY_TOP3 }), CONTRACT);
    expect(result.cards.map((c) => c.system_id)).toEqual(['EVL', 'TPA', 'CDE']);
  });

  it('marks all registry-active rows as registry-backed', () => {
    const result = extractTopThreeRecommendations(priorityResult({ top_5: REGISTRY_TOP3 }), CONTRACT);
    expect(result.cards.every((c) => c.is_registry_backed)).toBe(true);
    expect(result.registry_backed_system_ids).toEqual(['EVL', 'TPA', 'CDE']);
    expect(result.non_registry_system_ids).toEqual([]);
  });

  it('flags non-registry rows as text-only with a warning', () => {
    const offTopPriority = priorityResult({
      top_5: [
        { ...REGISTRY_TOP3[0], system_id: 'H01' },
        REGISTRY_TOP3[1],
        REGISTRY_TOP3[2],
      ],
    });
    const result = extractTopThreeRecommendations(offTopPriority, CONTRACT);
    expect(result.cards[0].is_registry_backed).toBe(false);
    expect(result.non_registry_system_ids).toEqual(['H01']);
    expect(result.warning).toMatch(/non-registry/);
  });

  it('reports fail-closed warning with recompute_command when artifact missing', () => {
    const result = extractTopThreeRecommendations({ state: 'missing', payload: null, reason: 'not_found', recompute_command: 'CMD' }, CONTRACT);
    expect(result.cards).toEqual([]);
    expect(result.warning).toMatch(/Top 3 unavailable/);
    expect(result.recompute_command).toBe('CMD');
  });

  it('reports fail-closed warning when artifact has invalid schema', () => {
    const result = extractTopThreeRecommendations({ state: 'invalid_schema', payload: null, reason: 'shape_mismatch' }, CONTRACT);
    expect(result.cards).toEqual([]);
    expect(result.warning).toMatch(/invalid/);
  });

  it('reports stale warning when artifact is past freshness threshold', () => {
    const result = extractTopThreeRecommendations({
      state: 'stale',
      generated_at: '2024-01-01T00:00:00Z',
      payload: priorityResult({ top_5: REGISTRY_TOP3 }).payload!,
    }, CONTRACT);
    expect(result.warning).toMatch(/stale/);
  });

  it('partial-coverage warning when ranking has fewer than 3 rows', () => {
    const result = extractTopThreeRecommendations(priorityResult({ top_5: REGISTRY_TOP3.slice(0, 2) }), CONTRACT);
    expect(result.warning).toMatch(/partial/);
  });

  it('falls back to requested_candidate_ranking when top_5 is empty', () => {
    const result = extractTopThreeRecommendations(priorityResult({
      top_5: [],
      requested_candidate_ranking: [
        { requested_rank: 1, system_id: 'EVL', classification: 'active_system', recommended_action: 'harden', why_now: 'eval', prerequisite_systems: [], minimum_safe_prompt_scope: 'scope', risk_if_built_before_prerequisites: 'do_not_touch', build_now_assessment: 'caution_signal', why_not_higher: '', why_not_lower: '', dependency_warning_level: 'caution_signal', evidence_summary: '', rank_explanation: '', prerequisite_explanation: '', safe_next_action: '', finish_definition: '' },
        { requested_rank: 2, system_id: 'TPA', classification: 'active_system', recommended_action: 'harden', why_now: 'tpa', prerequisite_systems: [], minimum_safe_prompt_scope: 'scope', risk_if_built_before_prerequisites: 'do_not_touch', build_now_assessment: 'caution_signal', why_not_higher: '', why_not_lower: '', dependency_warning_level: 'caution_signal', evidence_summary: '', rank_explanation: '', prerequisite_explanation: '', safe_next_action: '', finish_definition: '' },
        { requested_rank: 3, system_id: 'CDE', classification: 'active_system', recommended_action: 'harden', why_now: 'cde', prerequisite_systems: [], minimum_safe_prompt_scope: 'scope', risk_if_built_before_prerequisites: 'do_not_touch', build_now_assessment: 'caution_signal', why_not_higher: '', why_not_lower: '', dependency_warning_level: 'caution_signal', evidence_summary: '', rank_explanation: '', prerequisite_explanation: '', safe_next_action: '', finish_definition: '' },
      ],
    }), CONTRACT);
    expect(result.cards.map((c) => c.system_id)).toEqual(['EVL', 'TPA', 'CDE']);
  });
});

describe('buildLeverageQueueFromRoadmap', () => {
  const roadmap = {
    safe_bundles: [
      { bundle_id: 'TLS-BND-01', steps: ['TLS-EVL-01'], rationale: 'eval bundle' },
      { bundle_id: 'TLS-BND-02', steps: ['TLS-TPA-02'], rationale: 'tpa bundle' },
    ],
    entries: [
      { id: 'TLS-EVL-01', title: 'Eval bundle', why_it_matters: 'eval gates', dependencies: ['EVL', 'PQX'] },
      { id: 'TLS-TPA-02', title: 'TPA bundle', why_it_matters: 'trust gates', dependencies: ['TPA'] },
    ],
  };

  it('compresses each bundle into a single card with dependency_count', () => {
    const result = buildLeverageQueueFromRoadmap(roadmap, []);
    expect(result.queues.queue_1_immediate_next_bundle[0].dependency_count).toBe(2);
    expect(result.queues.queue_2_next_hardening_bundle[0].dependency_count).toBe(1);
  });

  it('links queue card to a top-3 system when one of its steps mentions it', () => {
    const result = buildLeverageQueueFromRoadmap(roadmap, ['EVL', 'TPA']);
    expect(result.queues.queue_1_immediate_next_bundle[0].linked_top3_system_id).toBe('EVL');
    expect(result.queues.queue_2_next_hardening_bundle[0].linked_top3_system_id).toBe('TPA');
  });

  it('does not invent systems even when bundle id resembles one', () => {
    // bundle_id TLS-BND-01 is a roadmap label, not a system. The queue must
    // reflect that — no graph node, no decision-layer placement.
    const result = buildLeverageQueueFromRoadmap(roadmap, ['EVL']);
    const card = result.queues.queue_1_immediate_next_bundle[0];
    expect(card.bundle_id).toBe('TLS-BND-01');
    expect(card.linked_top3_system_id).toBe('EVL');
  });

  it('returns warning when artifact missing', () => {
    const result = buildLeverageQueueFromRoadmap(null);
    expect(result.warning).toMatch(/Leverage queue unavailable/);
  });
});
