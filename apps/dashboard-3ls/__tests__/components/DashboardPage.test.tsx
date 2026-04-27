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


const mockNextStep = {
  state: 'ok' as const,
  payload: {
    artifact_type: 'next_step_decision_report',
    schema_version: '1.0.0',
    generated_at: '2026-04-27T00:00:00.000Z',
    status: 'pass' as const,
    readiness_state: 'ready' as const,
    source_refs: [],
    completed_work: ['BLF-01', 'RFX-04', 'RMP-SUPER-01', 'H01'],
    partial_work: [],
    remaining_work_table: [],
    ranked_priorities: [{ id: 'RFX-PROOF-01', work_item: 'RFX LOOP-09/10' }],
    selected_next_step: { id: 'RFX-PROOF-01', work_item: 'RFX LOOP-09/10', why: 'proof first', depends_on: ['H01'], unlocks: ['EVL'] },
    rejected_next_steps: [{ work_item: 'MET', reason: 'wait for proof' }],
    dependency_reasoning: [],
    red_team_findings: [{ id: 'RT-1', finding: 'example finding' }],
    warnings: [],
    reason_codes: [],
  },
};


const mockTrustGraph = {
  graph_state: 'freeze_signal',
  generated_at: '2026-04-27T00:00:00.000Z',
  source_mix: { artifact_store: 10, repo_registry: 0, derived: 2, stub_fallback: 1, missing: 0 },
  trust_posture: 'freeze_signal',
  nodes: [
    { system_id: 'AEX', label: 'AEX', layer: 'core', role: 'admission', trust_state: 'trusted_signal', artifact_backed_percent: 100, source_type: 'artifact_store', trust_gap_signals: [], upstream: [], downstream: ['PQX'], source_artifact_refs: [], warning_count: 0, is_focus: false, is_fallback_backed: false, is_disconnected: false },
    { system_id: 'EVL', label: 'EVL', layer: 'core', role: 'evaluation', trust_state: 'freeze_signal', artifact_backed_percent: 100, source_type: 'artifact_store', trust_gap_signals: ['missing_replay'], upstream: ['PQX'], downstream: ['TPA'], source_artifact_refs: [], warning_count: 1, is_focus: true, is_fallback_backed: false, is_disconnected: false },
  ],
  edges: [{ from: 'AEX', to: 'PQX', edge_type: 'dependency', source_type: 'artifact_store', source_artifact_ref: 'artifact', confidence: 1, is_failure_path: false, is_broken: false }],
  focus_systems: ['EVL'],
  failure_path: ['EVL', 'TPA'],
  missing_artifacts: [],
  warnings: [],
  replay_commands: ['python scripts/build_tls_dependency_priority.py --candidates H01,RFX,HOP,MET,METS --fail-if-missing'],
};

const mockSystemFlow = {
  state: 'ok' as const,
  source_artifact: 'artifacts/tls/system_registry_dependency_graph.json',
  payload: {
    schema_version: 'tls-00.v1',
    phase: 'TLS-00',
    canonical_loop: ['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL'],
    canonical_overlays: ['REP', 'LIN', 'OBS', 'SLO'],
    active_systems: [
      {
        system_id: 'AEX',
        upstream: [],
        downstream: ['PQX'],
        artifacts_owned: ['build_admission_record'],
        primary_code_paths: ['spectrum_systems/modules/runtime/agent_golden_path.py'],
      },
      {
        system_id: 'PQX',
        upstream: ['AEX'],
        downstream: ['EVL'],
        artifacts_owned: ['execution_result'],
        primary_code_paths: ['spectrum_systems/modules/runtime/pqx_sequence_runner.py'],
      },
      {
        system_id: 'EVL',
        upstream: ['PQX', 'MISSING_UPSTREAM'],
        downstream: ['TPA'],
        artifacts_owned: ['eval_summary'],
        primary_code_paths: ['spectrum_systems/modules/runtime/eval_pipeline.py'],
      },
    ],
  },
};

function setupFetch(
  health = mockHealth,
  intelligence = mockIntelligence,
  systems = mockSystems,
  rge = mockRGE,
  priority: unknown = mockPriorityMissing,
  systemFlow: unknown = mockSystemFlow,
  trustGraph: unknown = mockTrustGraph,
  nextStep: unknown = mockNextStep,
) {
  (global.fetch as jest.Mock).mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes('/api/health')) return Promise.resolve({ ok: true, json: async () => health });
    if (url.includes('/api/intelligence')) return Promise.resolve({ ok: true, json: async () => intelligence });
    if (url.includes('/api/systems')) return Promise.resolve({ ok: true, json: async () => systems });
    if (url.includes('/api/rge/analysis')) return Promise.resolve({ ok: true, json: async () => rge });
    if (url.includes('/api/priority')) return Promise.resolve({ ok: true, json: async () => priority });
    if (url.includes('/api/system-flow')) return Promise.resolve({ ok: true, json: async () => systemFlow });
    if (url.includes('/api/system-graph')) return Promise.resolve({ ok: true, json: async () => trustGraph });
    if (url.includes('/api/next-step')) return Promise.resolve({ ok: true, json: async () => nextStep });
    return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
  });
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

  it('system flow graph renders from artifact, highlights trust colors, fallback nodes, and broken edges', async () => {
    setupFetch();
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByTestId('system-flow-graph-panel')).toBeInTheDocument();
      expect(screen.getByTestId('flow-node-AEX')).toBeInTheDocument();
      expect(screen.getByTestId('flow-node-EVL')).toBeInTheDocument();
      expect(screen.getByTestId('flow-edge-list')).toBeInTheDocument();
      expect(screen.getAllByTestId('flow-edge-broken').length).toBeGreaterThan(0);
    });

    expect(screen.getByTestId('flow-node-AEX').textContent).toContain('source: fallback');
    expect(screen.getByTestId('flow-node-EVL').textContent).toContain('trust: unknown');
  });

  it('renders next best step panel from artifact payload', async () => {
    setupFetch();
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByTestId('next-step-panel')).toBeInTheDocument();
      expect(screen.getByText('Next Best Step')).toBeInTheDocument();
      expect(screen.getAllByText(/RFX LOOP-09\/10/).length).toBeGreaterThan(0);
      expect(screen.getByText(/Rejected next steps/i)).toBeInTheDocument();
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


  it('dashboard does not compute ranking in UI layer', async () => {
    setupFetch();
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByTestId('next-systems-panel')).toBeInTheDocument();
    });
    expect(screen.getByText(/Dashboard does not compute ranking\./i)).toBeInTheDocument();
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
            rank_explanation: 'prioritization: HOP has global_rank=7.',
            prerequisite_explanation: 'prerequisite_signal: finish EVL first.',
            safe_next_action: 'recommendation: harden EVL before build scope on HOP.',
            build_now_assessment: 'prerequisite_signal',
            why_not_higher: 'prerequisite_signal: ranked behind prerequisites EVL',
            why_not_lower: 'prioritization: requested candidate remains in ranked set with explicit signals.',
            minimum_safe_prompt_scope: 'prerequisite_signal: harden prerequisite systems only (EVL).',
            dependency_warning_level: 'prerequisite_signal',
            evidence_summary: 'observation: classification=active_system.',
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
            rank_explanation: 'observation: H01 is h_slice.',
            prerequisite_explanation: 'ready_signal: no higher-ranked active upstream prerequisites detected.',
            safe_next_action: 'recommendation: build H01 now with recommendation: minimal single-system scope for H01.',
            build_now_assessment: 'ready_signal',
            why_not_higher: 'observation: no stronger upstream score signal identified',
            why_not_lower: 'prioritization: requested candidate remains in ranked set with explicit signals.',
            minimum_safe_prompt_scope: 'recommendation: minimal single-system scope for H01.',
            dependency_warning_level: 'ready_signal',
            evidence_summary: 'observation: classification=h_slice.',
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
            rank_explanation: 'unknown_signal: registry/evidence is insufficient.',
            prerequisite_explanation: 'Unknown prerequisites: retrieve registry/evidence rows first.',
            safe_next_action: 'finding: retrieve registry + evidence and re-run TLS pipeline.',
            build_now_assessment: 'blocked_signal',
            why_not_higher: 'unknown_signal: candidate lacks proven registry/evidence activity',
            why_not_lower: 'finding: unresolved candidate retained for operator visibility.',
            minimum_safe_prompt_scope: 'finding: classify candidate only; avoid build changes.',
            dependency_warning_level: 'unknown_signal',
            evidence_summary: 'observation: no classification/evidence row found.',
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
      expect(within(panel).getAllByTestId('requested-candidate-details').length).toBeGreaterThan(0);
      expect(panel).toHaveTextContent(/rank_explanation:/);
      expect(panel).toHaveTextContent(/minimum_safe_prompt_scope:/);
      expect(panel).toHaveTextContent(/evidence_summary:/);
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
