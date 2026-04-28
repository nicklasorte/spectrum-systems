/**
 * D3L-DATA-REGISTRY-01 — Operator complexity-budget tests.
 *
 * These tests pin the operator-facing surfaces called out in
 * artifacts/tls/d3l_operator_complexity_budget.json. They are not
 * stylistic — they assert that an operator can find each critical
 * surface within the documented budget.
 */
import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import DashboardPage from '@/app/page';

global.fetch = jest.fn();

const mockHealth = { warnings: ['health_warn'] };

const mockPriority = {
  state: 'ok',
  generated_at: '2026-04-28T00:00:00Z',
  payload: {
    schema_version: 'tls-06.v1',
    phase: 'TLS-06',
    generated_at: '2026-04-28T00:00:00Z',
    priority_order: [],
    penalties: [],
    ranked_systems: [],
    global_ranked_systems: [],
    top_5: [
      { rank: 1, system_id: 'EVL', classification: 'active_system', score: 100, action: 'finish hardening', why_now: 'on canonical loop', trust_gap_signals: ['missing_eval'], dependencies: { upstream: ['PQX'], downstream: ['TPA'] }, unlocks: ['CDE'], finish_definition: 'close gaps', next_prompt: 'run TLS-FIX-EVL', trust_state: 'freeze_signal' },
      { rank: 2, system_id: 'TPA', classification: 'active_system', score: 90, action: 'attach trust pulse', why_now: 'trust handoff incomplete', trust_gap_signals: [], dependencies: { upstream: ['EVL'], downstream: ['CDE'] }, unlocks: ['CDE'], finish_definition: 'close trust gaps', next_prompt: 'run TLS-FIX-TPA', trust_state: 'caution_signal' },
      { rank: 3, system_id: 'CDE', classification: 'active_system', score: 80, action: 'finish control authority', why_now: 'control gap', trust_gap_signals: [], dependencies: { upstream: ['TPA'], downstream: ['SEL'] }, unlocks: ['SEL'], finish_definition: 'close control gaps', next_prompt: 'run TLS-FIX-CDE', trust_state: 'caution_signal' },
    ],
    requested_candidate_set: [],
    requested_candidate_ranking: [],
    ambiguous_requested_candidates: [],
  },
};

const mockFlow = {
  state: 'ok',
  payload: {
    canonical_loop: ['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL'],
    canonical_overlays: ['REP', 'LIN', 'OBS', 'SLO'],
    active_systems: [
      { system_id: 'AEX', upstream: [], downstream: ['PQX'] },
      { system_id: 'PQX', upstream: ['AEX'], downstream: ['EVL'] },
      { system_id: 'EVL', upstream: ['PQX'], downstream: ['TPA'] },
      { system_id: 'TPA', upstream: ['EVL'], downstream: ['CDE'] },
      { system_id: 'CDE', upstream: ['TPA'], downstream: ['SEL'] },
      { system_id: 'SEL', upstream: ['CDE'], downstream: [] },
    ],
  },
};

const mockGraph = {
  graph_state: 'freeze_signal',
  generated_at: '2026-04-28T00:00:00Z',
  source_mix: { artifact_store: 8, repo_registry: 2, derived: 0, stub_fallback: 0, missing: 0 },
  trust_posture: 'freeze_signal',
  nodes: [],
  edges: [],
  focus_systems: [],
  failure_path: [],
  missing_artifacts: [],
  warnings: [],
  replay_commands: [],
};

const mockRoadmap = {
  state: 'ok',
  payload: {
    safe_bundles: [
      { bundle_id: 'TLS-BND-01', steps: ['TLS-FX-01', 'TLS-RT-01', 'TLS-FIX-01'], rationale: 'Boundary hardening before integration.' },
      { bundle_id: 'TLS-BND-02', steps: ['TLS-FX-02', 'TLS-RT-02', 'TLS-FIX-02'], rationale: 'Integration hardening.' },
    ],
    entries: [
      { id: 'TLS-FX-01', title: 'Boundary map bundle', why_it_matters: 'Defines TLS boundaries before integration.', dependencies: ['artifact-a'] },
      { id: 'TLS-FX-02', title: 'Integration seam bundle', why_it_matters: 'Prevents regressions.', dependencies: ['TLS-FIX-01'] },
    ],
  },
  table_markdown: '| ID | Phase |',
  source_artifacts_used: ['artifacts/tls/tls_roadmap_final.json'],
};

const mockExplain = {
  trust_state: 'freeze_signal',
  generated_at: '2026-04-28T00:00:00Z',
  root_cause: { system_id: null, taxonomy: 'unknown', reason: 'no failure path declared', explanation: 'no failure path declared by graph artifact', artifact_backed: false },
  missing_signals: [],
  downstream_impact: [],
  propagation_path: [],
  top_three_fix_targets: [],
  next_safe_action: 'regenerate priority artifact',
  missing_data: [],
  notes: [],
};

const mockOcBottleneck = { state: 'unavailable', card: null, reason: 'OC bottleneck artifact not present', sources: [] };

function setupFetch(overrides?: Partial<Record<string, unknown>>) {
  (global.fetch as jest.Mock).mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes('/api/health')) return Promise.resolve({ ok: true, json: async () => overrides?.health ?? mockHealth });
    if (url.includes('/api/priority')) return Promise.resolve({ ok: true, json: async () => overrides?.priority ?? mockPriority });
    if (url.includes('/api/system-flow')) return Promise.resolve({ ok: true, json: async () => overrides?.flow ?? mockFlow });
    if (url.includes('/api/system-graph')) return Promise.resolve({ ok: true, json: async () => overrides?.graph ?? mockGraph });
    if (url.includes('/api/tls-roadmap')) return Promise.resolve({ ok: true, json: async () => overrides?.roadmap ?? mockRoadmap });
    if (url.includes('/api/intelligence')) return Promise.resolve({ ok: true, json: async () => ({ data_source: 'artifact_store' }) });
    if (url.includes('/api/registry-contract')) return Promise.resolve({ ok: true, json: async () => ({ allowed_active_node_ids: ['EVL', 'TPA', 'CDE'] }) });
    if (url.includes('/api/explain-state')) return Promise.resolve({ ok: true, json: async () => overrides?.explain ?? mockExplain });
    if (url.includes('/api/decision-layer')) return Promise.resolve({ ok: true, json: async () => ({ groups: [], allowed_active_node_ids: [] }) });
    if (url.includes('/api/oc-bottleneck')) return Promise.resolve({ ok: true, json: async () => overrides?.ocBottleneck ?? mockOcBottleneck });
    if (url.includes('/api/maturity')) return Promise.resolve({ ok: true, json: async () => overrides?.maturity ?? { status: 'ok', generated_at: '', blocking_reasons: [], rows: [], maturity_universe_size: 0, level_counts: { 0: 0, 1: 0, 2: 0, 3: 0, 4: 0 }, staleness_caps_applied: 0, warnings: [] } });
    return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
  });
}

describe('Operator complexity budget', () => {
  beforeEach(() => {
    (global.fetch as jest.Mock).mockClear();
  });

  it('overview has at most 5 sections (budget)', async () => {
    setupFetch();
    render(<DashboardPage />);
    await waitFor(() => expect(screen.getByTestId('overview-tab')).toBeInTheDocument());
    expect(screen.getAllByTestId('overview-section').length).toBeLessThanOrEqual(5);
  });

  it('operator can find trust state in 1 element on Overview', async () => {
    setupFetch();
    render(<DashboardPage />);
    await waitFor(() => expect(screen.getByTestId('overview-tab')).toBeInTheDocument());
    expect(screen.getByTestId('trust-pulse-label')).toBeInTheDocument();
  });

  it('operator can find Top 3 or a stale reason on Overview', async () => {
    setupFetch();
    render(<DashboardPage />);
    await waitFor(() => expect(screen.getByTestId('overview-tab')).toBeInTheDocument());
    const cards = screen.queryAllByTestId('top3-card');
    const warning = screen.queryByTestId('top3-warning');
    expect(cards.length > 0 || warning).toBeTruthy();
  });

  it('top 3 card uses the compact Fix / Why / Next / Boundary format', async () => {
    setupFetch();
    render(<DashboardPage />);
    await waitFor(() => expect(screen.getAllByTestId('top3-card').length).toBeGreaterThan(0));
    const first = screen.getAllByTestId('top3-card')[0];
    expect(first.textContent).toMatch(/Fix:/);
    expect(first.textContent).toMatch(/Why:/);
    expect(first.textContent).toMatch(/Next:/);
    expect(first.textContent).toMatch(/Boundary:/);
  });

  it('overview no longer renders leverage queue items (D3L-MASTER-01 Phase 8)', async () => {
    setupFetch();
    render(<DashboardPage />);
    await waitFor(() => expect(screen.getByTestId('overview-tab')).toBeInTheDocument());
    expect(screen.queryAllByTestId('leverage-queue-item')).toHaveLength(0);
  });

  it('full roadmap detail lives in the Roadmap tab, not Overview', async () => {
    setupFetch();
    render(<DashboardPage />);
    await waitFor(() => expect(screen.getByTestId('overview-tab')).toBeInTheDocument());
    // Overview should NOT contain the roadmap markdown table.
    expect(screen.queryByTestId('roadmap-full-queues')).toBeNull();

    fireEvent.click(screen.getByTestId('tab-roadmap'));
    await waitFor(() => expect(screen.getByTestId('roadmap-tab')).toBeInTheDocument());
    expect(screen.getByTestId('roadmap-full-queues')).toBeInTheDocument();
  });

  it('stale priority artifact does NOT render Top 3 cards as actionable', async () => {
    setupFetch({
      priority: {
        state: 'stale',
        generated_at: '2018-10-20T01:46:40.000Z',
        payload: mockPriority.payload,
        recompute_command: 'python scripts/build_tls_dependency_priority.py --candidates HOP,RAX,RSM,CAP,SEC,EVL,OBS,SLO --fail-if-missing',
        reason: 'older_than_threshold:age_hours=66000',
      },
    });
    render(<DashboardPage />);
    await waitFor(() => expect(screen.getByTestId('overview-tab')).toBeInTheDocument());
    expect(screen.queryAllByTestId('top3-card')).toHaveLength(0);
    expect(screen.getByTestId('top3-warning').textContent).toMatch(/stale/i);
    expect(screen.getByTestId('top3-fail-closed').textContent).toMatch(/build_tls_dependency_priority/);
  });

  it('missing-generated_at priority artifact does NOT render Top 3 cards', async () => {
    setupFetch({
      priority: {
        state: 'invalid_timestamp',
        payload: mockPriority.payload,
        recompute_command: 'python scripts/build_tls_dependency_priority.py --candidates HOP,RAX,RSM,CAP,SEC,EVL,OBS,SLO --fail-if-missing',
        reason: 'generated_at_missing',
      },
    });
    render(<DashboardPage />);
    await waitFor(() => expect(screen.getByTestId('overview-tab')).toBeInTheDocument());
    expect(screen.queryAllByTestId('top3-card')).toHaveLength(0);
    expect(screen.getByTestId('top3-warning').textContent).toMatch(/invalid_timestamp|stale/i);
  });
});
