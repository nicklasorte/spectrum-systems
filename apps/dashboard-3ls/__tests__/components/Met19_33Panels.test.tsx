import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import DashboardPage from '@/app/page';

global.fetch = jest.fn();

function setupFetch(intelligencePayload: Record<string, unknown> = {}) {
  (global.fetch as jest.Mock).mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes('/api/health')) return Promise.resolve({ ok: true, json: async () => ({ warnings: [] }) });
    if (url.includes('/api/intelligence'))
      return Promise.resolve({ ok: true, json: async () => intelligencePayload });
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
          generated_at: '2026-04-27T00:00:00.000Z',
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
      return Promise.resolve({ ok: true, json: async () => ({ state: 'missing', payload: null, table_markdown: null }) });
    return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
  });
}

describe('MET-19-33 dashboard sections', () => {
  beforeEach(() => {
    (global.fetch as jest.Mock).mockClear();
  });

  it('does not render MET-19-33 panels in overview and keeps diagnostics intelligence surface', async () => {
    setupFetch({
      candidate_closure: {
        candidate_item_count: 6,
        stale_candidate_signal_count: 1,
        candidate_items: [
          {
            candidate_id: 'EVC-EVL-LONG-HORIZON-REPLAY',
            candidate_type: 'eval_candidate',
            current_state: 'proposed',
            age_days: 0,
            stale_after_days: 30,
            source_artifacts_used: ['x'],
          },
          {
            candidate_id: 'FB-LEGACY-UNDATED-EXAMPLE',
            candidate_type: 'failure_feedback_item',
            current_state: 'stale_candidate_signal',
            age_days: 'unknown',
            stale_after_days: 30,
            source_artifacts_used: ['y'],
          },
        ],
        warnings: [],
      },
      debug_explanation_index: {
        debug_target_minutes: 15,
        explanation_entry_count: 2,
        explanation_entries: [
          {
            explanation_id: 'DEI-EVL-COVERAGE-GAP',
            what_failed: 'EVL coverage_status partial',
            where_in_loop: 'EVL',
            next_recommended_input: 'Forward EVC-EVL-LONG-HORIZON-REPLAY',
            debug_readiness: 'sufficient',
            source_evidence: ['x'],
          },
        ],
        warnings: [],
      },
      trend_frequency_honesty_gate: {
        comparable_case_count: 3,
        required_case_count_for_trend: 3,
        trend_state: 'eligible_for_observation',
        frequency_state: 'eligible_for_observation',
        cases_needed: 0,
        blocked_trend_fields: [
          { field: 'failure_modes[].trend', reason: 'per-failure threshold not met', current_value: 'unknown' },
        ],
        warnings: [],
      },
      evl_handoff_observations: {
        handoff_item_count: 2,
        handoff_items: [
          {
            handoff_signal_id: 'HOH-EVC-EVL-LONG-HORIZON-REPLAY',
            target_owner_recommendation: 'EVL',
            materialization_observation: 'none_observed',
            source_artifacts_used: ['x'],
          },
        ],
        warnings: [],
      },
      override_evidence_intake: {
        override_evidence_count: 'unknown',
        evidence_status: 'absent',
        next_recommended_input: 'Forward POL-CDE-OVERRIDE-AUDIT.',
        reason_codes: ['override_evidence_missing'],
        warnings: [],
      },
      met_generated_artifact_classification: {
        classified_path_count: 2,
        classified_paths: [
          {
            path: 'artifacts/dashboard_metrics/candidate_closure_ledger_record.json',
            classification: 'dashboard_metric',
            merge_policy: 'regenerate_not_hand_merge',
          },
        ],
        warnings: [],
      },
    });

    render(<DashboardPage />);

    await waitFor(() => expect(screen.getByTestId('overview-tab')).toBeInTheDocument());
    expect(screen.queryByTestId('candidate-closure-section')).not.toBeInTheDocument();
    expect(screen.queryByTestId('debug-explanation-index-section')).not.toBeInTheDocument();
    expect(screen.queryByTestId('trend-frequency-honesty-section')).not.toBeInTheDocument();
    expect(screen.queryByTestId('evl-handoff-observations-section')).not.toBeInTheDocument();
    expect(screen.queryByTestId('artifact-integrity-section')).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('tab-diagnostics'));
    await waitFor(() => expect(screen.getByTestId('diagnostics-intelligence-panel')).toBeInTheDocument());
    expect(screen.getByTestId('diagnostics-intelligence-panel').textContent).toContain('MET intelligence');
    expect(screen.getByTestId('candidate-closure-section')).toBeInTheDocument();
    expect(screen.getByTestId('debug-explanation-index-section')).toBeInTheDocument();
    expect(screen.getByTestId('trend-frequency-honesty-section')).toBeInTheDocument();
    expect(screen.getByTestId('evl-handoff-observations-section')).toBeInTheDocument();
    expect(screen.getByTestId('artifact-integrity-section')).toBeInTheDocument();
  });

  it('keeps unknown visible when MET-19-33 blocks are missing', async () => {
    setupFetch({});
    render(<DashboardPage />);
    await waitFor(() => expect(screen.getByTestId('overview-tab')).toBeInTheDocument());
    expect(screen.queryByTestId('candidate-closure-section')).not.toBeInTheDocument();
  });

  it('diagnostics intelligence surface renders when MET blocks exist', async () => {
    setupFetch({
      candidate_closure: {
        candidate_item_count: 20,
        stale_candidate_signal_count: 0,
        candidate_items: Array.from({ length: 20 }, (_, i) => ({
          candidate_id: `C-${i}`,
          candidate_type: 'eval_candidate',
          current_state: 'proposed',
          age_days: i,
          stale_after_days: 30,
          source_artifacts_used: ['x'],
        })),
        warnings: [],
      },
      debug_explanation_index: {
        debug_target_minutes: 15,
        explanation_entry_count: 20,
        explanation_entries: Array.from({ length: 20 }, (_, i) => ({
          explanation_id: `E-${i}`,
          what_failed: 'x',
          where_in_loop: 'EVL',
          next_recommended_input: 'y',
          debug_readiness: 'sufficient',
          source_evidence: ['x'],
        })),
      },
      evl_handoff_observations: {
        handoff_item_count: 20,
        handoff_items: Array.from({ length: 20 }, (_, i) => ({
          handoff_signal_id: `H-${i}`,
          target_owner_recommendation: 'EVL',
          materialization_observation: 'none_observed',
          source_artifacts_used: ['x'],
        })),
      },
      met_generated_artifact_classification: {
        classified_path_count: 20,
        classified_paths: Array.from({ length: 20 }, (_, i) => ({
          path: `artifacts/dashboard_metrics/path_${i}.json`,
          classification: 'dashboard_metric',
          merge_policy: 'regenerate_not_hand_merge',
        })),
      },
    });

    render(<DashboardPage />);
    fireEvent.click(await screen.findByTestId('tab-diagnostics'));
    await waitFor(() => expect(screen.getByTestId('diagnostics-intelligence-panel')).toBeInTheDocument());
  });

  it('does not render an Execute button anywhere on the dashboard', async () => {
    setupFetch({});
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByTestId('overview-tab')).toBeInTheDocument();
    });
    const buttons = screen.queryAllByRole('button');
    buttons.forEach((b) => {
      expect((b.textContent ?? '').toLowerCase()).not.toContain('execute');
    });
  });
});

describe('MET-19-33 dashboard authority vocabulary discipline', () => {
  it('page source does not use authority verbs in MET-owned section titles', () => {
    const fs = require('fs');
    const path = require('path');
    const src = fs.readFileSync(path.resolve(__dirname, '../../app/page.tsx'), 'utf-8');
    const banned = [
      'Candidate Closure Decisions',
      'Approved Candidates',
      'Enforced Handoffs',
      'Certified Closures',
      'Promoted Cases',
      'Executed Recommendations',
    ];
    banned.forEach((h) => {
      expect(src).not.toContain(h);
    });
  });
});
