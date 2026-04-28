/**
 * D3L-MASTER-01 Phase 1 — priority freshness gate tests.
 *
 * Covers the full fail-closed contract:
 *   - missing artifact ⇒ status missing, ok=false
 *   - stale (>24h) ⇒ status stale, ok=false
 *   - invalid JSON ⇒ status invalid_schema, ok=false
 *   - missing generated_at ⇒ invalid_timestamp
 *   - top_5 references non-active id ⇒ status non_active_in_top_5
 *   - missing registry contract ⇒ status contract_missing
 *   - everything good ⇒ status ok
 */
import fs from 'fs';
import os from 'os';
import path from 'path';
import { evaluatePriorityFreshnessGate } from '@/lib/artifactLoader';

function tmpRepo(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'd3l-gate-'));
}

const VALID_PRIORITY = {
  schema_version: 'tls-04.v1',
  phase: 'TLS-04',
  priority_order: ['a', 'b', 'c', 'd', 'e'],
  penalties: [],
  ranked_systems: [],
  global_ranked_systems: [
    { rank: 1, system_id: 'EVL', classification: 'active', score: 1, action: 'x', why_now: 'y', trust_gap_signals: [], dependencies: { upstream: [], downstream: [] }, unlocks: [], finish_definition: '', next_prompt: '', trust_state: 'caution_signal' },
  ],
  top_5: [
    { rank: 1, system_id: 'EVL', classification: 'active', score: 1, action: 'x', why_now: 'y', trust_gap_signals: [], dependencies: { upstream: [], downstream: [] }, unlocks: [], finish_definition: '', next_prompt: '', trust_state: 'caution_signal' },
  ],
  requested_candidate_set: [],
  requested_candidate_ranking: [],
  ambiguous_requested_candidates: [],
  generated_at: '2026-04-28T07:00:00Z',
};

const VALID_CONTRACT = {
  artifact_type: 'd3l_registry_contract',
  phase: 'D3L-MASTER-01',
  schema_version: 'd3l-master-01.v1',
  source_artifact: 'artifacts/tls/system_registry_dependency_graph.json',
  active_system_ids: ['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL'],
  future_system_ids: ['ABX'],
  deprecated_or_merged_system_ids: ['SUP'],
  excluded_ids: ['ABX', 'SUP'],
  ranking_universe: ['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL'],
  maturity_universe: ['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL'],
  forbidden_node_examples: ['H01', 'TLS-BND-01'],
  rules: [],
};

function setupRepo(opts: { priority?: unknown; contract?: unknown; rawPriority?: string }): string {
  const dir = tmpRepo();
  fs.mkdirSync(path.join(dir, 'artifacts', 'tls'), { recursive: true });
  if (opts.priority !== undefined) {
    fs.writeFileSync(path.join(dir, 'artifacts', 'system_dependency_priority_report.json'), JSON.stringify(opts.priority));
  } else if (opts.rawPriority !== undefined) {
    fs.writeFileSync(path.join(dir, 'artifacts', 'system_dependency_priority_report.json'), opts.rawPriority);
  }
  if (opts.contract !== undefined) {
    fs.writeFileSync(path.join(dir, 'artifacts', 'tls', 'd3l_registry_contract.json'), JSON.stringify(opts.contract));
  }
  return dir;
}

describe('evaluatePriorityFreshnessGate', () => {
  const originalRepoRoot = process.env.REPO_ROOT;

  afterEach(() => {
    if (originalRepoRoot === undefined) {
      delete process.env.REPO_ROOT;
    } else {
      process.env.REPO_ROOT = originalRepoRoot;
    }
  });

  it('returns ok when artifact is fresh and registry-aligned', () => {
    const dir = setupRepo({ priority: VALID_PRIORITY, contract: VALID_CONTRACT });
    process.env.REPO_ROOT = dir;
    const gate = evaluatePriorityFreshnessGate(new Date('2026-04-28T08:00:00Z'));
    expect(gate.ok).toBe(true);
    expect(gate.status).toBe('ok');
    expect(gate.non_active_in_top_5).toEqual([]);
    expect(gate.ranking_universe_size).toBe(6);
  });

  it('blocks when priority artifact missing', () => {
    const dir = setupRepo({ contract: VALID_CONTRACT });
    process.env.REPO_ROOT = dir;
    const gate = evaluatePriorityFreshnessGate(new Date('2026-04-28T08:00:00Z'));
    expect(gate.ok).toBe(false);
    expect(gate.status).toBe('missing');
    expect(gate.blocking_reasons.length).toBeGreaterThan(0);
    expect(gate.recompute_command).toContain('build_tls_dependency_priority.py');
  });

  it('blocks when timestamp is stale (older than 24h)', () => {
    const stale = { ...VALID_PRIORITY, generated_at: '2018-01-01T00:00:00Z' };
    const dir = setupRepo({ priority: stale, contract: VALID_CONTRACT });
    process.env.REPO_ROOT = dir;
    const gate = evaluatePriorityFreshnessGate(new Date('2026-04-28T08:00:00Z'));
    expect(gate.ok).toBe(false);
    expect(gate.status).toBe('stale');
  });

  it('blocks when generated_at is malformed', () => {
    const bad = { ...VALID_PRIORITY, generated_at: 'not-a-real-date' };
    const dir = setupRepo({ priority: bad, contract: VALID_CONTRACT });
    process.env.REPO_ROOT = dir;
    const gate = evaluatePriorityFreshnessGate(new Date('2026-04-28T08:00:00Z'));
    expect(gate.ok).toBe(false);
    expect(gate.status).toBe('invalid_timestamp');
  });

  it('blocks when generated_at is missing', () => {
    const bad: Record<string, unknown> = { ...VALID_PRIORITY };
    delete bad.generated_at;
    const dir = setupRepo({ priority: bad, contract: VALID_CONTRACT });
    process.env.REPO_ROOT = dir;
    const gate = evaluatePriorityFreshnessGate(new Date('2026-04-28T08:00:00Z'));
    expect(gate.ok).toBe(false);
    expect(gate.status).toBe('invalid_timestamp');
  });

  it('blocks when JSON is invalid', () => {
    const dir = setupRepo({ rawPriority: '{not-json', contract: VALID_CONTRACT });
    process.env.REPO_ROOT = dir;
    const gate = evaluatePriorityFreshnessGate(new Date('2026-04-28T08:00:00Z'));
    expect(gate.ok).toBe(false);
    expect(gate.status).toBe('invalid_schema');
  });

  it('blocks when registry contract is missing', () => {
    const dir = setupRepo({ priority: VALID_PRIORITY });
    process.env.REPO_ROOT = dir;
    const gate = evaluatePriorityFreshnessGate(new Date('2026-04-28T08:00:00Z'));
    expect(gate.ok).toBe(false);
    expect(gate.status).toBe('contract_missing');
  });

  it('blocks when top_5 references a non-active system_id', () => {
    const bad = {
      ...VALID_PRIORITY,
      top_5: [
        { ...VALID_PRIORITY.top_5[0], system_id: 'H01' },
      ],
    };
    const dir = setupRepo({ priority: bad, contract: VALID_CONTRACT });
    process.env.REPO_ROOT = dir;
    const gate = evaluatePriorityFreshnessGate(new Date('2026-04-28T08:00:00Z'));
    expect(gate.ok).toBe(false);
    expect(gate.status).toBe('non_active_in_top_5');
    expect(gate.non_active_in_top_5).toContain('H01');
  });

  it('reports non_active_in_global without blocking when top_5 stays clean', () => {
    const mixed = {
      ...VALID_PRIORITY,
      global_ranked_systems: [
        { ...VALID_PRIORITY.top_5[0], system_id: 'EVL' },
        { ...VALID_PRIORITY.top_5[0], system_id: 'H01', rank: 14 },
      ],
    };
    const dir = setupRepo({ priority: mixed, contract: VALID_CONTRACT });
    process.env.REPO_ROOT = dir;
    const gate = evaluatePriorityFreshnessGate(new Date('2026-04-28T08:00:00Z'));
    expect(gate.ok).toBe(true);
    expect(gate.non_active_in_global).toEqual(['H01']);
  });
});
