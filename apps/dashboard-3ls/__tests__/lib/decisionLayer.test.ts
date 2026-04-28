/**
 * D3L-REGISTRY-01 — Decision Layer projection tests.
 *
 * The decision layer is a view over the registry, NOT a new system or
 * graph. Filtering by an empty allowlist must produce no groups; filtering
 * by an active set must hide systems that are not registry-active.
 */
import {
  DECISION_LAYER_GROUPS,
  decisionLayerForSystem,
  filterDecisionLayersByRegistry,
} from '@/lib/decisionLayer';

describe('DECISION_LAYER_GROUPS', () => {
  it('uses only registry-active system_ids in every group', () => {
    const allowed = new Set([
      'AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL',
      'REP', 'LIN', 'OBS', 'SLO',
      'CTX', 'PRM', 'POL', 'TLC', 'RIL', 'FRE',
      'RAX', 'RSM', 'CAP', 'SEC',
      'JDX', 'JSX', 'PRA', 'GOV', 'MAP', 'HOP',
    ]);
    for (const group of DECISION_LAYER_GROUPS) {
      for (const systemId of group.systems) {
        expect(allowed.has(systemId)).toBe(true);
      }
    }
  });

  it('places CDE in control and SEL in enforcement (no role bleed)', () => {
    expect(decisionLayerForSystem('CDE')).toBe('control');
    expect(decisionLayerForSystem('SEL')).toBe('enforcement');
  });

  it('returns null for non-registry labels (e.g. H01, TLS-BND-*)', () => {
    expect(decisionLayerForSystem('H01')).toBeNull();
    expect(decisionLayerForSystem('TLS-BND-01')).toBeNull();
  });
});

describe('filterDecisionLayersByRegistry', () => {
  it('drops groups whose every system is missing from the allowlist', () => {
    const groups = filterDecisionLayersByRegistry(['AEX', 'PQX']);
    expect(groups.find((g) => g.layer === 'signal')?.systems).toEqual(['PQX']);
    expect(groups.find((g) => g.layer === 'enforcement')).toBeUndefined();
  });

  it('returns empty array when allowlist is empty', () => {
    expect(filterDecisionLayersByRegistry([])).toEqual([]);
  });
});
