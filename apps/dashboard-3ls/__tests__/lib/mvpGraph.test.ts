/**
 * D3L-MASTER-01 Phase 6 — MVP graph tests.
 *
 * Pins:
 *   - MVP boxes are NOT registry systems and never share node ids with
 *     active_system_ids.
 *   - Each box maps to one or more registry-active systems; mappings are
 *     validated and unknown system_ids are rejected.
 *   - Boxes/edges are stable; toggle is a UI concern (MVP graph never
 *     mutates the 3LS graph).
 */
import { buildMVPGraph, isMVPBoxId, MVP_BOXES } from '@/lib/mvpGraph';
import type { D3LRegistryContract } from '@/lib/systemRegistry';

const ACTIVE = ['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL', 'CTX', 'PRM', 'HOP', 'JDX', 'JSX', 'FRE', 'RIL', 'RAX', 'OBS', 'SLO'];

const CONTRACT: D3LRegistryContract = {
  artifact_type: 'd3l_registry_contract',
  phase: 'D3L-MASTER-01',
  schema_version: 'd3l-master-01.v1',
  source_artifact: 'artifacts/tls/system_registry_dependency_graph.json',
  active_system_ids: ACTIVE,
  future_system_ids: [],
  deprecated_or_merged_system_ids: [],
  excluded_ids: [],
  ranking_universe: ACTIVE,
  maturity_universe: ACTIVE,
  forbidden_node_examples: [],
  rules: [],
};

describe('buildMVPGraph', () => {
  it('produces every MVP box and its edges', () => {
    const g = buildMVPGraph(CONTRACT);
    expect(g.boxes.length).toBe(MVP_BOXES.length);
    expect(g.edges.length).toBeGreaterThanOrEqual(MVP_BOXES.length - 1);
    expect(g.boxes.map((b) => b.id)).toEqual(MVP_BOXES.map((b) => b.id));
  });

  it('every MVP mapping is validated against the registry contract', () => {
    const g = buildMVPGraph(CONTRACT);
    for (const v of g.validated_mappings) {
      expect(v.rejected_systems).toEqual([]);
    }
    expect(g.warnings.filter((w) => w.startsWith('mvp_box_rejected_mapping'))).toEqual([]);
  });

  it('rejects mappings to systems missing from the active universe', () => {
    const partial: D3LRegistryContract = {
      ...CONTRACT,
      active_system_ids: ['AEX', 'EVL'],
      ranking_universe: ['AEX', 'EVL'],
      maturity_universe: ['AEX', 'EVL'],
    };
    const g = buildMVPGraph(partial);
    const total = g.validated_mappings.reduce((s, v) => s + v.rejected_systems.length, 0);
    expect(total).toBeGreaterThan(0);
    expect(g.warnings.some((w) => w.startsWith('mvp_box_rejected_mapping'))).toBe(true);
  });

  it('warns when contract is missing', () => {
    const g = buildMVPGraph(null);
    expect(g.warnings.some((w) => w.startsWith('mvp_graph_contract_missing'))).toBe(true);
  });

  it('MVP box ids never collide with registry system ids', () => {
    const active = new Set(ACTIVE);
    for (const box of MVP_BOXES) {
      expect(active.has(box.id)).toBe(false);
    }
  });

  it('isMVPBoxId returns true for box ids and false for system ids', () => {
    for (const box of MVP_BOXES) {
      expect(isMVPBoxId(box.id)).toBe(true);
    }
    for (const sid of ACTIVE) {
      expect(isMVPBoxId(sid)).toBe(false);
    }
  });

  it('all MVP edges reference defined boxes', () => {
    const g = buildMVPGraph(CONTRACT);
    const ids = new Set(g.boxes.map((b) => b.id));
    for (const e of g.edges) {
      expect(ids.has(e.from)).toBe(true);
      expect(ids.has(e.to)).toBe(true);
    }
  });
});
