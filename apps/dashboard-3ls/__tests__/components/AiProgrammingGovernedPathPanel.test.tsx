// AEX-PQX-DASH-01 — AI Programming Governed Path panel rendering tests.
//
// Verify the dashboard surfaces Codex/Claude counts, AEX/PQX evidence per
// item, and that missing AEX/PQX evidence on Codex or Claude work cannot
// render green. Also assert no Execute button and no authority vocabulary
// violations creep into the new MET-owned section.

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import DashboardPage from '@/app/page';

global.fetch = jest.fn();

function setupFetch(governedPathBlock: Record<string, unknown> | undefined) {
  (global.fetch as jest.Mock).mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes('/api/health'))
      return Promise.resolve({ ok: true, json: async () => ({ warnings: [] }) });
    if (url.includes('/api/intelligence'))
      return Promise.resolve({
        ok: true,
        json: async () =>
          governedPathBlock === undefined
            ? {}
            : { ai_programming_governed_path: governedPathBlock },
      });
    if (url.includes('/api/priority'))
      return Promise.resolve({ ok: true, json: async () => ({ state: 'missing', payload: null }) });
    if (url.includes('/api/system-flow')) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          state: 'ok',
          payload: {
            canonical_loop: ['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL'],
            canonical_overlays: ['REP', 'LIN', 'OBS', 'SLO'],
            active_systems: [],
          },
        }),
      });
    }
    if (url.includes('/api/system-graph')) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          graph_state: 'caution_signal',
          generated_at: '2026-04-29T00:00:00.000Z',
          source_mix: { artifact_store: 1, repo_registry: 0, derived: 0, stub_fallback: 0, missing: 0 },
          trust_posture: 'caution_signal',
          nodes: [],
          edges: [],
          focus_systems: [],
          failure_path: [],
          missing_artifacts: [],
          warnings: [],
          replay_commands: [],
        }),
      });
    }
    if (url.includes('/api/tls-roadmap'))
      return Promise.resolve({
        ok: true,
        json: async () => ({ state: 'missing', payload: null, table_markdown: null }),
      });
    return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
  });
}

describe('AEX-PQX-DASH-01 — AI Programming Governed Path panel', () => {
  beforeEach(() => {
    (global.fetch as jest.Mock).mockClear();
  });

  it('renders the panel near the top of overview with Codex and Claude counts', async () => {
    setupFetch({
      status: 'warn',
      data_source: 'artifact_store',
      source_artifacts_used: ['artifacts/pqx_runs/preflight.pqx_slice_execution_record.json'],
      warnings: [],
      reason_codes: ['ai_programming_governed_path_observation_only'],
      total_ai_programming_work_items: 3,
      codex_work_count: 1,
      claude_work_count: 1,
      governed_work_count: 0,
      bypass_risk_count: 2,
      unknown_path_count: 1,
      aex_present_count: 0,
      pqx_present_count: 1,
      ai_programming_work_items: [],
      top_attention_items: [],
    });

    render(<DashboardPage />);
    await waitFor(() =>
      expect(screen.getByTestId('ai-programming-governed-path-panel')).toBeInTheDocument(),
    );
    expect(screen.getByTestId('ai-codex-count').textContent).toBe('1');
    expect(screen.getByTestId('ai-claude-count').textContent).toBe('1');
    expect(screen.getByTestId('ai-bypass-risk-count').textContent).toBe('2');
    expect(screen.getByTestId('ai-aex-present-count').textContent).toBe('0');
    expect(screen.getByTestId('ai-pqx-present-count').textContent).toBe('1');
    expect(screen.getByTestId('ai-programming-governed-path-status').textContent).toContain('WARN');
  });

  it('shows BLOCK when status=block (e.g. Codex missing AEX)', async () => {
    setupFetch({
      status: 'block',
      data_source: 'artifact_store',
      source_artifacts_used: [],
      warnings: [],
      reason_codes: [],
      total_ai_programming_work_items: 1,
      codex_work_count: 1,
      claude_work_count: 0,
      governed_work_count: 0,
      bypass_risk_count: 1,
      unknown_path_count: 0,
      aex_present_count: 0,
      pqx_present_count: 1,
      ai_programming_work_items: [],
      top_attention_items: [
        {
          work_item_id: 'AIPG-CODEX-X',
          agent_type: 'codex',
          repo_mutating: true,
          aex_admission_observation: 'missing',
          pqx_execution_observation: 'present',
          eval_observation: 'partial',
          control_signal_observation: 'partial',
          enforcement_or_readiness_signal_observation: 'partial',
          lineage_observation: 'partial',
          bypass_risk: 'aex_missing',
          next_recommended_input: 'Add AEX admission evidence for Codex work item AIPG-CODEX-X',
          source_artifacts_used: ['x'],
        },
      ],
    });

    render(<DashboardPage />);
    await waitFor(() =>
      expect(screen.getByTestId('ai-programming-governed-path-panel')).toBeInTheDocument(),
    );
    expect(screen.getByTestId('ai-programming-governed-path-status').textContent).toContain(
      'BLOCK',
    );
    expect(screen.getByTestId('ai-programming-top-attention-item')).toBeInTheDocument();
    expect(screen.getByTestId('ai-programming-item-aex').textContent).toContain('missing');
    expect(screen.getByTestId('ai-programming-item-pqx').textContent).toContain('present');
  });

  it('renders UNKNOWN with unknown counts when the artifact is missing', async () => {
    setupFetch(undefined);
    render(<DashboardPage />);
    await waitFor(() =>
      expect(screen.getByTestId('ai-programming-governed-path-panel')).toBeInTheDocument(),
    );
    expect(screen.getByTestId('ai-programming-governed-path-status').textContent).toContain(
      'UNKNOWN',
    );
    expect(screen.getByTestId('ai-codex-count').textContent).toBe('unknown');
    expect(screen.getByTestId('ai-claude-count').textContent).toBe('unknown');
    expect(screen.getByTestId('ai-bypass-risk-count').textContent).toBe('unknown');
  });

  it('does not render an Execute button on the AI programming panel', async () => {
    setupFetch({
      status: 'warn',
      total_ai_programming_work_items: 0,
      codex_work_count: 0,
      claude_work_count: 0,
      ai_programming_work_items: [],
      top_attention_items: [],
    });
    render(<DashboardPage />);
    await waitFor(() => expect(screen.getByTestId('overview-tab')).toBeInTheDocument());
    const buttons = screen.queryAllByRole('button');
    buttons.forEach((b) => {
      expect((b.textContent ?? '').toLowerCase()).not.toContain('execute');
    });
  });
});

describe('AEX-PQX-DASH-01 — page source authority discipline', () => {
  it('does not assert MET decides/enforces/certifies the AI programming path', () => {
    const fs = require('fs');
    const path = require('path');
    const src = fs.readFileSync(path.resolve(__dirname, '../../app/page.tsx'), 'utf-8');
    const banned = [
      'AI Programming Decision',
      'AI Programming Enforced',
      'AI Programming Certified',
      'AI Programming Promoted',
      'AI Programming Approved',
      'MET decides',
      'MET enforces',
      'MET certifies',
      'MET promotes',
      'MET adopts',
      'MET approves',
    ];
    banned.forEach((b) => {
      expect(src).not.toContain(b);
    });
  });
});
