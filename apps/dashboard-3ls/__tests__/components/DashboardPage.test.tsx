import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import DashboardPage from '@/app/page';

global.fetch = jest.fn();

const mockHealth = { warnings: ['health_warn'] };

const mockPriority = {
  state: 'ok',
  payload: {
    schema_version: 'tls-04.v1',
    phase: 'TLS-04',
    priority_order: ['H01', 'RFX', 'HOP'],
    penalties: [],
    ranked_systems: [],
    global_ranked_systems: [],
    top_5: [],
    requested_candidate_set: ['H01', 'RFX', 'HOP'],
    ambiguous_requested_candidates: [],
    requested_candidate_ranking: [
      {
        requested_rank: 1,
        system_id: 'H01',
        classification: 'h_slice',
        recommended_action: 'harden_authority',
        why_now: 'high trust gaps',
        prerequisite_systems: ['AEX'],
        minimum_safe_prompt_scope: 'single-system hardening',
        risk_if_built_before_prerequisites: 'do_not_touch upstream ownership',
      },
      {
        requested_rank: 2,
        system_id: 'RFX',
        classification: 'fix_bundle',
        recommended_action: 'stabilize retries',
        why_now: 'repeat failures',
        prerequisite_systems: [],
        minimum_safe_prompt_scope: 'retry boundary fix only',
        risk_if_built_before_prerequisites: 'avoid control transfer',
      },
      {
        requested_rank: 3,
        system_id: 'HOP',
        classification: 'h_slice',
        recommended_action: 'close handoff gaps',
        why_now: 'lineage instability',
        prerequisite_systems: ['RFX'],
        minimum_safe_prompt_scope: 'handoff schema hardening',
        risk_if_built_before_prerequisites: 'do_not_touch downstream enforcers',
      },
    ],
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
  generated_at: '2026-04-27T00:00:00.000Z',
  source_mix: { artifact_store: 8, repo_registry: 2, derived: 0, stub_fallback: 2, missing: 0 },
  trust_posture: 'freeze_signal',
  nodes: [],
  edges: [],
  focus_systems: [],
  failure_path: [],
  missing_artifacts: [],
  warnings: ['graph_warn'],
  replay_commands: [],
};

const mockRoadmap = {
  state: 'ok',
  payload: {
    safe_bundles: [
      { bundle_id: 'TLS-BND-01', steps: ['TLS-FX-01', 'TLS-RT-01', 'TLS-FIX-01'], rationale: 'Boundary hardening.' },
      { bundle_id: 'TLS-BND-02', steps: ['TLS-FX-02', 'TLS-RT-02', 'TLS-FIX-02'], rationale: 'Integration hardening.' },
      { bundle_id: 'TLS-BND-03', steps: ['TLS-FX-03', 'TLS-RT-03', 'TLS-FIX-03'], rationale: 'Review/fix hardening.' },
      { bundle_id: 'TLS-BND-09', steps: ['TLS-FIX-08', 'TLS-FX-10', 'TLS-RT-09'], rationale: 'Later work.' },
    ],
    entries: [
      { id: 'TLS-FX-01', title: 'Boundary map bundle', why_it_matters: 'Defines clear boundary.', dependencies: ['artifact-a'] },
      { id: 'TLS-FX-02', title: 'Integration seam bundle', why_it_matters: 'Prevents regressions.', dependencies: ['TLS-FIX-01'] },
      { id: 'TLS-FX-03', title: 'Ranking trust calibration bundle', why_it_matters: 'Stabilizes order.', dependencies: ['TLS-FIX-02'] },
      { id: 'TLS-FIX-08', title: 'Dataset+eval fix bundle', why_it_matters: 'Maintains eligibility.', dependencies: ['TLS-RT-08'] },
    ],
  },
  table_markdown: '| ID | Phase |',
  source_artifacts_used: ['artifacts/tls/tls_roadmap_final.json'],
};

function setupFetch(overrides?: Partial<Record<string, unknown>>) {
  (global.fetch as jest.Mock).mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes('/api/health')) return Promise.resolve({ ok: true, json: async () => overrides?.health ?? mockHealth });
    if (url.includes('/api/priority')) return Promise.resolve({ ok: true, json: async () => overrides?.priority ?? mockPriority });
    if (url.includes('/api/system-flow')) return Promise.resolve({ ok: true, json: async () => overrides?.flow ?? mockFlow });
    if (url.includes('/api/system-graph')) return Promise.resolve({ ok: true, json: async () => overrides?.graph ?? mockGraph });
    if (url.includes('/api/tls-roadmap')) return Promise.resolve({ ok: true, json: async () => overrides?.roadmap ?? mockRoadmap });
    if (url.includes('/api/intelligence')) return Promise.resolve({ ok: true, json: async () => ({ data_source: 'artifact_store' }) });
    return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
  });
}

describe('DashboardPage simplified cockpit', () => {
  beforeEach(() => {
    (global.fetch as jest.Mock).mockClear();
  });

  it('overview shows only 4 sections', async () => {
    setupFetch();
    render(<DashboardPage />);
    await waitFor(() => expect(screen.getByTestId('overview-tab')).toBeInTheDocument());
    expect(screen.getAllByTestId('overview-section')).toHaveLength(4);
  });

  it('top 3 cards are extracted from artifact rows without re-ranking', async () => {
    setupFetch();
    render(<DashboardPage />);
    await waitFor(() => expect(screen.getAllByTestId('top3-card')).toHaveLength(3));
    const first = screen.getAllByTestId('top3-card')[0];
    expect(first.textContent).toContain('H01');
    expect(screen.getByText(/Dashboard does not compute ranking/i)).toBeInTheDocument();
  });

  it('leverage queue is derived from roadmap safe bundles', async () => {
    setupFetch();
    render(<DashboardPage />);
    await waitFor(() => expect(screen.getAllByTestId('leverage-queue-item').length).toBeGreaterThan(0));
    expect(screen.getByText(/Queue 1: immediate next bundle/i)).toBeInTheDocument();
    expect(screen.getByText(/Run bundle TLS-BND-01/i)).toBeInTheDocument();
  });

  it('missing artifacts show fail-closed warnings', async () => {
    setupFetch({ priority: { state: 'missing', payload: null }, roadmap: { state: 'missing', payload: null, table_markdown: null }, flow: { state: 'missing', payload: null } });
    render(<DashboardPage />);
    await waitFor(() => expect(screen.getByTestId('overview-tab')).toBeInTheDocument());
    expect(screen.getByTestId('top3-warning')).toBeInTheDocument();
    expect(screen.getByTestId('queue-warning')).toBeInTheDocument();
    expect(screen.getByTestId('flow-warning')).toBeInTheDocument();
  });

  it('tabs exist and isolate complexity panels', async () => {
    setupFetch();
    render(<DashboardPage />);
    await waitFor(() => expect(screen.getByTestId('tab-roadmap')).toBeInTheDocument());

    ['overview', 'graph', 'prioritization', 'sources', 'diagnostics', 'roadmap', 'raw'].forEach((tab) => {
      expect(screen.getByTestId(`tab-${tab}`)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('tab-roadmap'));
    await waitFor(() => expect(screen.getByTestId('roadmap-tab')).toBeInTheDocument());
    expect(screen.queryByTestId('overview-tab')).not.toBeInTheDocument();
  });

  it('flow edges are rendered from artifact-provided dependencies', async () => {
    setupFetch();
    render(<DashboardPage />);
    await waitFor(() => expect(screen.getByTestId('flow-edges')).toBeInTheDocument());
    expect(screen.getByText('AEX → PQX')).toBeInTheDocument();
    expect(screen.getByText('PQX → EVL')).toBeInTheDocument();
  });

  it('top 3 ordering is preserved from artifact (no dashboard-side rerank)', async () => {
    const reorderedPriority = {
      ...mockPriority,
      payload: {
        ...mockPriority.payload,
        requested_candidate_ranking: [
          {
            requested_rank: 1,
            system_id: 'HOP',
            classification: 'h_slice',
            recommended_action: 'close handoff gaps',
            why_now: 'lineage instability',
            prerequisite_systems: ['RFX'],
            minimum_safe_prompt_scope: 'handoff schema hardening',
            risk_if_built_before_prerequisites: 'do_not_touch downstream enforcers',
          },
          {
            requested_rank: 2,
            system_id: 'H01',
            classification: 'h_slice',
            recommended_action: 'harden authority',
            why_now: 'high trust gaps',
            prerequisite_systems: ['AEX'],
            minimum_safe_prompt_scope: 'single-system hardening',
            risk_if_built_before_prerequisites: 'do_not_touch upstream ownership',
          },
          {
            requested_rank: 3,
            system_id: 'RFX',
            classification: 'fix_bundle',
            recommended_action: 'stabilize retries',
            why_now: 'repeat failures',
            prerequisite_systems: [],
            minimum_safe_prompt_scope: 'retry boundary fix only',
            risk_if_built_before_prerequisites: 'avoid control transfer',
          },
        ],
      },
    };
    setupFetch({ priority: reorderedPriority });
    render(<DashboardPage />);
    await waitFor(() => expect(screen.getAllByTestId('top3-card')).toHaveLength(3));
    const cards = screen.getAllByTestId('top3-card');
    expect(cards[0].textContent).toContain('HOP');
    expect(cards[1].textContent).toContain('H01');
    expect(cards[2].textContent).toContain('RFX');
  });

  it('renders no flow edges when artifact has none (no hardcoded graph edges)', async () => {
    const emptyFlow = {
      state: 'ok',
      payload: {
        canonical_loop: ['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL'],
        canonical_overlays: ['REP', 'LIN', 'OBS', 'SLO'],
        active_systems: [
          { system_id: 'AEX', upstream: [], downstream: [] },
          { system_id: 'PQX', upstream: [], downstream: [] },
          { system_id: 'EVL', upstream: [], downstream: [] },
          { system_id: 'TPA', upstream: [], downstream: [] },
          { system_id: 'CDE', upstream: [], downstream: [] },
          { system_id: 'SEL', upstream: [], downstream: [] },
        ],
      },
    };
    setupFetch({ flow: emptyFlow });
    render(<DashboardPage />);
    await waitFor(() => expect(screen.getByTestId('flow-edges')).toBeInTheDocument());
    expect(screen.getByTestId('flow-edges').children.length).toBe(0);
    expect(screen.getByTestId('flow-warning')).toBeInTheDocument();
  });

  it('trust pulse is visible on the overview with all five fields', async () => {
    setupFetch();
    render(<DashboardPage />);
    await waitFor(() => expect(screen.getByTestId('overview-tab')).toBeInTheDocument());
    expect(screen.getByText(/A\. Trust Pulse/i)).toBeInTheDocument();
    expect(screen.getByText(/trust state:/i)).toBeInTheDocument();
    expect(screen.getByText(/artifact-backed %:/i)).toBeInTheDocument();
    expect(screen.getByText(/stub fallback %:/i)).toBeInTheDocument();
    expect(screen.getByText(/last recompute:/i)).toBeInTheDocument();
    expect(screen.getByText(/warning count:/i)).toBeInTheDocument();
  });

  it('critical warnings are surfaced via trust pulse warning count', async () => {
    setupFetch();
    render(<DashboardPage />);
    await waitFor(() => expect(screen.getByTestId('overview-tab')).toBeInTheDocument());
    const warningLine = screen.getByText(/warning count:/i).closest('li');
    expect(warningLine?.textContent ?? '').toMatch(/2/);
  });
});
