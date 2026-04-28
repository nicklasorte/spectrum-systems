/**
 * D3L-REGISTRY-01 — Failure taxonomy mapping tests.
 *
 * The taxonomy is artifact-driven. Empty signal lists must map to 'none',
 * unrecognized signals must map to 'unknown', never a guess.
 */
import {
  FAILURE_TAXONOMY_TABLE,
  mapSignalsToTaxonomy,
  taxonomyLabel,
} from '@/lib/failureTaxonomy';

describe('mapSignalsToTaxonomy', () => {
  it('returns none when no signals present', () => {
    expect(mapSignalsToTaxonomy([])).toBe('none');
  });

  it('returns unknown when signals do not match the taxonomy', () => {
    expect(mapSignalsToTaxonomy(['totally_made_up_signal'])).toBe('unknown');
  });

  it('maps missing_artifact signal to missing_artifact taxonomy', () => {
    expect(mapSignalsToTaxonomy(['missing_artifact'])).toBe('missing_artifact');
  });

  it('maps missing_eval signal to missing_eval taxonomy', () => {
    expect(mapSignalsToTaxonomy(['missing_eval'])).toBe('missing_eval');
  });

  it('maps schema signals to schema_violation taxonomy', () => {
    expect(mapSignalsToTaxonomy(['schema_weakness'])).toBe('schema_violation');
    expect(mapSignalsToTaxonomy(['shape_mismatch'])).toBe('schema_violation');
  });

  it('maps observability signals to trace_missing taxonomy', () => {
    expect(mapSignalsToTaxonomy(['missing_observability'])).toBe('trace_missing');
  });

  it('maps replay signals to replay_mismatch taxonomy', () => {
    expect(mapSignalsToTaxonomy(['missing_replay'])).toBe('replay_mismatch');
  });

  it('maps policy / control signals to policy_mismatch taxonomy', () => {
    expect(mapSignalsToTaxonomy(['missing_control'])).toBe('policy_mismatch');
    expect(mapSignalsToTaxonomy(['missing_enforcement_signal'])).toBe('policy_mismatch');
  });

  // D3L-DATA-REGISTRY-01: stale and registry-mismatch taxonomies.
  it('maps stale artifact signals to stale_artifact taxonomy', () => {
    expect(mapSignalsToTaxonomy(['older_than_threshold'])).toBe('stale_artifact');
    expect(mapSignalsToTaxonomy(['generated_at_missing'])).toBe('stale_artifact');
    expect(mapSignalsToTaxonomy(['generated_at_in_future'])).toBe('stale_artifact');
  });

  it('maps registry-rejection signals to registry_mismatch taxonomy', () => {
    expect(mapSignalsToTaxonomy(['registry_contract_rejected_nodes'])).toBe('registry_mismatch');
    expect(mapSignalsToTaxonomy(['reject_unknown_node'])).toBe('registry_mismatch');
    expect(mapSignalsToTaxonomy(['reject_unknown_edge'])).toBe('registry_mismatch');
  });
});

describe('taxonomyLabel', () => {
  it('produces a human-readable label for every taxonomy', () => {
    for (const entry of FAILURE_TAXONOMY_TABLE) {
      expect(taxonomyLabel(entry.taxonomy)).not.toBe('');
    }
    expect(taxonomyLabel('unknown')).toBe('unknown');
    expect(taxonomyLabel('none')).toBe('no failure');
  });
});
