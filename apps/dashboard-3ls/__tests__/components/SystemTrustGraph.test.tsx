import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { SystemTrustGraph } from '@/components/SystemTrustGraph';
import { SystemInspector } from '@/components/SystemInspector';
import { ExplainFreezePanel } from '@/components/ExplainFreezePanel';
import type { SystemGraphPayload } from '@/lib/systemGraph';

const graph: SystemGraphPayload = {
  graph_state: 'freeze_signal',
  generated_at: '2026-04-27T00:00:00Z',
  source_mix: { artifact_store: 8, repo_registry: 0, derived: 1, stub_fallback: 1, missing: 0 },
  trust_posture: 'freeze_signal',
  nodes: [
    { system_id: 'AEX', label: 'AEX', layer: 'core', role: 'admission', trust_state: 'trusted_signal', artifact_backed_percent: 100, source_type: 'artifact_store', trust_gap_signals: [], upstream: [], downstream: ['PQX'], source_artifact_refs: ['a'], warning_count: 0, is_focus: false, is_fallback_backed: false, is_disconnected: false },
    { system_id: 'EVL', label: 'EVL', layer: 'core', role: 'evaluation', trust_state: 'freeze_signal', artifact_backed_percent: 100, source_type: 'artifact_store', trust_gap_signals: ['missing_eval'], upstream: ['PQX'], downstream: ['TPA'], source_artifact_refs: ['b'], warning_count: 1, is_focus: true, is_fallback_backed: false, is_disconnected: false },
    { system_id: 'REP', label: 'REP', layer: 'overlay', role: 'replay', trust_state: 'caution_signal', artifact_backed_percent: 100, source_type: 'artifact_store', trust_gap_signals: [], upstream: [], downstream: ['EVL'], source_artifact_refs: ['c'], warning_count: 0, is_focus: false, is_fallback_backed: false, is_disconnected: false },
    { system_id: 'H01', label: 'H01', layer: 'candidate', role: 'candidate', trust_state: 'unknown_signal', artifact_backed_percent: 0, source_type: 'missing', trust_gap_signals: ['missing_tests'], upstream: [], downstream: [], source_artifact_refs: ['d'], warning_count: 2, is_focus: false, is_fallback_backed: true, is_disconnected: true },
  ],
  edges: [
    { from: 'AEX', to: 'EVL', edge_type: 'dependency', source_type: 'artifact_store', source_artifact_ref: 'x', confidence: 1, is_failure_path: false, is_broken: false },
    { from: 'REP', to: 'EVL', edge_type: 'overlay', source_type: 'derived', source_artifact_ref: 'y', confidence: 0.7, is_failure_path: true, is_broken: false },
  ],
  focus_systems: ['EVL'],
  failure_path: ['EVL', 'TPA'],
  missing_artifacts: ['artifacts/tls/system_graph_validation_report.json'],
  warnings: ['missing_artifact:artifacts/tls/system_graph_validation_report.json'],
  replay_commands: ['python scripts/build_tls_dependency_priority.py --candidates H01,RFX,HOP,MET,METS --fail-if-missing'],
};

describe('SystemTrustGraph + inspector', () => {
  it('renders core, overlay, and candidate systems', () => {
    render(<SystemTrustGraph graph={graph} selectedSystem={null} showAll onSelect={() => undefined} />);
    expect(screen.getByTestId('trust-node-AEX')).toBeInTheDocument();
    expect(screen.getByTestId('trust-node-REP')).toBeInTheDocument();
    expect(screen.getByTestId('trust-node-H01')).toBeInTheDocument();
  });

  it('applies focus dimming when showAll is false', () => {
    render(<SystemTrustGraph graph={graph} selectedSystem={null} showAll={false} onSelect={() => undefined} />);
    expect(screen.getByTestId('trust-node-EVL')).toHaveAttribute('opacity', '1');
    expect(screen.getByTestId('trust-node-H01')).toHaveAttribute('opacity', '0.25');
  });

  it('clicking node opens inspector details', () => {
    let selected = 'EVL';
    const { rerender } = render(
      <>
        <SystemTrustGraph graph={graph} selectedSystem={selected} showAll onSelect={(id) => { selected = id; }} />
        <SystemInspector node={graph.nodes.find((n) => n.system_id === selected) ?? null} replayCommands={graph.replay_commands} />
      </>,
    );

    fireEvent.click(screen.getByTestId('trust-node-H01'));
    rerender(
      <>
        <SystemTrustGraph graph={graph} selectedSystem={selected} showAll onSelect={(id) => { selected = id; }} />
        <SystemInspector node={graph.nodes.find((n) => n.system_id === selected) ?? null} replayCommands={graph.replay_commands} />
      </>,
    );

    expect(screen.getByTestId('system-inspector')).toHaveTextContent('Investigate: H01');
    expect(screen.getByTestId('system-inspector')).toHaveTextContent('minimum safe prompt scope');
  });

  it('explain freeze panel renders failure path', () => {
    render(<ExplainFreezePanel graph={graph} />);
    expect(screen.getByTestId('explain-freeze-panel')).toHaveTextContent('Propagation path: EVL → TPA');
  });

  it('graph source does not hard-code authoritative edges', () => {
    expect(SystemTrustGraph.toString()).not.toContain('AEX → PQX → EVL');
  });
});
