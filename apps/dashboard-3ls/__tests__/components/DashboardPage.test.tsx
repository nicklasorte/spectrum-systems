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

function setupFetch(health = mockHealth, intelligence = mockIntelligence, systems = mockSystems, rge = mockRGE) {
  (global.fetch as jest.Mock)
    .mockResolvedValueOnce({ ok: true, json: async () => health })
    .mockResolvedValueOnce({ ok: true, json: async () => intelligence })
    .mockResolvedValueOnce({ ok: true, json: async () => systems })
    .mockResolvedValueOnce({ ok: true, json: async () => rge });
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
});
