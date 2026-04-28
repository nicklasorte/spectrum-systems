/**
 * D3L-MASTER-01 Phase 0 — registry-aligned ranking helper tests.
 *
 * Pins the contract that:
 *   - active_system_ids ⇒ ranking_universe ⇒ maturity_universe
 *   - excluded ids (future / deprecated / merged) MUST be rejected
 *   - forbidden node examples (H01, TLS-BND-*, D3L-FIX-*) MUST be rejected
 *   - missing contract ⇒ everything is rejected (fail-closed)
 */
import {
  admitAgainstRegistry,
  filterRowsByRanking,
  isForbiddenNodeLabel,
  isInMaturityUniverse,
  isInRankingUniverse,
  type D3LRegistryContract,
} from '@/lib/systemRegistry';

const ACTIVE = ['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL'];
const FUTURE = ['ABX', 'DBB'];
const DEMOTED = ['HNX', 'SUP'];

const CONTRACT: D3LRegistryContract = {
  artifact_type: 'd3l_registry_contract',
  phase: 'D3L-MASTER-01',
  schema_version: 'd3l-master-01.v1',
  source_artifact: 'artifacts/tls/system_registry_dependency_graph.json',
  active_system_ids: ACTIVE,
  future_system_ids: FUTURE,
  deprecated_or_merged_system_ids: DEMOTED,
  excluded_ids: [...FUTURE, ...DEMOTED],
  ranking_universe: ACTIVE,
  maturity_universe: ACTIVE,
  forbidden_node_examples: ['H01', 'TLS-BND-01', 'D3L-FIX-01'],
  rules: [],
};

describe('admitAgainstRegistry', () => {
  it('admits only active system ids', () => {
    const r = admitAgainstRegistry(CONTRACT, ['AEX', 'EVL', 'CDE']);
    expect(r.admitted).toEqual(['AEX', 'EVL', 'CDE']);
    expect(r.rejected_excluded).toEqual([]);
    expect(r.rejected_forbidden).toEqual([]);
    expect(r.rejected_unknown).toEqual([]);
  });

  it('rejects future system ids into rejected_excluded', () => {
    const r = admitAgainstRegistry(CONTRACT, ['AEX', 'ABX']);
    expect(r.admitted).toEqual(['AEX']);
    expect(r.rejected_excluded).toEqual(['ABX']);
  });

  it('rejects deprecated/merged system ids into rejected_excluded', () => {
    const r = admitAgainstRegistry(CONTRACT, ['AEX', 'HNX', 'SUP']);
    expect(r.admitted).toEqual(['AEX']);
    expect(r.rejected_excluded).toEqual(['HNX', 'SUP']);
  });

  it('rejects forbidden node labels (H01, TLS-BND-*, D3L-FIX-*)', () => {
    const r = admitAgainstRegistry(CONTRACT, ['EVL', 'H01', 'TLS-BND-01', 'D3L-FIX-01']);
    expect(r.admitted).toEqual(['EVL']);
    expect(r.rejected_forbidden).toEqual(['H01', 'TLS-BND-01', 'D3L-FIX-01']);
  });

  it('classifies unknown ids separately from excluded/forbidden', () => {
    const r = admitAgainstRegistry(CONTRACT, ['UNKNOWN_LABEL']);
    expect(r.rejected_unknown).toEqual(['UNKNOWN_LABEL']);
    expect(r.rejected_excluded).toEqual([]);
    expect(r.rejected_forbidden).toEqual([]);
  });

  it('fails closed when the contract is missing', () => {
    const r = admitAgainstRegistry(null, ['AEX', 'EVL']);
    expect(r.admitted).toEqual([]);
    expect(r.rejected_unknown).toEqual(['AEX', 'EVL']);
  });

  it('preserves first-seen order and de-duplicates', () => {
    const r = admitAgainstRegistry(CONTRACT, ['AEX', 'EVL', 'AEX']);
    expect(r.admitted).toEqual(['AEX', 'EVL']);
  });
});

describe('isInRankingUniverse / isInMaturityUniverse / isForbiddenNodeLabel', () => {
  it('treats ranking_universe and maturity_universe as registry-active only', () => {
    for (const id of ACTIVE) {
      expect(isInRankingUniverse(CONTRACT, id)).toBe(true);
      expect(isInMaturityUniverse(CONTRACT, id)).toBe(true);
    }
    for (const id of [...FUTURE, ...DEMOTED]) {
      expect(isInRankingUniverse(CONTRACT, id)).toBe(false);
      expect(isInMaturityUniverse(CONTRACT, id)).toBe(false);
    }
  });

  it('flags forbidden labels regardless of any other state', () => {
    expect(isForbiddenNodeLabel(CONTRACT, 'H01')).toBe(true);
    expect(isForbiddenNodeLabel(CONTRACT, 'TLS-BND-01')).toBe(true);
    expect(isForbiddenNodeLabel(CONTRACT, 'AEX')).toBe(false);
  });

  it('returns false for everything when contract is missing (fail-closed)', () => {
    expect(isInRankingUniverse(null, 'AEX')).toBe(false);
    expect(isInMaturityUniverse(null, 'AEX')).toBe(false);
    expect(isForbiddenNodeLabel(null, 'H01')).toBe(false);
  });
});

describe('filterRowsByRanking', () => {
  it('keeps only registry-active rows and reports rejections', () => {
    const rows = [
      { system_id: 'AEX', detail: 'a' },
      { system_id: 'H01', detail: 'b' },
      { system_id: 'ABX', detail: 'c' },
      { system_id: 'EVL', detail: 'd' },
    ];
    const { admitted, admission } = filterRowsByRanking(CONTRACT, rows);
    expect(admitted.map((r) => r.system_id)).toEqual(['AEX', 'EVL']);
    expect(admission.rejected_forbidden).toEqual(['H01']);
    expect(admission.rejected_excluded).toEqual(['ABX']);
  });
});
