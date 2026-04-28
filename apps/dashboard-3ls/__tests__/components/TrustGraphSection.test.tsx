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

function mockGraphFetch(payload: SystemGraphPayload | { ok: boolean }) {
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


  it('default graph mode is clean structure and canvas defaults to scroll (mobile-safe)', async () => {
    mockGraphFetch(baseGraph);
    render(<TrustGraphSection />);
    await waitFor(() => expect(screen.getByTestId('debug-mode-selector-input')).toBeInTheDocument());
    expect(screen.getByTestId('debug-mode-selector-input')).toHaveValue('clean_structure');
    expect(screen.getByTestId('graph-canvas-wrapper')).toHaveClass('overflow-x-auto');
    expect(screen.queryByTestId('canvas-mode-toggle')).not.toBeInTheDocument();
  });


  it('graph panels include dark-mode readable classes', async () => {
    mockGraphFetch(baseGraph);
    render(<TrustGraphSection />);
    await waitFor(() => expect(screen.getByTestId('graph-legend')).toBeInTheDocument());
    expect(screen.getByTestId('trust-graph-section').className).toContain('dark:bg-slate-900');
    expect(screen.getByTestId('graph-legend').className).toContain('dark:bg-slate-900');
    expect(screen.getByTestId('activity-log').className).toContain('dark:bg-slate-900');
    expect(screen.getByTestId('system-inspector').className).toContain('dark:bg-slate-900');
    expect(screen.getByTestId('edge-inspector').className).toContain('dark:bg-slate-900');
    expect(screen.getByTestId('recommendation-debug-panel').className).toContain('dark:bg-slate-900');
  });

  it('shows last recompute timestamp from artifact when no recompute has been triggered yet', async () => {
    mockGraphFetch(baseGraph);
    render(<TrustGraphSection />);
    await waitFor(() => expect(screen.getByTestId('trust-status-last-recompute')).toBeInTheDocument());
    expect(screen.getByTestId('trust-status-last-recompute')).toHaveTextContent('2026-04-27T00:00:00Z');
  });
});
