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
    if (url.includes('/api/system-flow')) {
      return Promise.resolve({ ok: true, json: async () => ({ state: 'ok', payload: { canonical_loop: ['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL'], canonical_overlays: ['REP', 'LIN', 'OBS', 'SLO'], active_systems: [] } }) });
    }
    if (url.includes('/api/system-graph')) {
      return Promise.resolve({ ok: true, json: async () => ({ graph_state: 'caution_signal', generated_at: '2026-04-27T00:00:00.000Z', source_mix: { artifact_store: 1, repo_registry: 0, derived: 0, stub_fallback: 0, missing: 0 }, trust_posture: 'caution_signal', nodes: [], edges: [], focus_systems: [], failure_path: [], missing_artifacts: [], warnings: [], replay_commands: [] }) });
    }
    if (url.includes('/api/tls-roadmap')) return Promise.resolve({ ok: true, json: async () => ({ state: 'missing', payload: null, table_markdown: null }) });
    return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
  });
}

describe('MET-04-18 dashboard sections', () => {
  beforeEach(() => {
    (global.fetch as jest.Mock).mockClear();
  });

  it('keeps MET-04-18 heavy sections off Overview and accessible via non-overview tabs', async () => {
    setupFetch({
      feedback_loop: {
        feedback_items_count: 7,
        eval_candidates_count: 6,
        policy_candidate_signals_count: 4,
        unresolved_feedback_count: 7,
        expired_feedback_count: 0,
        top_feedback_themes: [
          { theme: 'EVL coverage gap' },
          { theme: 'Replay/lineage hardening' },
        ],
        next_recommended_improvement_inputs: ['forward EVC-EVL-* to EVL'],
        loop_status: 'partial',
        warnings: ['Loop is partial.'],
      },
      failure_explanation_packets: {
        packets: [
          {
            packet_id: 'FXP-EVL-COVERAGE-GAP',
            title: 'Eval coverage gap',
            current_status: 'warn',
            constrained_loop_leg: 'EVL',
            what_failed: 'EVL coverage_status=partial',
            why_it_matters: 'EVL gates downstream',
            next_recommended_input: 'Forward EVC-EVL-LONG-HORIZON-REPLAY',
            evidence_artifacts: ['artifacts/dashboard_seed/eval_summary_record.json'],
          },
        ],
        warnings: [],
      },
      override_audit: {
        override_count: 'unknown',
        reason_codes: ['override_history_missing'],
        next_recommended_input: 'Forward POL-CDE-OVERRIDE-AUDIT.',
        warnings: ['No canonical override log.'],
      },
      fallback_reduction_plan: {
        total_fallback_count: 6,
        high_leverage_fallback_count: 4,
        fallback_items: [
          {
            system_id: 'REP',
            replacement_signal_needed: 'per-dimension status',
            priority: 'high',
          },
        ],
        warnings: [],
      },
      replay_lineage_hardening: {
        affected_systems: ['REP', 'LIN'],
        replay_dimensions_checked: [
          { dimension: 'short_horizon', status: 'present' },
          { dimension: 'long_horizon', status: 'missing' },
        ],
        lineage_links_checked: [
          { edge: 'eval -> certification', status: 'missing' },
        ],
        gaps_observed: ['REP missing long_horizon'],
        warnings: [],
      },
    });

    render(<DashboardPage />);

    await waitFor(() => expect(screen.getByTestId('tab-diagnostics')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('tab-diagnostics'));
    await waitFor(() => {
      expect(screen.getByTestId('diagnostics-tab')).toBeInTheDocument();
    });

    expect(screen.getByTestId('diagnostics-tab')).toBeInTheDocument();
  });

  it('keeps unknown/fallback/proposed states visible when feedback loop is missing', async () => {
    setupFetch({});
    render(<DashboardPage />);
    await waitFor(() => expect(screen.getByTestId('overview-tab')).toBeInTheDocument());
    expect(screen.queryByTestId('learning-loop-section')).not.toBeInTheDocument();
    expect(screen.queryByTestId('override-unknowns-section')).not.toBeInTheDocument();
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

describe('MET-04-18 dashboard authority vocabulary discipline', () => {
  it('page source does not use authority verbs in MET-owned headings', () => {
    const fs = require('fs');
    const path = require('path');
    const src = fs.readFileSync(
      path.resolve(__dirname, '../../app/page.tsx'),
      'utf-8',
    );
    // Section titles must not assert MET authority.
    const bannedHeadings = [
      'Override Decisions',
      'Approved Candidates',
      'Enforced Signals',
      'Certified Cases',
      'Promoted Cases',
      'Executed Recommendations',
    ];
    bannedHeadings.forEach((h) => {
      expect(src).not.toContain(h);
    });
  });
});
