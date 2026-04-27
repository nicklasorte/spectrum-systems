import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import DashboardPage from '@/app/page';

global.fetch = jest.fn();

function setupFetch() {
  (global.fetch as jest.Mock).mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes('/api/health')) return Promise.resolve({ ok: true, json: async () => ({ warnings: [] }) });
    if (url.includes('/api/intelligence')) return Promise.resolve({ ok: true, json: async () => ({ warnings: [] }) });
    if (url.includes('/api/priority')) return Promise.resolve({ ok: true, json: async () => ({ state: 'missing', payload: null }) });
    if (url.includes('/api/system-flow')) {
      return Promise.resolve({ ok: true, json: async () => ({ state: 'ok', payload: { canonical_loop: ['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL'], canonical_overlays: ['REP', 'LIN', 'OBS', 'SLO'], active_systems: [{ system_id: 'AEX', upstream: [], downstream: ['PQX'] }, { system_id: 'PQX', upstream: ['AEX'], downstream: ['EVL'] }] } }) });
    }
    if (url.includes('/api/system-graph')) {
      return Promise.resolve({ ok: true, json: async () => ({ graph_state: 'caution_signal', generated_at: '2026-04-27T00:00:00.000Z', source_mix: { artifact_store: 1, repo_registry: 0, derived: 0, stub_fallback: 0, missing: 0 }, trust_posture: 'caution_signal', nodes: [], edges: [], focus_systems: [], failure_path: [], missing_artifacts: [], warnings: [], replay_commands: [] }) });
    }
    if (url.includes('/api/tls-roadmap')) {
      return Promise.resolve({ ok: true, json: async () => ({ state: 'missing', payload: null, table_markdown: null }) });
    }
    return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
  });
}

describe('MET-03 dashboard simplification', () => {
  beforeEach(() => {
    (global.fetch as jest.Mock).mockClear();
  });

  it('renders flow and queue/top3 warnings in overview fail-closed state', async () => {
    setupFetch();
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByTestId('overview-tab')).toBeInTheDocument();
      expect(screen.getByTestId('top3-warning')).toBeInTheDocument();
      expect(screen.getByTestId('queue-warning')).toBeInTheDocument();
    });
  });

  it('keeps overview concise with only four operator panels', async () => {
    setupFetch();
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getAllByTestId('overview-section')).toHaveLength(4);
    });
  });
});
