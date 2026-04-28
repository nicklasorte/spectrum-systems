import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { SystemTrustGraph } from '@/components/SystemTrustGraph';
import { SystemInspector } from '@/components/SystemInspector';
import { EdgeInspector } from '@/components/EdgeInspector';
import { ExplainFreezePanel } from '@/components/ExplainFreezePanel';
import { DebugModeSelector } from '@/components/DebugModeSelector';
import { RecommendationDebugPanel } from '@/components/RecommendationDebugPanel';
import { DiffSinceLastRecompute } from '@/components/DiffSinceLastRecompute';
import { SourceBreadcrumbs } from '@/components/SourceBreadcrumbs';
import type { SystemGraphPayload } from '@/lib/systemGraph';
import type { PriorityArtifactLoadResult } from '@/lib/artifactLoader';

const fullGraph: SystemGraphPayload = {
  graph_state: 'freeze_signal',
  generated_at: '2026-04-27T00:00:00Z',
  source_mix: { artifact_store: 6, repo_registry: 0, derived: 1, stub_fallback: 1, missing: 1 },
  trust_posture: 'freeze_signal',
  nodes: [
    {
      system_id: 'AEX', label: 'AEX', layer: 'core', role: 'admission',
      trust_state: 'trusted_signal', artifact_backed_percent: 100, source_type: 'artifact_store',
      trust_gap_signals: [], upstream: [], downstream: ['EVL'],
      source_artifact_refs: ['artifacts/tls/system_registry_dependency_graph.json'],
      warning_count: 0, is_focus: false, is_fallback_backed: false, is_disconnected: false,
      debug_status: 'OK', why_blocked: null, missing_artifacts: [], failed_evals: [],
      trace_gaps: [], upstream_blockers: [], downstream_dependents: ['EVL'],
      schema_paths: ['schemas/tls/system_registry_dependency_graph.schema.json'],
      producing_script: 'python scripts/build_tls_dependency_priority.py',
      last_recompute: '2026-04-27T00:00:00Z',
    },
    {
      system_id: 'EVL', label: 'EVL', layer: 'core', role: 'evaluation',
      trust_state: 'freeze_signal', artifact_backed_percent: 100, source_type: 'artifact_store',
      trust_gap_signals: ['missing_eval', 'missing_replay'], upstream: ['AEX'], downstream: ['TPA'],
      source_artifact_refs: ['artifacts/tls/system_trust_gap_report.json'],
      warning_count: 2, is_focus: true, is_fallback_backed: false, is_disconnected: false,
      debug_status: 'FAILED',
      why_blocked: 'failing signals: missing_eval, missing_replay',
      missing_artifacts: [],
      failed_evals: ['missing_eval', 'missing_replay'],
      trace_gaps: [],
      upstream_blockers: [],
      downstream_dependents: ['TPA'],
      schema_paths: ['schemas/tls/system_trust_gap_report.schema.json'],
      producing_script: 'python scripts/build_tls_dependency_priority.py',
      last_recompute: '2026-04-27T00:00:00Z',
    },
    {
      system_id: 'TPA', label: 'TPA', layer: 'core', role: 'trust pulse',
      trust_state: 'caution_signal', artifact_backed_percent: 90, source_type: 'artifact_store',
      trust_gap_signals: ['schema_weakness'], upstream: ['EVL'], downstream: ['CDE'],
      source_artifact_refs: ['artifacts/tls/system_trust_gap_report.json'],
      warning_count: 1, is_focus: false, is_fallback_backed: false, is_disconnected: false,
      debug_status: 'STALE',
      why_blocked: 'upstream blocked: EVL',
      missing_artifacts: [],
      failed_evals: ['schema_weakness'],
      trace_gaps: [],
      upstream_blockers: ['EVL'],
      downstream_dependents: ['CDE'],
      schema_paths: ['schemas/tls/system_trust_gap_report.schema.json'],
      producing_script: 'python scripts/build_tls_dependency_priority.py',
      last_recompute: '2026-04-27T00:00:00Z',
    },
    {
      system_id: 'CDE', label: 'CDE', layer: 'core', role: 'control decision',
      trust_state: 'trusted_signal', artifact_backed_percent: 95, source_type: 'artifact_store',
      trust_gap_signals: [], upstream: ['TPA'], downstream: ['SEL'],
      source_artifact_refs: ['artifacts/tls/system_registry_dependency_graph.json'],
      warning_count: 0, is_focus: false, is_fallback_backed: false, is_disconnected: false,
      debug_status: 'OK', why_blocked: null, missing_artifacts: [], failed_evals: [],
      trace_gaps: [], upstream_blockers: [], downstream_dependents: ['SEL'],
      schema_paths: ['schemas/tls/system_registry_dependency_graph.schema.json'],
      producing_script: 'python scripts/build_tls_dependency_priority.py',
      last_recompute: '2026-04-27T00:00:00Z',
    },
    {
      system_id: 'SEL', label: 'SEL', layer: 'core', role: 'enforcement',
      trust_state: 'trusted_signal', artifact_backed_percent: 95, source_type: 'artifact_store',
      trust_gap_signals: [], upstream: ['CDE'], downstream: [],
      source_artifact_refs: ['artifacts/tls/system_registry_dependency_graph.json'],
      warning_count: 0, is_focus: false, is_fallback_backed: false, is_disconnected: false,
      debug_status: 'OK', why_blocked: null, missing_artifacts: [], failed_evals: [],
      trace_gaps: [], upstream_blockers: [], downstream_dependents: [],
      schema_paths: ['schemas/tls/system_registry_dependency_graph.schema.json'],
      producing_script: 'python scripts/build_tls_dependency_priority.py',
      last_recompute: '2026-04-27T00:00:00Z',
    },
    {
      system_id: 'PQX', label: 'PQX', layer: 'core', role: 'execution',
      trust_state: 'caution_signal', artifact_backed_percent: 70, source_type: 'derived',
      trust_gap_signals: ['missing_observability'], upstream: ['AEX'], downstream: ['EVL'],
      source_artifact_refs: ['artifacts/tls/system_evidence_attachment.json'],
      warning_count: 1, is_focus: false, is_fallback_backed: false, is_disconnected: false,
      debug_status: 'STALE',
      why_blocked: 'failing signals: missing_observability',
      missing_artifacts: [],
      failed_evals: ['missing_observability'],
      trace_gaps: [],
      upstream_blockers: [],
      downstream_dependents: ['EVL'],
      schema_paths: ['schemas/tls/system_evidence_attachment.schema.json'],
      producing_script: 'python scripts/build_tls_dependency_priority.py',
      last_recompute: '2026-04-27T00:00:00Z',
    },
    {
      system_id: 'H01', label: 'H01', layer: 'candidate', role: 'candidate',
      trust_state: 'unknown_signal', artifact_backed_percent: 0, source_type: 'missing',
      trust_gap_signals: ['missing_tests'], upstream: [], downstream: [],
      source_artifact_refs: [], warning_count: 2, is_focus: false, is_fallback_backed: true, is_disconnected: true,
      debug_status: 'MISSING',
      why_blocked: 'source artifact missing',
      missing_artifacts: ['artifacts/tls/system_registry_dependency_graph.json'],
      failed_evals: ['missing_tests'],
      trace_gaps: ['evidence_attachment_missing'],
      upstream_blockers: [],
      downstream_dependents: [],
      schema_paths: [],
      producing_script: null,
      last_recompute: null,
    },
  ],
  edges: [
    { from: 'AEX', to: 'EVL', edge_type: 'dependency', source_type: 'artifact_store', source_artifact_ref: 'artifacts/tls/system_registry_dependency_graph.json', confidence: 1, is_failure_path: true, is_broken: false, dependency_type: 'dependency', artifact_backed: true, last_validated: '2026-04-27T00:00:00Z', related_signal: 'failure_path_signal' },
    { from: 'EVL', to: 'TPA', edge_type: 'dependency', source_type: 'artifact_store', source_artifact_ref: 'artifacts/tls/system_registry_dependency_graph.json', confidence: 1, is_failure_path: true, is_broken: false, dependency_type: 'dependency', artifact_backed: true, last_validated: '2026-04-27T00:00:00Z', related_signal: 'failure_path_signal' },
    { from: 'TPA', to: 'CDE', edge_type: 'dependency', source_type: 'artifact_store', source_artifact_ref: 'artifacts/tls/system_registry_dependency_graph.json', confidence: 1, is_failure_path: false, is_broken: false, dependency_type: 'dependency', artifact_backed: true, last_validated: '2026-04-27T00:00:00Z', related_signal: null },
    { from: 'CDE', to: 'SEL', edge_type: 'dependency', source_type: 'artifact_store', source_artifact_ref: 'artifacts/tls/system_registry_dependency_graph.json', confidence: 1, is_failure_path: false, is_broken: false, dependency_type: 'dependency', artifact_backed: true, last_validated: '2026-04-27T00:00:00Z', related_signal: null },
    { from: 'PQX', to: 'EVL', edge_type: 'dependency', source_type: 'derived', source_artifact_ref: 'artifacts/tls/system_evidence_attachment.json', confidence: 0.6, is_failure_path: false, is_broken: false, dependency_type: 'dependency', artifact_backed: false, last_validated: null, related_signal: null },
  ],
  focus_systems: ['EVL', 'TPA'],
  failure_path: ['AEX', 'EVL', 'TPA'],
  missing_artifacts: ['artifacts/tls/system_graph_validation_report.json'],
  warnings: ['missing_artifact:artifacts/tls/system_graph_validation_report.json'],
  replay_commands: ['python scripts/build_tls_dependency_priority.py'],
};

describe('Trust Debugger — Node Debug Inspector', () => {
  it('shows full debug fields when node is selected', () => {
    const node = fullGraph.nodes.find((n) => n.system_id === 'EVL') ?? null;
    render(<SystemInspector node={node} replayCommands={fullGraph.replay_commands} />);
    expect(screen.getByTestId('system-inspector')).toHaveTextContent('Investigate: EVL');
    expect(screen.getByTestId('inspector-status')).toHaveAttribute('data-status', 'FAILED');
    expect(screen.getByTestId('inspector-why-blocked')).toHaveTextContent('failing signals: missing_eval');
    expect(screen.getByTestId('inspector-failed-evals')).toHaveTextContent('missing_eval');
    expect(screen.getByTestId('inspector-downstream-dependents')).toHaveTextContent('TPA');
    expect(screen.getByTestId('inspector-last-recompute')).toHaveTextContent('2026-04-27T00:00:00Z');
    expect(screen.getByTestId('inspector-breadcrumbs-artifact')).toHaveTextContent(
      'artifacts/tls/system_trust_gap_report.json',
    );
    expect(screen.getByTestId('inspector-breadcrumbs-script')).toHaveTextContent(
      'python scripts/build_tls_dependency_priority.py',
    );
  });

  it('renders Unknown / Missing fields for nodes with no debugger data, and emits fail-closed warning', () => {
    const node = fullGraph.nodes.find((n) => n.system_id === 'H01') ?? null;
    render(<SystemInspector node={node} replayCommands={fullGraph.replay_commands} />);
    expect(screen.getByTestId('inspector-fail-closed-warning')).toBeInTheDocument();
    expect(screen.getByTestId('inspector-status')).toHaveAttribute('data-status', 'MISSING');
    expect(screen.getByTestId('inspector-breadcrumbs-script')).toHaveTextContent('Unknown / Missing');
  });

  it('clicking a graph node opens the inspector for that system', () => {
    let selected: string | null = null;
    function Harness() {
      const node = fullGraph.nodes.find((n) => n.system_id === selected) ?? null;
      return (
        <>
          <SystemTrustGraph
            graph={fullGraph}
            selectedSystem={selected}
            showAll
            graphMode="full_registry"
            onSelect={(id) => { selected = id; }}
          />
          <SystemInspector node={node} replayCommands={fullGraph.replay_commands} />
        </>
      );
    }
    const { rerender } = render(<Harness />);
    fireEvent.click(screen.getByTestId('trust-node-EVL'));
    rerender(<Harness />);
    expect(screen.getByTestId('system-inspector')).toHaveTextContent('Investigate: EVL');
  });
});

describe('Trust Debugger — Propagation path highlighting', () => {
  it('Explain Freeze toggle highlights root-cause and propagation path nodes', () => {
    let path: string[] = [];
    function Harness() {
      return (
        <>
          <ExplainFreezePanel graph={fullGraph} onPathChange={(p) => { path = p; }} />
          <SystemTrustGraph
            graph={fullGraph}
            selectedSystem={null}
            showAll
            graphMode="full_registry"
            highlightedPath={path}
            onSelect={() => undefined}
          />
        </>
      );
    }
    const { rerender } = render(<Harness />);
    expect(screen.getByTestId('explain-freeze-path-text')).toHaveTextContent('AEX → EVL → TPA');
    fireEvent.click(screen.getByTestId('explain-freeze-toggle'));
    rerender(<Harness />);
    expect(screen.getByTestId('trust-node-AEX')).toHaveAttribute('data-highlight-root', 'true');
    expect(screen.getByTestId('trust-node-EVL')).toHaveAttribute('data-highlight-path', 'true');
    expect(screen.getByTestId('trust-node-TPA')).toHaveAttribute('data-highlight-path', 'true');
  });

  it('distinguishes direct blockers from downstream affected systems', () => {
    render(<ExplainFreezePanel graph={fullGraph} forceVisible />);
    expect(screen.getByTestId('explain-freeze-direct-blockers')).toBeInTheDocument();
    expect(screen.getByTestId('explain-freeze-downstream-affected')).toHaveTextContent('EVL, TPA');
  });
});

describe('Trust Debugger — Debug Modes', () => {
  it('Blockers mode emphasises blocking systems and dims healthy ones', () => {
    render(
      <SystemTrustGraph
        graph={fullGraph}
        selectedSystem={null}
        showAll
        graphMode="full_registry" debugMode="blockers"
        onSelect={() => undefined}
      />,
    );
    expect(screen.getByTestId('system-trust-graph')).toHaveAttribute('data-debug-mode', 'blockers');
    expect(screen.getByTestId('trust-node-EVL')).toHaveAttribute('opacity', '1');
    expect(screen.getByTestId('trust-node-AEX')).toHaveAttribute('opacity', '0.2');
  });

  it('Control mode highlights only EVL/TPA/CDE/SEL', () => {
    render(
      <SystemTrustGraph
        graph={fullGraph}
        selectedSystem={null}
        showAll
        graphMode="full_registry" debugMode="control"
        onSelect={() => undefined}
      />,
    );
    expect(screen.getByTestId('trust-node-EVL')).toHaveAttribute('opacity', '1');
    expect(screen.getByTestId('trust-node-CDE')).toHaveAttribute('opacity', '1');
    expect(screen.getByTestId('trust-node-SEL')).toHaveAttribute('opacity', '1');
    expect(screen.getByTestId('trust-node-AEX')).toHaveAttribute('opacity', '0.25');
  });

  it('Lineage mode dims edges that are not artifact-backed', () => {
    render(
      <SystemTrustGraph
        graph={fullGraph}
        selectedSystem={null}
        showAll
        graphMode="full_registry" debugMode="lineage"
        onSelect={() => undefined}
      />,
    );
    const backedEdge = screen.getByTestId('trust-edge-AEX-EVL');
    expect(backedEdge).toHaveAttribute('data-edge-artifact-backed', 'true');
    const inferred = screen.getByTestId('trust-edge-PQX-EVL');
    expect(inferred).toHaveAttribute('data-edge-artifact-backed', 'false');
  });

  it('Freshness mode emphasises stale and missing nodes', () => {
    render(
      <SystemTrustGraph
        graph={fullGraph}
        selectedSystem={null}
        showAll
        graphMode="full_registry" debugMode="freshness"
        onSelect={() => undefined}
      />,
    );
    expect(screen.getByTestId('trust-node-H01')).toHaveAttribute('opacity', '1');
    expect(screen.getByTestId('trust-node-TPA')).toHaveAttribute('opacity', '1');
    expect(screen.getByTestId('trust-node-AEX')).toHaveAttribute('opacity', '0.3');
  });

  it('DebugModeSelector calls onChange with selected mode value', () => {
    let captured: string = 'normal';
    render(<DebugModeSelector value="normal" onChange={(m) => { captured = m; }} />);
    fireEvent.change(screen.getByTestId('debug-mode-selector-input'), { target: { value: 'blockers' } });
    expect(captured).toBe('blockers');
  });
});

describe('Trust Debugger — Edge inspector and labels', () => {
  it('shows dependency type, artifact-backed flag, last validated, related signal', () => {
    const edge = fullGraph.edges.find((e) => e.from === 'AEX' && e.to === 'EVL') ?? null;
    render(<EdgeInspector edge={edge} />);
    expect(screen.getByTestId('edge-inspector')).toHaveTextContent('Edge: AEX → EVL');
    expect(screen.getByTestId('edge-inspector-dependency-type')).toHaveTextContent('dependency');
    expect(screen.getByTestId('edge-inspector-artifact-backed')).toHaveTextContent('yes (artifact-backed)');
    expect(screen.getByTestId('edge-inspector-last-validated')).toHaveTextContent('2026-04-27T00:00:00Z');
    expect(screen.getByTestId('edge-inspector-related-signal')).toHaveTextContent('failure_path_signal');
    expect(screen.getByTestId('edge-inspector-breadcrumbs-artifact')).toHaveTextContent(
      'artifacts/tls/system_registry_dependency_graph.json',
    );
  });

  it('shows Unknown / Missing for inferred edges with no last_validated', () => {
    const edge = fullGraph.edges.find((e) => e.from === 'PQX' && e.to === 'EVL') ?? null;
    render(<EdgeInspector edge={edge} />);
    expect(screen.getByTestId('edge-inspector-artifact-backed')).toHaveTextContent('no (inferred)');
    expect(screen.getByTestId('edge-inspector-last-validated')).toHaveTextContent('Unknown / Missing');
  });

  it('clicking an edge fires onSelectEdge in the graph', () => {
    let selected: string | null = null;
    render(
      <SystemTrustGraph
        graph={fullGraph}
        selectedSystem={null}
        showAll
        graphMode="full_registry"
        onSelect={() => undefined}
        onSelectEdge={(e) => { selected = `${e.from}-${e.to}`; }}
      />,
    );
    fireEvent.click(screen.getByTestId('trust-edge-EVL-TPA'));
    expect(selected).toBe('EVL-TPA');
  });
});

describe('Trust Debugger — Recommendation Debug Panel', () => {
  const priorityResult: PriorityArtifactLoadResult = {
    state: 'ok',
    generated_at: '2026-04-27T00:00:00Z',
    payload: {
      schema_version: 'tls-04.v1',
      phase: 'TLS-04',
      priority_order: [],
      penalties: [],
      ranked_systems: [],
      global_ranked_systems: [
        {
          rank: 1, system_id: 'EVL', classification: 'active_system', score: 221,
          action: 'finish_hardening',
          why_now: 'on canonical loop; trust-boundary authority',
          trust_gap_signals: ['missing_eval'],
          dependencies: { upstream: ['PQX'], downstream: ['CDE'] },
          unlocks: ['CDE'],
          finish_definition: 'resolve missing_eval',
          next_prompt: 'Run TLS-FIX-EVL: resolve missing_eval on system EVL',
          trust_state: 'freeze_signal',
        },
      ],
      top_5: [],
      requested_candidate_set: ['H01'],
      requested_candidate_ranking: [
        {
          requested_rank: 1, system_id: 'H01', classification: 'h_slice',
          recommended_action: 'harden_authority',
          why_now: 'multiple gaps',
          prerequisite_systems: ['EVL'],
          trust_gap_signals: ['missing_tests'],
          finish_definition: 'resolve missing_tests',
          risk_if_built_before_prerequisites: 'risk: upstream EVL not finished',
          rank_explanation: 'prioritization: H01 has global_rank=14 in deterministic ranking',
          prerequisite_explanation: 'finish EVL first',
          safe_next_action: 'recommendation: build H01',
          build_now_assessment: 'caution_signal',
          why_not_higher: 'observation: no stronger upstream',
          why_not_lower: 'remains in ranked set',
          minimum_safe_prompt_scope: 'recommendation: single-system hardening for H01',
          dependency_warning_level: 'caution_signal',
          evidence_summary: 'observation: classification=h_slice; gap_score=72',
        },
      ],
      ambiguous_requested_candidates: [],
    },
  };

  it('renders artifact-backed explanation fields without computing rankings', () => {
    render(<RecommendationDebugPanel priority={priorityResult} />);
    const card = screen.getByTestId('rec-debug-card-H01');
    expect(card).toBeInTheDocument();
    expect(screen.getByTestId('rec-debug-why-H01')).toHaveTextContent('global_rank=14');
    expect(screen.getByTestId('rec-debug-support-H01')).toHaveTextContent('classification=h_slice');
    expect(screen.getByTestId('rec-debug-block-H01')).toHaveTextContent('EVL');
    expect(screen.getByTestId('rec-debug-scope-H01')).toHaveTextContent(
      'recommendation: single-system hardening for H01',
    );
    expect(screen.getByTestId('rec-debug-boundary-H01')).toHaveTextContent('risk: upstream EVL not finished');
    expect(screen.getByTestId('rec-debug-breadcrumbs-H01-artifact')).toHaveTextContent(
      'artifacts/system_dependency_priority_report.json',
    );
  });

  it('shows fail-closed warning when priority artifact is missing', () => {
    render(
      <RecommendationDebugPanel
        priority={{ state: 'missing', payload: null, reason: 'not_found' }}
      />,
    );
    expect(screen.getByTestId('recommendation-debug-fail-closed')).toBeInTheDocument();
  });

  it('does not include any client-side ranking computation in source', () => {
    const src = RecommendationDebugPanel.toString();
    expect(src).not.toMatch(/\.sort\s*\(/);
    expect(src).not.toMatch(/\.score\s*[+-]/);
  });
});

describe('Trust Debugger — Diff Since Last Recompute', () => {
  it('shows "No previous snapshot available." when previous is null', () => {
    render(<DiffSinceLastRecompute current={fullGraph} previous={null} />);
    expect(screen.getByTestId('diff-no-snapshot')).toHaveTextContent('No previous snapshot available.');
  });

  it('lists new and resolved blockers between two snapshots', () => {
    const previous: SystemGraphPayload = {
      ...fullGraph,
      nodes: fullGraph.nodes.map((n) =>
        n.system_id === 'EVL'
          ? { ...n, debug_status: 'OK', trust_state: 'trusted_signal', failed_evals: [], why_blocked: null }
          : n,
      ),
      focus_systems: ['CDE'],
    };
    const current: SystemGraphPayload = {
      ...fullGraph,
      focus_systems: ['EVL', 'TPA'],
    };
    render(
      <DiffSinceLastRecompute current={current} previous={previous} recomputeStatus="recompute_success_signal" />,
    );
    expect(screen.getByTestId('diff-new-blockers')).toHaveTextContent('EVL');
    expect(screen.getByTestId('diff-recompute-status')).toHaveTextContent('recompute_success_signal');
    expect(screen.getByTestId('diff-ranking-changes')).toHaveTextContent('CDE');
  });
});

describe('Trust Debugger — Source Breadcrumbs', () => {
  it('renders artifact, schema, script, last validation', () => {
    render(
      <SourceBreadcrumbs
        artifactPaths={['artifacts/x.json']}
        schemaPaths={['schemas/x.schema.json']}
        producingScript="python build_x.py"
        lastValidated="2026-04-27T00:00:00Z"
      />,
    );
    expect(screen.getByTestId('source-breadcrumbs-artifact')).toHaveTextContent('artifacts/x.json');
    expect(screen.getByTestId('source-breadcrumbs-schema')).toHaveTextContent('schemas/x.schema.json');
    expect(screen.getByTestId('source-breadcrumbs-script')).toHaveTextContent('python build_x.py');
    expect(screen.getByTestId('source-breadcrumbs-validated')).toHaveTextContent('2026-04-27T00:00:00Z');
  });

  it('shows Unknown / Missing for omitted fields', () => {
    render(<SourceBreadcrumbs artifactPaths={[]} />);
    expect(screen.getByTestId('source-breadcrumbs-artifact')).toHaveTextContent('Unknown / Missing');
    expect(screen.getByTestId('source-breadcrumbs-schema')).toHaveTextContent('Unknown / Missing');
    expect(screen.getByTestId('source-breadcrumbs-script')).toHaveTextContent('Unknown / Missing');
    expect(screen.getByTestId('source-breadcrumbs-validated')).toHaveTextContent('Unknown / Missing');
  });
});
