import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import DashboardPage from '@/app/page';

global.fetch = jest.fn();

function setupFetch(intelligencePayload: Record<string, unknown> = {}) {
  (global.fetch as jest.Mock).mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes('/api/health')) return Promise.resolve({ ok: true, json: async () => ({ warnings: [] }) });
    if (url.includes('/api/intelligence')) return Promise.resolve({ ok: true, json: async () => intelligencePayload });
    if (url.includes('/api/priority')) return Promise.resolve({ ok: true, json: async () => ({ state: 'missing', payload: null }) });
    if (url.includes('/api/system-flow')) return Promise.resolve({ ok: true, json: async () => ({ state: 'ok', payload: { canonical_loop: ['AEX','PQX','EVL','TPA','CDE','SEL'], canonical_overlays: ['REP','LIN','OBS','SLO'], active_systems: [] } }) });
    if (url.includes('/api/system-graph')) return Promise.resolve({ ok: true, json: async () => ({ graph_state: 'caution_signal', generated_at: '2026-04-28T00:00:00.000Z', source_mix: { artifact_store: 1, repo_registry: 0, derived: 0, stub_fallback: 0, missing: 0 }, trust_posture: 'caution_signal', nodes: [], edges: [], focus_systems: [], failure_path: [], missing_artifacts: [], warnings: [], replay_commands: [] }) });
    if (url.includes('/api/tls-roadmap')) return Promise.resolve({ ok: true, json: async () => ({ state: 'missing', payload: null, table_markdown: null }) });
    return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
  });
}

describe('MET-34-47 dashboard panels', () => {
  beforeEach(() => {
    (global.fetch as jest.Mock).mockClear();
  });

  it('renders all new diagnostics sections', async () => {
    setupFetch({
      owner_read_observations: { owner_read_items: [{ owner_read_observation_id: 'OR-1', source_candidate_id: 'EVC-1', read_observation_state: 'none_observed', recommended_owner_system: 'EVL' }], source_artifacts_used: ['a'] },
      materialization_observation_mapper: { materialization_observations: [{ materialization_observation_id: 'MO-1', source_candidate_id: 'EVC-1', materialization_observation: 'none_observed' }], source_artifacts_used: ['b'] },
      comparable_case_qualification_gate: { qualified_case_groups: [{ group_id: 'G1' }] },
      trend_ready_case_pack: { case_packs: [{ case_pack_id: 'P1' }], source_artifacts_used: ['c'] },
      fold_candidate_proof_check: { fold_candidates: [{ fold_candidate_id: 'F1', fold_safety_observation: 'not_ready_observation' }] },
      operator_debuggability_drill: { target_minutes: 15, drill_items: [{ drill_id: 'D1', debug_readiness: 'partial' }] },
    });

    render(<DashboardPage />);
    fireEvent.click(await screen.findByTestId('tab-diagnostics'));

    await waitFor(() => {
      expect(screen.getByTestId('owner-read-observations-section')).toBeInTheDocument();
      expect(screen.getByTestId('materialization-observations-section')).toBeInTheDocument();
      expect(screen.getByTestId('comparable-trend-readiness-section')).toBeInTheDocument();
      expect(screen.getByTestId('fold-safety-section')).toBeInTheDocument();
      expect(screen.getByTestId('operator-debuggability-drill-section')).toBeInTheDocument();
    });
  });

  it('keeps sections compact at no more than 5 visible items', async () => {
    setupFetch({
      owner_read_observations: {
        owner_read_items: Array.from({ length: 9 }, (_, i) => ({ owner_read_observation_id: `OR-${i}`, source_candidate_id: `C-${i}`, read_observation_state: 'unknown', recommended_owner_system: 'EVL' })),
      },
    });
    render(<DashboardPage />);
    fireEvent.click(await screen.findByTestId('tab-diagnostics'));
    await waitFor(() => expect(screen.getByTestId('owner-read-observations-section')).toBeInTheDocument());
    const items = screen.getByTestId('owner-read-observations-section').querySelectorAll('li');
    expect(items.length).toBeLessThanOrEqual(5);
  });

  it('does not render an action button with blocked label', async () => {
    setupFetch({});
    render(<DashboardPage />);
    await waitFor(() => expect(screen.getByTestId('overview-tab')).toBeInTheDocument());
    screen.queryAllByRole('button').forEach((btn) => {
      expect((btn.textContent ?? '').toLowerCase()).not.toContain('run-now');
    });
  });
});
