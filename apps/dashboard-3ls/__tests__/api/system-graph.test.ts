import { buildSystemGraphPayload } from '@/lib/systemGraphBuilder';

describe('/api/system-graph payload', () => {
  it('returns normalized graph payload from artifacts', () => {
    const payload = buildSystemGraphPayload('2026-04-27T00:00:00.000Z');
    expect(payload.graph_state).toBeDefined();
    expect(payload.nodes.length).toBeGreaterThan(0);
    expect(payload.edges.length).toBeGreaterThan(0);
    expect(payload).toHaveProperty('focus_systems');
    expect(payload).toHaveProperty('replay_commands');
  });

  it('reports missing graph validation artifact with warning and no fake edges', () => {
    const payload = buildSystemGraphPayload('2026-04-27T00:00:00.000Z');
    expect(payload.warnings.join(' ')).toContain('system_graph_validation_report.json');
    for (const edge of payload.edges) {
      expect(payload.nodes.some((node) => node.system_id === edge.from)).toBe(true);
    }
  });
});
