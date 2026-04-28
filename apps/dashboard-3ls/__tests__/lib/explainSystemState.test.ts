/**
 * D3L-REGISTRY-01 — Deterministic Explain System State tests.
 *
 * Same inputs → same output. No free-form text. Unknown root cause must
 * be explicit; non-registry Top 3 entries must surface as a note.
 */
import { explainSystemState } from '@/lib/explainSystemState';
import { parseRegistryContractFromArtifact } from '@/lib/registryContract';
import type { SystemGraphPayload } from '@/lib/systemGraph';
import type { PriorityArtifactLoadResult } from '@/lib/artifactLoader';

const CONTRACT = parseRegistryContractFromArtifact({
  active_systems: ['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL'].map((id) => ({
    system_id: id,
    status: 'active',
    purpose: '',
    upstream: [],
    downstream: [],
  })),
  future_systems: [],
  merged_or_demoted: [],
  canonical_loop: ['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL'],
  canonical_overlays: [],
});

const GRAPH: SystemGraphPayload = {
  graph_state: 'blocked_signal',
  generated_at: '2026-04-28T00:00:00.000Z',
  source_mix: { artifact_store: 4, repo_registry: 0, derived: 0, stub_fallback: 0, missing: 0 },
  trust_posture: 'blocked_signal',
  nodes: [
    { system_id: 'EVL', label: 'EVL', layer: 'core', role: 'eval', trust_state: 'blocked_signal', artifact_backed_percent: 100, source_type: 'artifact_store', trust_gap_signals: ['missing_eval'], upstream: [], downstream: ['TPA'], source_artifact_refs: [], warning_count: 1, is_focus: true, is_fallback_backed: false, is_disconnected: false, why_blocked: 'missing eval coverage', upstream_blockers: [], failed_evals: ['missing_eval'], missing_artifacts: [] },
    { system_id: 'TPA', label: 'TPA', layer: 'core', role: 'trust', trust_state: 'blocked_signal', artifact_backed_percent: 100, source_type: 'artifact_store', trust_gap_signals: [], upstream: ['EVL'], downstream: [], source_artifact_refs: [], warning_count: 0, is_focus: true, is_fallback_backed: false, is_disconnected: false, why_blocked: 'upstream EVL blocking', upstream_blockers: ['EVL'], failed_evals: [], missing_artifacts: [] },
  ],
  edges: [{ from: 'EVL', to: 'TPA', edge_type: 'dependency', source_type: 'artifact_store', source_artifact_ref: '', confidence: 1, is_failure_path: true, is_broken: false }],
  focus_systems: ['EVL', 'TPA'],
  failure_path: ['EVL', 'TPA'],
  missing_artifacts: [],
  warnings: [],
  replay_commands: [],
};

const PRIORITY_OK: PriorityArtifactLoadResult = {
  state: 'ok',
  generated_at: '2026-04-28T00:00:00.000Z',
  source_path: 'artifacts/system_dependency_priority_report.json',
  payload: {
    schema_version: 'tls-06.v1',
    phase: 'TLS-06',
    priority_order: [],
    penalties: [],
    ranked_systems: [],
    global_ranked_systems: [],
    top_5: [
      { rank: 1, system_id: 'EVL', classification: 'active_system', score: 100, action: 'finish_hardening', why_now: 'eval missing', trust_gap_signals: ['missing_eval'], dependencies: { upstream: [], downstream: ['TPA'] }, unlocks: [], finish_definition: 'close', next_prompt: 'TLS-FIX-EVL', trust_state: 'blocked_signal' },
      { rank: 2, system_id: 'TPA', classification: 'active_system', score: 90, action: 'harden', why_now: 'tpa', trust_gap_signals: [], dependencies: { upstream: [], downstream: [] }, unlocks: [], finish_definition: '', next_prompt: '', trust_state: 'blocked_signal' },
      { rank: 3, system_id: 'CDE', classification: 'active_system', score: 80, action: 'harden', why_now: 'cde', trust_gap_signals: [], dependencies: { upstream: [], downstream: [] }, unlocks: [], finish_definition: '', next_prompt: '', trust_state: 'blocked_signal' },
    ],
    requested_candidate_set: [],
    requested_candidate_ranking: [],
    ambiguous_requested_candidates: [],
  },
};

describe('explainSystemState', () => {
  it('produces the same explanation snapshot for identical inputs', () => {
    const a = explainSystemState({ graph: GRAPH, priority: PRIORITY_OK, contract: CONTRACT });
    const b = explainSystemState({ graph: GRAPH, priority: PRIORITY_OK, contract: CONTRACT });
    expect(a).toEqual(b);
  });

  it('identifies root cause as the upstream-most failure-path node', () => {
    const result = explainSystemState({ graph: GRAPH, priority: PRIORITY_OK, contract: CONTRACT });
    expect(result.root_cause.system_id).toBe('EVL');
    expect(result.propagation_path).toEqual(['EVL', 'TPA']);
  });

  it('returns Unknown root cause when graph has no failure path', () => {
    const cleanGraph: SystemGraphPayload = { ...GRAPH, failure_path: [] };
    const result = explainSystemState({ graph: cleanGraph, priority: PRIORITY_OK, contract: CONTRACT });
    expect(result.root_cause.system_id).toBeNull();
    expect(result.root_cause.taxonomy).toBe('none');
  });

  it('reports missing data when graph and priority artifacts are absent', () => {
    const result = explainSystemState({
      graph: null,
      priority: { state: 'missing', payload: null, reason: 'not_found' },
      contract: CONTRACT,
    });
    expect(result.root_cause.system_id).toBeNull();
    expect(result.root_cause.taxonomy).toBe('unknown');
    expect(result.missing_data.length).toBeGreaterThan(0);
  });

  it('flags non-registry top-3 entries in notes', () => {
    const offTopPriority: PriorityArtifactLoadResult = {
      ...PRIORITY_OK,
      payload: {
        ...PRIORITY_OK.payload!,
        top_5: [
          { rank: 1, system_id: 'H01', classification: 'h_slice', score: 87, action: 'harden', why_now: 'gap', trust_gap_signals: [], dependencies: { upstream: [], downstream: [] }, unlocks: [], finish_definition: '', next_prompt: '', trust_state: 'blocked_signal' },
          ...PRIORITY_OK.payload!.top_5.slice(1),
        ],
      },
    };
    const result = explainSystemState({ graph: GRAPH, priority: offTopPriority, contract: CONTRACT });
    const top1 = result.top_three_fix_targets[0];
    expect(top1.system_id).toBe('H01');
    expect(top1.is_registry_backed).toBe(false);
    expect(result.notes.some((n) => n.includes('non-registry'))).toBe(true);
  });
});
