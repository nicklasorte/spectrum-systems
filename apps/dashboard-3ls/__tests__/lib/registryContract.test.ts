/**
 * D3L-REGISTRY-01 — Registry contract parser tests.
 *
 * Pins the no-invented-systems guarantee: only registry-active system_ids
 * may render as graph nodes. Roadmap labels (H01, RFX, MET, METS),
 * red-team report IDs (D3L-FIX-*, TLS-BND-*), prompt labels, and bundle
 * IDs MUST be rejected.
 */
import {
  EXPECTED_ACTIVE_SYSTEMS_FIXTURE,
  FORBIDDEN_UNKNOWN_NODE_EXAMPLES,
  isAllowedActiveNode,
  isKnownRegistrySystem,
  parseRegistryContractFromArtifact,
  partitionCandidatesByRegistry,
  validateGraphAgainstContract,
} from '@/lib/registryContract';

const FAKE_RAW = {
  active_systems: EXPECTED_ACTIVE_SYSTEMS_FIXTURE.map((id) => ({
    system_id: id,
    status: 'active',
    purpose: `${id} purpose`,
    upstream: [],
    downstream: [],
  })),
  future_systems: [
    { system_id: 'ABX', status: 'future', purpose: 'placeholder', upstream: [], downstream: [] },
    { system_id: 'DBB', status: 'future', purpose: 'placeholder', upstream: [], downstream: [] },
  ],
  merged_or_demoted: [
    { system_id: 'HNX', status: 'demoted', purpose: 'demoted', upstream: [], downstream: [] },
    { system_id: 'SUP', status: 'merged', purpose: 'merged', upstream: [], downstream: [] },
  ],
  canonical_loop: ['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL'],
  canonical_overlays: ['REP', 'LIN', 'OBS', 'SLO'],
};

describe('parseRegistryContractFromArtifact', () => {
  it('returns empty contract when artifact is missing', () => {
    const c = parseRegistryContractFromArtifact(null);
    expect(c.allowed_active_node_ids).toEqual([]);
    expect(c.active_systems).toEqual([]);
    expect(c.graph_rows.length).toBeGreaterThan(0);
    expect(c.edge_classes.length).toBeGreaterThan(0);
    expect(c.validation_rules.length).toBeGreaterThan(0);
  });

  it('parses active / future / demoted systems from the registry artifact', () => {
    const c = parseRegistryContractFromArtifact(FAKE_RAW);
    expect(c.allowed_active_node_ids).toEqual(Array.from(EXPECTED_ACTIVE_SYSTEMS_FIXTURE));
    expect(c.allowed_future_node_ids).toEqual(['ABX', 'DBB']);
    expect(c.demoted_or_deprecated_ids).toEqual(['HNX', 'SUP']);
  });

  it('parses canonical_loop and canonical_overlays', () => {
    const c = parseRegistryContractFromArtifact(FAKE_RAW);
    expect(c.canonical_loop).toEqual(['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL']);
    expect(c.canonical_overlays).toEqual(['REP', 'LIN', 'OBS', 'SLO']);
  });

  it('declares forbidden non-system labels in the contract', () => {
    const c = parseRegistryContractFromArtifact(FAKE_RAW);
    for (const example of FORBIDDEN_UNKNOWN_NODE_EXAMPLES) {
      expect(c.forbidden_unknown_node_examples).toContain(example);
    }
  });
});

describe('isAllowedActiveNode / isKnownRegistrySystem', () => {
  const c = parseRegistryContractFromArtifact(FAKE_RAW);

  it('accepts every registry-active system', () => {
    for (const id of EXPECTED_ACTIVE_SYSTEMS_FIXTURE) {
      expect(isAllowedActiveNode(c, id)).toBe(true);
    }
  });

  it('rejects roadmap / candidate / prompt labels', () => {
    for (const forbidden of FORBIDDEN_UNKNOWN_NODE_EXAMPLES) {
      expect(isAllowedActiveNode(c, forbidden)).toBe(false);
    }
  });

  it('isKnownRegistrySystem is true for active, future, demoted', () => {
    expect(isKnownRegistrySystem(c, 'AEX')).toBe(true);
    expect(isKnownRegistrySystem(c, 'ABX')).toBe(true);
    expect(isKnownRegistrySystem(c, 'HNX')).toBe(true);
    expect(isKnownRegistrySystem(c, 'NOT_A_SYSTEM')).toBe(false);
  });
});

describe('validateGraphAgainstContract', () => {
  const c = parseRegistryContractFromArtifact(FAKE_RAW);

  it('accepts a graph containing only registry-active nodes', () => {
    const result = validateGraphAgainstContract(c, {
      nodes: [{ system_id: 'AEX' }, { system_id: 'PQX' }],
      edges: [{ from: 'AEX', to: 'PQX' }],
    });
    expect(result.ok).toBe(true);
    expect(result.findings).toEqual([]);
  });

  it('rejects unknown node IDs (e.g. H01)', () => {
    const result = validateGraphAgainstContract(c, {
      nodes: [{ system_id: 'AEX' }, { system_id: 'H01' }],
      edges: [],
    });
    expect(result.ok).toBe(false);
    expect(result.findings.some((f) => f.rule_id === 'reject_unknown_node' && f.offending.includes('H01'))).toBe(true);
  });

  it('rejects demoted system in default active graph', () => {
    const result = validateGraphAgainstContract(c, {
      nodes: [{ system_id: 'HNX' }],
      edges: [],
    });
    expect(result.ok).toBe(false);
    expect(result.findings.some((f) => f.rule_id === 'reject_demoted_in_default')).toBe(true);
  });

  it('rejects future placeholder in default active graph', () => {
    const result = validateGraphAgainstContract(c, {
      nodes: [{ system_id: 'ABX' }],
      edges: [],
    });
    expect(result.ok).toBe(false);
    expect(result.findings.some((f) => f.rule_id === 'reject_future_in_default')).toBe(true);
  });

  it('allows future placeholder when allowFutureLayer is enabled', () => {
    const result = validateGraphAgainstContract(c, {
      nodes: [{ system_id: 'ABX' }],
      edges: [],
    }, { allowFutureLayer: true });
    expect(result.ok).toBe(true);
  });

  it('rejects edges whose endpoint is not a registry node', () => {
    const result = validateGraphAgainstContract(c, {
      nodes: [{ system_id: 'AEX' }],
      edges: [{ from: 'AEX', to: 'TLS-BND-01' }],
    });
    expect(result.ok).toBe(false);
    expect(result.findings.some((f) => f.rule_id === 'reject_unknown_edge')).toBe(true);
  });
});

describe('partitionCandidatesByRegistry', () => {
  const c = parseRegistryContractFromArtifact(FAKE_RAW);

  it('separates registry-backed from non-registry rows', () => {
    const rows = [
      { system_id: 'EVL', meta: 1 },
      { system_id: 'H01', meta: 2 },
      { system_id: 'TPA', meta: 3 },
      { system_id: 'RFX', meta: 4 },
    ];
    const { registry_backed, non_registry } = partitionCandidatesByRegistry(c, rows);
    expect(registry_backed.map((r) => r.system_id)).toEqual(['EVL', 'TPA']);
    expect(non_registry.map((r) => r.system_id)).toEqual(['H01', 'RFX']);
  });
});
