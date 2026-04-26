import React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import DashboardPage from '@/app/page';

global.fetch = jest.fn();

const mockHealth = {
  data_source: 'artifact_store',
  generated_at: '2026-04-25T00:00:00.000Z',
  source_artifacts_used: ['artifacts/dashboard/repo_snapshot.json'],
  warnings: [],
  systems: [
    { system_id: 'AEX', system_name: 'AEX', status: 'healthy', incidents_week: 1, contract_violations: [], data_source: 'stub_fallback', authority_role: 'admits' },
    { system_id: 'PQX', system_name: 'PQX', status: 'warning', incidents_week: 0, contract_violations: [], data_source: 'artifact_store', authority_role: 'executes' },
    { system_id: 'EVL', system_name: 'EVL', status: 'unknown', incidents_week: 2, contract_violations: [], data_source: 'unknown', authority_role: 'evaluates' },
    { system_id: 'TPA', system_name: 'TPA', status: 'warning', incidents_week: 0, contract_violations: [], data_source: 'derived_estimate', authority_role: 'adjudicates trust/policy' },
    { system_id: 'CDE', system_name: 'CDE', status: 'warning', incidents_week: 0, contract_violations: [], data_source: 'artifact_store', authority_role: 'decides' },
    { system_id: 'SEL', system_name: 'SEL', status: 'warning', incidents_week: 0, contract_violations: [], data_source: 'artifact_store', authority_role: 'enforces' },
    { system_id: 'REP', system_name: 'REP', status: 'warning', incidents_week: 0, contract_violations: [], data_source: 'artifact_store', authority_role: 'replays' },
    { system_id: 'LIN', system_name: 'LIN', status: 'unknown', incidents_week: 0, contract_violations: [], data_source: 'unknown', authority_role: 'links lineage' },
    { system_id: 'OBS', system_name: 'OBS', status: 'warning', incidents_week: 0, contract_violations: [], data_source: 'artifact_store', authority_role: 'observes' },
    { system_id: 'SLO', system_name: 'SLO', status: 'warning', incidents_week: 0, contract_violations: [], data_source: 'artifact_store', authority_role: 'manages reliability budget' },
  ],
};

const mockIntelligence = {
  data_source: 'artifact_store',
  warnings: [],
  source_artifacts_used: ['artifacts/roadmap/latest/gap_analysis.json'],
  intelligence_summary: {
    roadmap: {
      dominant_bottleneck: 'EVL',
      bottleneck_statement: 'Missing evaluations are blocking promotion',
      top_risks: ['Missing eval artifacts', 'Trace lineage drift'],
    },
    mg_kernel: {
      status: 'fail',
      all_pass: false,
    },
    repo: {
      operational_signals: [{ title: 'eval_latency', status: 'warn', detail: 'Lagging checks' }],
    },
  },
};

const mockSystems = {
  data_source: 'derived_estimate',
  source_artifacts_used: [],
  warnings: ['system_state unavailable'],
};

const mockRGE = {
  data_source: 'derived_estimate',
  rge_can_operate: true,
  context_maturity_level: 7,
  mg_kernel_status: 'fail',
  active_drift_legs: ['EVL'],
  warnings: ['partial inputs'],
};

const mockPriorityMissing = {
  state: 'missing' as const,
  payload: null,
  reason: 'not_found:artifacts/system_dependency_priority_report.json',
};

function setupFetch(
  health = mockHealth,
  intelligence = mockIntelligence,
  systems = mockSystems,
  rge = mockRGE,
  priority: unknown = mockPriorityMissing,
) {
  (global.fetch as jest.Mock)
    .mockResolvedValueOnce({ ok: true, json: async () => health })
    .mockResolvedValueOnce({ ok: true, json: async () => intelligence })
    .mockResolvedValueOnce({ ok: true, json: async () => systems })
    .mockResolvedValueOnce({ ok: true, json: async () => rge })
    .mockResolvedValueOnce({ ok: true, json: async () => priority });
}

describe('DashboardPage panels', () => {
  beforeEach(() => {
    (global.fetch as jest.Mock).mockClear();
  });

  it('stub_fallback and unknown never render healthy', async () => {
    setupFetch();
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByTestId('loop-node-AEX')).toBeInTheDocument();
    });

    const aex = screen.getByTestId('loop-node-AEX');
    const evl = screen.getByTestId('loop-node-EVL');
    expect(within(aex).queryByText('healthy')).not.toBeInTheDocument();
    expect(within(evl).queryByText('healthy')).not.toBeInTheDocument();
  });

  it('shows provisional badge for derived_estimate sources', async () => {
    setupFetch();
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getAllByTestId('provisional-badge').length).toBeGreaterThan(0);
    });
  });

  it('renders all required loop systems and authority roles', async () => {
    setupFetch();
    render(<DashboardPage />);

    await waitFor(() => {
      ['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL', 'REP', 'LIN', 'OBS', 'SLO'].forEach((id) => {
        expect(screen.getByTestId(`loop-node-${id}`)).toBeInTheDocument();
        expect(screen.getByTestId(`authority-${id}`)).toBeInTheDocument();
      });
    });
  });

  it('proof chain shows missing stages', async () => {
    setupFetch();
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/^Eval$/)).toBeInTheDocument();
      expect(screen.getByText(/reason_codes: eval_missing/)).toBeInTheDocument();
    });
  });

  it('leverage queue items always include failure_prevented and signal_improved', async () => {
    setupFetch();
    render(<DashboardPage />);

    await waitFor(() => {
      const items = screen.getAllByTestId('leverage-item');
      expect(items.length).toBeGreaterThan(0);
      items.forEach((item) => {
        expect(within(item).getByText(/failure_prevented:/i)).toBeInTheDocument();
        expect(within(item).getByText(/signal_improved:/i)).toBeInTheDocument();
      });
    });
  });

  it('RGE panel never shows Execute and shows authority boundary statement', async () => {
    setupFetch();
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /^Execute$/i })).not.toBeInTheDocument();
      expect(screen.getByText(/RGE proposes only\. CDE decides\. SEL enforces\./i)).toBeInTheDocument();
    });
  });

  it('next-systems-to-finish panel shows missing-artifact state when artifact is absent', async () => {
    setupFetch();
    render(<DashboardPage />);
    await waitFor(() => {
      const panel = screen.getByTestId('next-systems-panel');
      expect(panel).toHaveAttribute('data-state', 'missing');
      expect(within(panel).getByTestId('next-systems-state-banner')).toHaveTextContent(/MISSING/i);
    });
  });

  it('next-systems-to-finish panel renders top-5 ranked systems verbatim from artifact', async () => {
    const priority = {
      state: 'ok',
      payload: {
        schema_version: 'tls-04.v1',
        phase: 'TLS-04',
        priority_order: ['a','b','c','d','e'],
        penalties: ['deprecated','unknown'],
        ranked_systems: [],
        global_ranked_systems: [],
        top_5: [
          {
            rank: 1,
            system_id: 'EVL',
            classification: 'active_system',
            score: 251,
            action: 'finish_hardening',
            why_now: 'on canonical loop; trust-boundary authority',
            trust_gap_signals: ['missing_eval', 'schema_weakness'],
            dependencies: { upstream: ['PQX'], downstream: ['TPA','CDE'] },
            unlocks: ['CDE','TPA'],
            finish_definition: 'all of: resolve signal(missing_eval), resolve signal(schema_weakness)',
            next_prompt: 'Run TLS-FIX-EVL',
            trust_state: 'blocked_signal',
          },
          {
            rank: 2,
            system_id: 'CDE',
            classification: 'active_system',
            score: 242,
            action: 'finish_hardening',
            why_now: 'on canonical loop',
            trust_gap_signals: ['missing_replay'],
            dependencies: { upstream: ['EVL'], downstream: ['SEL','GOV'] },
            unlocks: ['GOV','SEL'],
            finish_definition: 'resolve signal(missing_replay)',
            next_prompt: 'Run TLS-FIX-CDE',
            trust_state: 'freeze_signal',
          },
        ],
        requested_candidate_set: ['H01', 'RFX', 'HOP', 'MET', 'METS'],
        requested_candidate_ranking: [
          {
            requested_rank: 1,
            global_rank: 7,
            system_id: 'HOP',
            classification: 'active_system',
            score: 121,
            recommended_action: 'finish_hardening',
            why_now: 'unlocks downstream',
            prerequisite_systems: ['EVL'],
            trust_gap_signals: ['missing_observability'],
            finish_definition: 'resolve signal(missing_observability)',
            risk_if_built_before_prerequisites: 'higher risk',
          },
          {
            requested_rank: 2,
            global_rank: 10,
            system_id: 'H01',
            classification: 'h_slice',
            score: 88,
            recommended_action: 'investigate',
            why_now: 'slice candidate',
            prerequisite_systems: [],
            trust_gap_signals: [],
            finish_definition: 'retrieve evidence',
            risk_if_built_before_prerequisites: 'no higher-priority upstream trust prerequisite detected in TLS ranking',
          },
          {
            requested_rank: 3,
            global_rank: null,
            system_id: 'RFX',
            classification: 'unknown',
            score: null,
            recommended_action: 'investigate:classify_or_reject',
            why_now: 'unknown',
            prerequisite_systems: [],
            trust_gap_signals: [],
            finish_definition: 'retrieve registry and evidence before build prioritization',
            risk_if_built_before_prerequisites: 'unknown risk until candidate is classified',
            ambiguity_reason: 'repo_only_candidate_no_registry_record',
          },
        ],
        ambiguous_requested_candidates: [
          { system_id: 'RFX', ambiguity_reason: 'repo_only_candidate_no_registry_record' },
        ],
      },
      generated_at: new Date().toISOString(),
    };
    setupFetch(mockHealth, mockIntelligence, mockSystems, mockRGE, priority);
    render(<DashboardPage />);
    await waitFor(() => {
      const panel = screen.getByTestId('next-systems-panel');
      expect(panel).toHaveAttribute('data-state', 'ok');
      const rows = within(panel).getAllByTestId('next-system-row');
      expect(rows).toHaveLength(2);
      // Render order is the artifact's rank order — the dashboard MUST NOT
      // re-rank.
      expect(rows[0]).toHaveAttribute('data-system-id', 'EVL');
      expect(rows[1]).toHaveAttribute('data-system-id', 'CDE');
      expect(within(rows[0]).getAllByText(/missing_eval/).length).toBeGreaterThan(0);
      expect(rows[0].textContent).toContain('Run TLS-FIX-EVL');
      const requestedRows = within(panel).getAllByTestId('requested-candidate-row');
      expect(requestedRows.length).toBeGreaterThan(0);
      expect(within(panel).getByTestId('requested-candidate-ambiguity')).toHaveTextContent(/RFX/);
    });
  });

  it('next-systems-to-finish panel shows freeze_signal banner when control_signal asserts freeze_signal', async () => {
    const priority = {
      state: 'freeze_signal',
      payload: {
        schema_version: 'tls-04.v1',
        phase: 'TLS-04',
        priority_order: ['a','b','c','d','e'],
        penalties: [],
        ranked_systems: [],
        global_ranked_systems: [],
        top_5: [],
        requested_candidate_set: [],
        requested_candidate_ranking: [],
        ambiguous_requested_candidates: [],
      },
      reason: 'control_signal=freeze_signal',
    };
    setupFetch(mockHealth, mockIntelligence, mockSystems, mockRGE, priority);
    render(<DashboardPage />);
    await waitFor(() => {
      const panel = screen.getByTestId('next-systems-panel');
      expect(panel).toHaveAttribute('data-state', 'freeze_signal');
      expect(within(panel).getByTestId('next-systems-state-banner')).toHaveTextContent(/FREEZE_SIGNAL/i);
    });
  });

  it('requested candidate section shows empty-state guidance when no candidate set is provided', async () => {
    const priority = {
      state: 'ok',
      payload: {
        schema_version: 'tls-04.v1',
        phase: 'TLS-04',
        priority_order: ['a', 'b', 'c', 'd', 'e'],
        penalties: [],
        ranked_systems: [],
        global_ranked_systems: [],
        top_5: [],
        requested_candidate_set: [],
        requested_candidate_ranking: [],
        ambiguous_requested_candidates: [],
      },
      generated_at: new Date().toISOString(),
    };
    setupFetch(mockHealth, mockIntelligence, mockSystems, mockRGE, priority);
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByTestId('requested-candidate-empty')).toHaveTextContent(
        /No requested candidate set provided/i,
      );
    });
  });
});
