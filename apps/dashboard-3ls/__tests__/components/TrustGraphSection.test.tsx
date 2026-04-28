import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { TrustGraphSection } from '@/components/TrustGraphSection';
import type { SystemGraphPayload } from '@/lib/systemGraph';

global.fetch = jest.fn();

const baseGraph: SystemGraphPayload = {
  graph_state: 'caution_signal',
  generated_at: '2026-04-27T00:00:00Z',
  source_mix: { artifact_store: 7, repo_registry: 1, derived: 0, stub_fallback: 1, missing: 0 },
  trust_posture: 'caution_signal',
  nodes: [
    { system_id: 'AEX', label: 'AEX', layer: 'core', role: 'admission', trust_state: 'trusted_signal', artifact_backed_percent: 100, source_type: 'artifact_store', trust_gap_signals: [], upstream: [], downstream: ['PQX'], source_artifact_refs: ['a'], warning_count: 0, is_focus: false, is_fallback_backed: false, is_disconnected: false },
    { system_id: 'PQX', label: 'PQX', layer: 'core', role: 'execution', trust_state: 'trusted_signal', artifact_backed_percent: 100, source_type: 'artifact_store', trust_gap_signals: [], upstream: ['AEX'], downstream: [], source_artifact_refs: ['a'], warning_count: 0, is_focus: false, is_fallback_backed: false, is_disconnected: false },
  ],
  edges: [
    { from: 'AEX', to: 'PQX', edge_type: 'dependency', source_type: 'artifact_store', source_artifact_ref: 'x', confidence: 1, is_failure_path: false, is_broken: false },
  ],
  focus_systems: ['PQX'],
  failure_path: [],
  missing_artifacts: [],
  warnings: [],
  replay_commands: ['python scripts/build_tls_dependency_priority.py'],
};

function mockGraphFetch(payload: SystemGraphPayload | { ok: boolean }, priorityOverride?: unknown) {
  (global.fetch as jest.Mock).mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes('/api/system-graph')) {
      if ('ok' in payload && payload.ok === false) {
        return Promise.reject(new Error('boom'));
      }
      return Promise.resolve({ ok: true, json: async () => payload });
    }
    if (url.includes('/api/recompute-graph')) {
      return Promise.resolve({ ok: true, json: async () => ({ status: 'recompute_success_signal' }) });
    }
    if (url.includes('/api/priority')) {
      return Promise.resolve({
        ok: true,
        json: async () => priorityOverride ?? {
          state: 'ok',
          payload: {
            requested_candidate_ranking: [{
              requested_rank: 1,
              system_id: 'AEX',
              classification: 'h_slice',
              recommended_action: 'harden',
              why_now: 'now',
              prerequisite_systems: [],
              trust_gap_signals: [],
              finish_definition: 'done',
              risk_if_built_before_prerequisites: 'none',
              rank_explanation: 'artifact',
              prerequisite_explanation: 'none',
              safe_next_action: 'run',
              build_now_assessment: 'ready_signal',
              why_not_higher: 'n/a',
              why_not_lower: 'n/a',
              minimum_safe_prompt_scope: 'narrow',
              dependency_warning_level: 'ready_signal',
              evidence_summary: 'artifact',
            }],
            global_ranked_systems: [],
            ranked_systems: [],
          },
        },
      });
    }
    return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
  });
}

describe('TrustGraphSection', () => {
  beforeEach(() => {
    (global.fetch as jest.Mock).mockReset();
  });

  it('renders the layered cockpit layout (left rail + main graph) when artifact loads', async () => {
    mockGraphFetch(baseGraph);
    render(<TrustGraphSection />);
    await waitFor(() => expect(screen.getByTestId('graph-tab-layout')).toBeInTheDocument());
    expect(screen.getByTestId('graph-left-rail')).toBeInTheDocument();
    expect(screen.getByTestId('graph-main-panel')).toBeInTheDocument();
    expect(screen.getByTestId('system-trust-status-card')).toBeInTheDocument();
    expect(screen.getByTestId('graph-legend')).toBeInTheDocument();
    expect(screen.getByTestId('activity-log')).toBeInTheDocument();
    expect(screen.getByTestId('layout-selector')).toBeInTheDocument();
    expect(screen.getByTestId('focus-toggle')).toBeInTheDocument();
    expect(screen.getByTestId('recompute-graph-button')).toBeInTheDocument();
  });

  it('shows a fail-closed warning when the graph artifact fetch fails', async () => {
    mockGraphFetch({ ok: false });
    render(<TrustGraphSection />);
    await waitFor(() => expect(screen.getByTestId('graph-fail-closed-warning')).toBeInTheDocument());
    expect(screen.queryByTestId('system-trust-graph')).not.toBeInTheDocument();
  });

  it('shows a fail-closed warning when the artifact has no nodes (no synthesized fallback)', async () => {
    mockGraphFetch({ ...baseGraph, nodes: [], edges: [] });
    render(<TrustGraphSection />);
    await waitFor(() => expect(screen.getByTestId('graph-fail-closed-warning')).toBeInTheDocument());
    expect(screen.queryByTestId('trust-node-AEX')).not.toBeInTheDocument();
  });

  it('clicking Recompute Graph triggers the refresh path and reloads the graph', async () => {
    mockGraphFetch(baseGraph);
    render(<TrustGraphSection />);
    await waitFor(() => expect(screen.getByTestId('recompute-graph-button')).toBeInTheDocument());

    await act(async () => {
      fireEvent.click(screen.getByTestId('recompute-graph-button'));
    });

    await waitFor(() => {
      const calls = (global.fetch as jest.Mock).mock.calls.map((c) => String(c[0]));
      expect(calls.some((url) => url.includes('/api/recompute-graph'))).toBe(true);
    });
    const calls = (global.fetch as jest.Mock).mock.calls.map((c) => String(c[0]));
    const graphFetches = calls.filter((url) => url.includes('/api/system-graph')).length;
    expect(graphFetches).toBeGreaterThanOrEqual(2);
  });

  it('toggling Show all changes the focus button label', async () => {
    mockGraphFetch(baseGraph);
    render(<TrustGraphSection />);
    await waitFor(() => expect(screen.getByTestId('focus-toggle')).toBeInTheDocument());
    expect(screen.getByTestId('focus-toggle')).toHaveTextContent('Show all');
    fireEvent.click(screen.getByTestId('focus-toggle'));
    expect(screen.getByTestId('focus-toggle')).toHaveTextContent('Focus mode');
  });

  it('shows last recompute timestamp from artifact when no recompute has been triggered yet', async () => {
    mockGraphFetch(baseGraph);
    render(<TrustGraphSection />);
    await waitFor(() => expect(screen.getByTestId('trust-status-last-recompute')).toBeInTheDocument());
    expect(screen.getByTestId('trust-status-last-recompute')).toHaveTextContent('2026-04-27T00:00:00Z');
  });

  it('hides graph recommendation overlay when priority freshness gate is stale', async () => {
    mockGraphFetch(baseGraph, { state: 'ok', payload: { requested_candidate_ranking: [] }, freshness_gate: { ok: false, recompute_command: 'python recompute.py' } });
    render(<TrustGraphSection />);
    await waitFor(() => expect(screen.getByTestId('recommendation-debug-panel')).toBeInTheDocument());
    expect(screen.getByText(/unavailable — ranking artifact stale\/invalid\/missing/i)).toBeInTheDocument();
    expect(screen.queryByTestId('rec-debug-card-AEX')).not.toBeInTheDocument();
  });
});
