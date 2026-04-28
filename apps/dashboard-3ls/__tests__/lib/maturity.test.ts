/**
 * D3L-MASTER-01 Phase 4 — maturity engine tests.
 *
 * Pins the maturity ladder:
 *   0 Unknown    — no evidence
 *   1 Emerging   — evidence but ≥2 structural signals failing
 *   2 Developing — exactly 1 structural signal failing
 *   3 Stable     — no failing structural; trust caution / not fresh
 *   4 Trusted    — no failing signals, fresh, ready trust state
 *
 * Edge cases: missing contract, stale freshness caps level 4 to 3,
 * spoofed evidence (has_evidence=true but failing signals) keeps low.
 */
import {
  computeMaturityReport,
  STRUCTURAL_SIGNALS,
  type MaturityInputs,
} from '@/lib/maturity';
import type { D3LRegistryContract } from '@/lib/systemRegistry';

const ACTIVE = ['AEX', 'EVL', 'CDE', 'SEL'];

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

function inputs(overrides: Partial<MaturityInputs>): MaturityInputs {
  return {
    contract: CONTRACT,
    evidence: [
      { system_id: 'AEX', has_evidence: true, evidence_count: 100 },
      { system_id: 'EVL', has_evidence: true, evidence_count: 50 },
      { system_id: 'CDE', has_evidence: true, evidence_count: 50 },
      { system_id: 'SEL', has_evidence: true, evidence_count: 50 },
    ],
    trustGap: [
      { system_id: 'AEX', trust_state: 'ready_signal', failing_signals: [] },
      { system_id: 'EVL', trust_state: 'caution_signal', failing_signals: ['missing_lineage'] },
      { system_id: 'CDE', trust_state: 'freeze_signal', failing_signals: ['missing_lineage', 'missing_replay', 'missing_observability'] },
      { system_id: 'SEL', trust_state: 'ready_signal', failing_signals: ['missing_eval', 'missing_replay'] },
    ],
    priorityFresh: true,
    ...overrides,
  };
}

describe('computeMaturityReport', () => {
  it('returns fail-closed when contract is missing', () => {
    const r = computeMaturityReport(inputs({ contract: null }));
    expect(r.status).toBe('fail-closed');
    expect(r.rows).toEqual([]);
  });

  it('all active systems are rows; universe size matches contract', () => {
    const r = computeMaturityReport(inputs({}));
    expect(r.rows.map((row) => row.system_id).sort()).toEqual([...ACTIVE].sort());
    expect(r.maturity_universe_size).toBe(ACTIVE.length);
  });

  it('zero evidence ⇒ level 0 Unknown', () => {
    const r = computeMaturityReport(
      inputs({
        evidence: [{ system_id: 'AEX', has_evidence: false, evidence_count: 0 }],
      }),
    );
    const aex = r.rows.find((row) => row.system_id === 'AEX')!;
    expect(aex.level).toBe(0);
    expect(aex.level_label).toBe('Unknown');
  });

  it('one structural failure ⇒ level 2 Developing', () => {
    const r = computeMaturityReport(inputs({}));
    const evl = r.rows.find((row) => row.system_id === 'EVL')!;
    expect(evl.level).toBe(2);
    expect(evl.failing_structural_signals).toEqual(['missing_lineage']);
  });

  it('three+ structural failures ⇒ level 1 Emerging', () => {
    const r = computeMaturityReport(inputs({}));
    const cde = r.rows.find((row) => row.system_id === 'CDE')!;
    expect(cde.level).toBe(1);
    expect(cde.failing_structural_signals.length).toBeGreaterThanOrEqual(3);
  });

  it('clean evidence + ready trust + fresh ⇒ level 4 Trusted', () => {
    const r = computeMaturityReport(inputs({}));
    const aex = r.rows.find((row) => row.system_id === 'AEX')!;
    expect(aex.level).toBe(4);
    expect(aex.level_label).toBe('Trusted');
  });

  it('clean structural + stale freshness ⇒ caps at level 3 with bookkeeping', () => {
    const r = computeMaturityReport(inputs({ priorityFresh: false }));
    const aex = r.rows.find((row) => row.system_id === 'AEX')!;
    expect(aex.level).toBe(3);
    expect(r.staleness_caps_applied).toBeGreaterThanOrEqual(1);
  });

  it('spoofed evidence (has_evidence true) cannot upgrade past level 1 if structural signals remain', () => {
    const r = computeMaturityReport(inputs({}));
    const sel = r.rows.find((row) => row.system_id === 'SEL')!;
    // Two structural failures (missing_eval + missing_replay) ⇒ level 1.
    expect(sel.level).toBe(1);
  });

  it('key_gap orders structural signals before tests / schema', () => {
    const r = computeMaturityReport(
      inputs({
        trustGap: [
          { system_id: 'AEX', trust_state: 'caution_signal', failing_signals: ['schema_weakness', 'missing_lineage'] },
          ...inputs({}).trustGap.filter((row) => row.system_id !== 'AEX'),
        ],
      }),
    );
    const aex = r.rows.find((row) => row.system_id === 'AEX')!;
    expect(aex.key_gap).toBe('missing_lineage');
  });

  it('level_counts roll-up reflects every row', () => {
    const r = computeMaturityReport(inputs({}));
    const total = Object.values(r.level_counts).reduce((s, n) => s + n, 0);
    expect(total).toBe(ACTIVE.length);
  });

  it('STRUCTURAL_SIGNALS contains the registry-aligned signal taxonomy', () => {
    expect(STRUCTURAL_SIGNALS).toContain('missing_eval');
    expect(STRUCTURAL_SIGNALS).toContain('missing_lineage');
    expect(STRUCTURAL_SIGNALS).toContain('missing_replay');
    expect(STRUCTURAL_SIGNALS).toContain('missing_observability');
    expect(STRUCTURAL_SIGNALS).toContain('missing_control');
    expect(STRUCTURAL_SIGNALS).toContain('missing_enforcement_signal');
  });
});
