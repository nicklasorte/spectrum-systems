import React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import DashboardPage from '@/app/page';

global.fetch = jest.fn();

const baseHealth = {
  data_source: 'artifact_store',
  generated_at: '2026-04-25T00:00:00.000Z',
  source_artifacts_used: ['artifacts/dashboard/repo_snapshot.json'],
  warnings: [],
  systems: [
    { system_id: 'AEX', system_name: 'AEX', status: 'warning', incidents_week: 1, contract_violations: [], data_source: 'artifact_store', authority_role: 'admits' },
    { system_id: 'PQX', system_name: 'PQX', status: 'warning', incidents_week: 0, contract_violations: [], data_source: 'artifact_store', authority_role: 'executes' },
    { system_id: 'EVL', system_name: 'EVL', status: 'warning', incidents_week: 2, contract_violations: [], data_source: 'artifact_store', authority_role: 'evaluates' },
    { system_id: 'TPA', system_name: 'TPA', status: 'warning', incidents_week: 0, contract_violations: [], data_source: 'artifact_store', authority_role: 'adjudicates trust/policy' },
    { system_id: 'CDE', system_name: 'CDE', status: 'warning', incidents_week: 0, contract_violations: [], data_source: 'artifact_store', authority_role: 'decides' },
    { system_id: 'SEL', system_name: 'SEL', status: 'warning', incidents_week: 0, contract_violations: [], data_source: 'artifact_store', authority_role: 'enforces' },
    { system_id: 'REP', system_name: 'REP', status: 'warning', incidents_week: 0, contract_violations: [], data_source: 'artifact_store', authority_role: 'replays' },
    { system_id: 'LIN', system_name: 'LIN', status: 'warning', incidents_week: 0, contract_violations: [], data_source: 'artifact_store', authority_role: 'links lineage' },
    { system_id: 'OBS', system_name: 'OBS', status: 'warning', incidents_week: 0, contract_violations: [], data_source: 'artifact_store', authority_role: 'observes' },
    { system_id: 'SLO', system_name: 'SLO', status: 'warning', incidents_week: 0, contract_violations: [], data_source: 'artifact_store', authority_role: 'manages reliability budget' },
  ],
};

const baseIntelligence = {
  data_source: 'artifact_store',
  warnings: [],
  source_artifacts_used: ['artifacts/dashboard_metrics/bottleneck_record.json'],
  bottleneck: {
    dominant_bottleneck_system: 'EVL',
    constrained_loop_leg: 'EVL',
    supporting_evidence: [
      {
        kind: 'eval_partial_coverage',
        source: 'artifacts/dashboard_seed/eval_summary_record.json',
        detail: 'EVL coverage_status=partial with score=0.72.',
      },
    ],
    warning_counts_by_system: { EVL: 2, TPA: 1, CDE: 1 },
    block_counts_by_system: { CDE: 1 },
    priority_rule: 'EVL/CDE/TPA gate promotion',
    confidence_rationale: 'EVL is partial; downstream warns inherit.',
    data_source: 'artifact_store',
    source_artifacts_used: ['artifacts/dashboard_seed/eval_summary_record.json'],
    warnings: [],
  },
  bottleneck_confidence: 'artifact_backed',
  leverage_queue: {
    formula: 'severity*systems / effort',
    data_source: 'artifact_store',
    source_artifacts_used: ['artifacts/dashboard_metrics/leverage_queue_record.json'],
    warnings: [],
    items: [
      {
        id: 'LV-EVL-001',
        title: 'Close EVL coverage gap',
        failure_prevented: 'Promotion on partial eval evidence',
        signal_improved: 'Eval coverage and TPA confidence',
        systems_affected: ['EVL', 'TPA', 'CDE'],
        severity: 'high',
        frequency: 'unknown',
        estimated_effort: 'medium',
        leverage_score: 7.25,
        data_source: 'artifact_store',
        source_artifacts_used: ['artifacts/dashboard_seed/eval_summary_record.json'],
        confidence: 'artifact_backed',
      },
      {
        id: 'LV-NO-SOURCE',
        title: 'Missing source — should be filtered',
        failure_prevented: 'Anything',
        signal_improved: 'Anything',
        systems_affected: ['REP'],
        severity: 'medium',
        frequency: 'unknown',
        estimated_effort: 'low',
        leverage_score: 9.99,
        data_source: 'artifact_store',
        source_artifacts_used: [],
        confidence: 'artifact_backed',
      },
    ],
  },
  risk_summary: {
    fallback_signal_count: 6,
    unknown_signal_count: 0,
    missing_eval_count: 2,
    missing_trace_count: 0,
    override_count: 'unknown',
    proof_chain_coverage: { total: 10, present: 4, partial: 6, missing_or_unknown: 0, percent_present_or_partial: 100 },
    top_risks: [
      {
        id: 'FM-SEED-EVAL-GAP',
        title: 'Eval coverage gap',
        severity: 'high',
        systems_affected: ['EVL', 'TPA', 'CDE'],
        evidence_artifact: 'artifacts/dashboard_seed/eval_summary_record.json',
      },
    ],
    data_source: 'artifact_store',
    source_artifacts_used: ['artifacts/dashboard_metrics/risk_summary_record.json'],
    warnings: [],
  },
  failure_modes: [
    {
      id: 'FM-SEED-EVAL-GAP',
      title: 'Eval coverage gap can mask regressions',
      severity: 'high',
      frequency: 'unknown',
      systems_affected: ['EVL', 'TPA', 'CDE'],
      trend: 'unknown',
    },
    {
      id: 'FM-SEED-CERT-INCOMPLETE',
      title: 'Certification incomplete forces SEL observe_only',
      severity: 'high',
      frequency: 'unknown',
      systems_affected: ['SEL', 'CDE'],
      trend: 'unknown',
    },
  ],
  intelligence_summary: {
    roadmap: { dominant_bottleneck: 'EVL', bottleneck_statement: 'Eval is the constraint', top_risks: [] },
    mg_kernel: { status: 'fail', all_pass: false },
    repo: { operational_signals: [] },
  },
};

const baseSystems = { data_source: 'artifact_store', source_artifacts_used: [], warnings: [] };
const baseRGE = {
  data_source: 'artifact_store',
  rge_can_operate: true,
  context_maturity_level: 7,
  mg_kernel_status: 'fail',
  active_drift_legs: [],
  warnings: [],
};

function setupFetch(
  health = baseHealth,
  intelligence = baseIntelligence,
  systems = baseSystems,
  rge = baseRGE
) {
  (global.fetch as jest.Mock)
    .mockResolvedValueOnce({ ok: true, json: async () => health })
    .mockResolvedValueOnce({ ok: true, json: async () => intelligence })
    .mockResolvedValueOnce({ ok: true, json: async () => systems })
    .mockResolvedValueOnce({ ok: true, json: async () => rge });
}

describe('MET-03 dashboard panels', () => {
  beforeEach(() => {
    (global.fetch as jest.Mock).mockClear();
  });

  it('highlights the bottleneck node in the loop panel', async () => {
    setupFetch();
    render(<DashboardPage />);

    await waitFor(() => {
      const node = screen.getByTestId('loop-node-EVL');
      expect(node.getAttribute('data-bottleneck')).toBe('true');
      expect(within(node).getByText(/^bottleneck$/i)).toBeInTheDocument();
    });
  });

  it('shows bottleneck reason and supporting evidence', async () => {
    setupFetch();
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByTestId('bottleneck-reason')).toHaveTextContent(/EVL is partial/);
      expect(screen.getByTestId('bottleneck-evidence')).toHaveTextContent(/eval_partial_coverage/);
    });
  });

  it('renders top leverage items from artifact-backed queue and filters unsourced items', async () => {
    setupFetch();
    render(<DashboardPage />);

    await waitFor(() => {
      const items = screen.getAllByTestId('leverage-item');
      expect(items.length).toBeGreaterThan(0);
      const titles = items.map((item) => item.textContent ?? '');
      expect(titles.some((t) => t.includes('Close EVL coverage gap'))).toBe(true);
      expect(titles.some((t) => t.includes('Missing source'))).toBe(false);
    });
  });

  it('every rendered leverage item shows source_artifacts_used', async () => {
    setupFetch();
    render(<DashboardPage />);

    await waitFor(() => {
      const items = screen.getAllByTestId('leverage-item');
      items.forEach((item) => {
        expect(within(item).getByText(/source_artifacts_used:/)).toBeInTheDocument();
      });
    });
  });

  it('risk panel shows artifact-backed counts and failure modes with severity', async () => {
    setupFetch();
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/fallback count: 6/)).toBeInTheDocument();
      expect(screen.getByText(/missing eval count: 2/)).toBeInTheDocument();
      expect(screen.getByText(/override count: unknown/)).toBeInTheDocument();
      const list = screen.getByTestId('risk-failure-modes');
      expect(within(list).getByText(/Eval coverage gap can mask regressions/)).toBeInTheDocument();
      expect(within(list).getAllByText(/severity:\s*high/).length).toBeGreaterThan(0);
    });
  });

  it('fallback signals still degrade trust posture (not green)', async () => {
    setupFetch(
      {
        ...baseHealth,
        systems: baseHealth.systems.map((s) =>
          s.system_id === 'OBS' ? { ...s, data_source: 'stub_fallback' as const, status: 'healthy' as const } : s
        ),
      },
      baseIntelligence
    );
    render(<DashboardPage />);

    await waitFor(() => {
      const panel = screen.getByTestId('trust-posture-panel');
      expect(within(panel).queryByText(/^PASS$/)).not.toBeInTheDocument();
      expect(panel.textContent).toMatch(/FREEZE|WARN|BLOCK/);
    });
  });

  it('unknown stages keep proof chain from rendering green', async () => {
    setupFetch(
      {
        ...baseHealth,
        systems: baseHealth.systems.map((s) =>
          s.system_id === 'EVL' ? { ...s, data_source: 'unknown' as const, status: 'unknown' as const } : s
        ),
      },
      baseIntelligence
    );
    render(<DashboardPage />);

    await waitFor(() => {
      const proof = screen.getByTestId('proof-chain-panel');
      expect(within(proof).queryByText(/^healthy$/)).not.toBeInTheDocument();
    });
  });
});
