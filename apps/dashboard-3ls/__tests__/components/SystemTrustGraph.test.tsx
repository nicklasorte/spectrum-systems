import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { SystemTrustGraph } from '@/components/SystemTrustGraph';
import { SystemInspector } from '@/components/SystemInspector';
import { ExplainFreezePanel } from '@/components/ExplainFreezePanel';
import { GraphLegend } from '@/components/GraphLegend';
import type { SystemGraphPayload } from '@/lib/systemGraph';

const graph: SystemGraphPayload = {
  graph_state: 'freeze_signal',
  generated_at: '2026-04-27T00:00:00Z',
  source_mix: { artifact_store: 8, repo_registry: 0, derived: 1, stub_fallback: 1, missing: 0 },
  trust_posture: 'freeze_signal',
  nodes: [
    { system_id: 'AEX', label: 'AEX', layer: 'core', role: 'admission', trust_state: 'trusted_signal', artifact_backed_percent: 100, source_type: 'artifact_store', trust_gap_signals: [], upstream: [], downstream: ['PQX'], source_artifact_refs: ['a'], warning_count: 0, is_focus: false, is_fallback_backed: false, is_disconnected: false },
    { system_id: 'PQX', label: 'PQX', layer: 'core', role: 'execution', trust_state: 'trusted_signal', artifact_backed_percent: 100, source_type: 'artifact_store', trust_gap_signals: [], upstream: ['AEX'], downstream: ['EVL'], source_artifact_refs: ['a'], warning_count: 0, is_focus: false, is_fallback_backed: false, is_disconnected: false },
    { system_id: 'EVL', label: 'EVL', layer: 'core', role: 'evaluation', trust_state: 'freeze_signal', artifact_backed_percent: 100, source_type: 'artifact_store', trust_gap_signals: ['missing_eval'], upstream: ['PQX'], downstream: ['TPA'], source_artifact_refs: ['b'], warning_count: 1, is_focus: true, is_fallback_backed: false, is_disconnected: false },
    { system_id: 'TPA', label: 'TPA', layer: 'core', role: 'trust pulse', trust_state: 'caution_signal', artifact_backed_percent: 90, source_type: 'artifact_store', trust_gap_signals: [], upstream: ['EVL'], downstream: ['CDE'], source_artifact_refs: ['a'], warning_count: 0, is_focus: false, is_fallback_backed: false, is_disconnected: false },
    { system_id: 'CDE', label: 'CDE', layer: 'core', role: 'control decision', trust_state: 'trusted_signal', artifact_backed_percent: 95, source_type: 'artifact_store', trust_gap_signals: [], upstream: ['TPA'], downstream: ['SEL'], source_artifact_refs: ['a'], warning_count: 0, is_focus: false, is_fallback_backed: false, is_disconnected: false },
    { system_id: 'SEL', label: 'SEL', layer: 'core', role: 'enforcement', trust_state: 'trusted_signal', artifact_backed_percent: 95, source_type: 'artifact_store', trust_gap_signals: [], upstream: ['CDE'], downstream: [], source_artifact_refs: ['a'], warning_count: 0, is_focus: false, is_fallback_backed: false, is_disconnected: false },
    { system_id: 'REP', label: 'REP', layer: 'overlay', role: 'replay', trust_state: 'caution_signal', artifact_backed_percent: 100, source_type: 'artifact_store', trust_gap_signals: [], upstream: [], downstream: ['EVL'], source_artifact_refs: ['c'], warning_count: 0, is_focus: false, is_fallback_backed: false, is_disconnected: false },
    { system_id: 'CTX', label: 'CTX', layer: 'support', role: 'context', trust_state: 'trusted_signal', artifact_backed_percent: 88, source_type: 'artifact_store', trust_gap_signals: [], upstream: [], downstream: ['PQX'], source_artifact_refs: ['s'], warning_count: 0, is_focus: false, is_fallback_backed: false, is_disconnected: false },
    { system_id: 'H01', label: 'H01', layer: 'candidate', role: 'candidate', trust_state: 'unknown_signal', artifact_backed_percent: 0, source_type: 'missing', trust_gap_signals: ['missing_tests'], upstream: [], downstream: [], source_artifact_refs: ['d'], warning_count: 2, is_focus: false, is_fallback_backed: true, is_disconnected: true },
  ],
  edges: [
    { from: 'AEX', to: 'PQX', edge_type: 'dependency', source_type: 'artifact_store', source_artifact_ref: 'x', confidence: 1, is_failure_path: false, is_broken: false },
    { from: 'PQX', to: 'EVL', edge_type: 'dependency', source_type: 'artifact_store', source_artifact_ref: 'x', confidence: 1, is_failure_path: false, is_broken: false },
    { from: 'EVL', to: 'TPA', edge_type: 'dependency', source_type: 'artifact_store', source_artifact_ref: 'x', confidence: 1, is_failure_path: false, is_broken: false },
    { from: 'TPA', to: 'CDE', edge_type: 'dependency', source_type: 'artifact_store', source_artifact_ref: 'x', confidence: 1, is_failure_path: false, is_broken: false },
    { from: 'CDE', to: 'SEL', edge_type: 'dependency', source_type: 'artifact_store', source_artifact_ref: 'x', confidence: 1, is_failure_path: false, is_broken: false },
    { from: 'REP', to: 'EVL', edge_type: 'overlay', source_type: 'derived', source_artifact_ref: 'y', confidence: 0.7, is_failure_path: true, is_broken: false },
    { from: 'CTX', to: 'PQX', edge_type: 'support', source_type: 'derived', source_artifact_ref: 'z', confidence: 0.7, is_failure_path: false, is_broken: false },
  ],
  focus_systems: ['EVL'],
  failure_path: ['EVL', 'TPA'],
  missing_artifacts: ['artifacts/tls/system_graph_validation_report.json'],
  warnings: ['missing_artifact:artifacts/tls/system_graph_validation_report.json'],
  replay_commands: ['python scripts/build_tls_dependency_priority.py --candidates H01,RFX,HOP,MET,METS --fail-if-missing'],
};

describe('SystemTrustGraph + inspector', () => {
  it('default clean structure mode shows only core chain nodes', () => {
    render(<SystemTrustGraph graph={graph} selectedSystem={null} showAll onSelect={() => undefined} />);
    expect(screen.getByTestId('trust-node-AEX')).toBeInTheDocument();
    expect(screen.getByTestId('trust-node-SEL')).toBeInTheDocument();
    expect(screen.queryByTestId('trust-node-REP')).not.toBeInTheDocument();
    expect(screen.queryByTestId('trust-node-CTX')).not.toBeInTheDocument();
  });

  it('renders core, overlay, support, and candidate systems', () => {
    render(<SystemTrustGraph graph={graph} selectedSystem={null} showAll graphMode="full_registry" onSelect={() => undefined} />);
    expect(screen.getByTestId('trust-node-AEX')).toBeInTheDocument();
    expect(screen.getByTestId('trust-node-PQX')).toBeInTheDocument();
    expect(screen.getByTestId('trust-node-EVL')).toBeInTheDocument();
    expect(screen.getByTestId('trust-node-TPA')).toBeInTheDocument();
    expect(screen.getByTestId('trust-node-CDE')).toBeInTheDocument();
    expect(screen.getByTestId('trust-node-SEL')).toBeInTheDocument();
    expect(screen.getByTestId('trust-node-REP')).toBeInTheDocument();
    expect(screen.getByTestId('trust-node-CTX')).toBeInTheDocument();
    expect(screen.getByTestId('trust-node-H01')).toBeInTheDocument();
  });

  it('full registry mode renders dense lines and nodes', () => {
    render(<SystemTrustGraph graph={graph} selectedSystem={null} showAll graphMode="full_registry" onSelect={() => undefined} />);
    expect(screen.getByTestId('trust-node-REP')).toBeInTheDocument();
    expect(screen.getByTestId('trust-edge-CTX-PQX')).toBeInTheDocument();
  });

  it('layered layout positions core path AEX → PQX → EVL → TPA → CDE → SEL left-to-right on the same row', () => {
    render(<SystemTrustGraph graph={graph} selectedSystem={null} showAll layout="layered" graphMode="full_registry" onSelect={() => undefined} />);
    const order = ['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL'];
    const transforms = order.map((id) => screen.getByTestId(`trust-node-${id}`).getAttribute('transform') ?? '');
    const positions = transforms.map((t) => {
      const match = t.match(/translate\(([-\d.]+),\s*([-\d.]+)\)/);
      if (!match) throw new Error(`unexpected transform: ${t}`);
      return { x: Number(match[1]), y: Number(match[2]) };
    });
    for (let i = 0; i < positions.length - 1; i += 1) {
      expect(positions[i].y).toBe(positions[i + 1].y);
      expect(positions[i].x).toBeLessThan(positions[i + 1].x);
    }
  });

  it('layered layout uses distinct rows for overlay, core, support, extension', () => {
    render(<SystemTrustGraph graph={graph} selectedSystem={null} showAll layout="layered" graphMode="full_registry" onSelect={() => undefined} />);
    const overlayY = Number((screen.getByTestId('trust-node-REP').getAttribute('transform') ?? '').match(/translate\([-\d.]+,\s*([-\d.]+)\)/)?.[1]);
    const coreY = Number((screen.getByTestId('trust-node-AEX').getAttribute('transform') ?? '').match(/translate\([-\d.]+,\s*([-\d.]+)\)/)?.[1]);
    const supportY = Number((screen.getByTestId('trust-node-CTX').getAttribute('transform') ?? '').match(/translate\([-\d.]+,\s*([-\d.]+)\)/)?.[1]);
    const extensionY = Number((screen.getByTestId('trust-node-H01').getAttribute('transform') ?? '').match(/translate\([-\d.]+,\s*([-\d.]+)\)/)?.[1]);
    expect(overlayY).toBeLessThan(coreY);
    expect(coreY).toBeLessThan(supportY);
    expect(supportY).toBeLessThan(extensionY);
  });

  it('renders dashed group containers for overlay, support, and extension rows', () => {
    render(<SystemTrustGraph graph={graph} selectedSystem={null} showAll layout="layered" graphMode="full_registry" onSelect={() => undefined} />);
    expect(screen.getByTestId('graph-row-overlay')).toBeInTheDocument();
    expect(screen.getByTestId('graph-row-core')).toBeInTheDocument();
    expect(screen.getByTestId('graph-row-support')).toBeInTheDocument();
    expect(screen.getByTestId('graph-row-extension')).toBeInTheDocument();
  });

  it('applies focus dimming when showAll is false', () => {
    render(<SystemTrustGraph graph={graph} selectedSystem={null} showAll={false} graphMode="full_registry" onSelect={() => undefined} />);
    expect(screen.getByTestId('trust-node-EVL')).toHaveAttribute('opacity', '1');
    expect(screen.getByTestId('trust-node-H01')).toHaveAttribute('opacity', '0.25');
  });

  it('hides secondary edges in focus mode and shows them when Show all is enabled', () => {
    const { rerender } = render(
      <SystemTrustGraph graph={graph} selectedSystem={null} showAll={false} graphMode="full_registry" onSelect={() => undefined} />,
    );
    const supportEdgeFocus = screen.getByTestId('trust-edge-CTX-PQX');
    expect(supportEdgeFocus).toHaveAttribute('data-edge-hidden', 'true');

    rerender(<SystemTrustGraph graph={graph} selectedSystem={null} showAll graphMode="full_registry" onSelect={() => undefined} />);
    const supportEdgeShowAll = screen.getByTestId('trust-edge-CTX-PQX');
    expect(supportEdgeShowAll).not.toHaveAttribute('data-edge-hidden');
  });

  it('marks core canonical edges with the core style for clear directional flow', () => {
    render(<SystemTrustGraph graph={graph} selectedSystem={null} showAll graphMode="full_registry" onSelect={() => undefined} />);
    expect(screen.getByTestId('trust-edge-AEX-PQX')).toHaveAttribute('data-edge-style', 'core');
    expect(screen.getByTestId('trust-edge-CDE-SEL')).toHaveAttribute('data-edge-style', 'core');
    expect(screen.getByTestId('trust-edge-REP-EVL')).toHaveAttribute('data-edge-style', 'failure');
  });

  it('clicking node opens inspector details', () => {
    let selected = 'EVL';
    const { rerender } = render(
      <>
        <SystemTrustGraph graph={graph} selectedSystem={selected} showAll graphMode="full_registry" onSelect={(id) => { selected = id; }} />
        <SystemInspector node={graph.nodes.find((n) => n.system_id === selected) ?? null} replayCommands={graph.replay_commands} />
      </>,
    );

    fireEvent.click(screen.getByTestId('trust-node-H01'));
    rerender(
      <>
        <SystemTrustGraph graph={graph} selectedSystem={selected} showAll graphMode="full_registry" onSelect={(id) => { selected = id; }} />
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

describe('GraphLegend', () => {
  it('renders all node groups, edge types, and trust borders', () => {
    render(<GraphLegend />);
    expect(screen.getByTestId('graph-legend')).toBeInTheDocument();

    expect(screen.getByTestId('legend-node-core')).toBeInTheDocument();
    expect(screen.getByTestId('legend-node-control')).toBeInTheDocument();
    expect(screen.getByTestId('legend-node-support')).toBeInTheDocument();
    expect(screen.getByTestId('legend-node-overlay')).toBeInTheDocument();

    expect(screen.getByTestId('legend-edge-core')).toBeInTheDocument();
    expect(screen.getByTestId('legend-edge-failure')).toBeInTheDocument();
    expect(screen.getByTestId('legend-edge-broken')).toBeInTheDocument();
    expect(screen.getByTestId('legend-edge-secondary')).toBeInTheDocument();

    expect(screen.getByTestId('legend-trust-trusted_signal')).toBeInTheDocument();
    expect(screen.getByTestId('legend-trust-caution_signal')).toBeInTheDocument();
    expect(screen.getByTestId('legend-trust-freeze_signal')).toBeInTheDocument();
    expect(screen.getByTestId('legend-trust-blocked_signal')).toBeInTheDocument();
    expect(screen.getByTestId('legend-trust-unknown_signal')).toBeInTheDocument();
  });
});
