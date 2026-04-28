import fs from 'fs';
import path from 'path';

const appRoot = path.resolve(__dirname, '../../');
const intelligenceSrc = fs.readFileSync(
  path.resolve(appRoot, 'app/api/intelligence/route.ts'),
  'utf-8',
);

describe('MET-19-33 — /api/intelligence wires new MET fields', () => {
  it('exposes candidate_closure, met_artifact_dependency_index, trend_frequency_honesty_gate', () => {
    expect(intelligenceSrc).toContain('candidate_closure:');
    expect(intelligenceSrc).toContain('met_artifact_dependency_index:');
    expect(intelligenceSrc).toContain('trend_frequency_honesty_gate:');
  });

  it('exposes evl_handoff_observations, override_evidence_intake, debug_explanation_index', () => {
    expect(intelligenceSrc).toContain('evl_handoff_observations:');
    expect(intelligenceSrc).toContain('override_evidence_intake:');
    expect(intelligenceSrc).toContain('debug_explanation_index:');
  });

  it('exposes met_generated_artifact_classification', () => {
    expect(intelligenceSrc).toContain('met_generated_artifact_classification:');
  });

  it('every new block surfaces data_source, source_artifacts_used, warnings', () => {
    [
      'candidateClosureBlock',
      'metArtifactDependencyIndexBlock',
      'trendFrequencyHonestyGateBlock',
      'evlHandoffObservationsBlock',
      'overrideEvidenceIntakeBlock',
      'debugExplanationIndexBlock',
      'metGeneratedArtifactClassificationBlock',
    ].forEach((blockName) => {
      const idx = intelligenceSrc.indexOf(`const ${blockName}`);
      expect(idx).toBeGreaterThan(-1);
      const block = intelligenceSrc.slice(idx, idx + 4000);
      expect(block).toContain('data_source');
      expect(block).toContain('source_artifacts_used');
      expect(block).toContain('warnings');
    });
  });

  it('override_evidence_count never silently substitutes 0; degrades to unknown', () => {
    const idx = intelligenceSrc.indexOf('const overrideEvidenceIntakeBlock');
    const block = intelligenceSrc.slice(idx, idx + 3000);
    expect(block).toMatch(
      /override_evidence_count: overrideEvidenceIntake\.override_evidence_count \?\? 'unknown'/,
    );
    expect(block).toMatch(/override_evidence_count: 'unknown'/);
  });

  it('candidate closure counts degrade to unknown when artifact missing', () => {
    const idx = intelligenceSrc.indexOf('const candidateClosureBlock');
    const block = intelligenceSrc.slice(idx, idx + 3000);
    expect(block).toMatch(/candidate_item_count: 'unknown'/);
    expect(block).toMatch(/stale_candidate_signal_count: 'unknown'/);
  });

  it('trend honesty gate degrades to unknown trend_state and frequency_state', () => {
    const idx = intelligenceSrc.indexOf('const trendFrequencyHonestyGateBlock');
    const block = intelligenceSrc.slice(idx, idx + 3000);
    expect(block).toMatch(/trend_state: 'unknown'/);
    expect(block).toMatch(/frequency_state: 'unknown'/);
    expect(block).toMatch(/cases_needed: 'unknown'/);
  });

  it('filters out unsourced candidate, handoff, and explanation entries', () => {
    expect(intelligenceSrc).toContain('filteredCandidateItems');
    expect(intelligenceSrc).toContain('filteredHandoffItems');
    expect(intelligenceSrc).toContain('filteredExplanationEntries');
  });

  it('does not name MET as a decision/enforcement/promotion authority', () => {
    expect(intelligenceSrc).not.toContain('candidate_closure_decision');
    expect(intelligenceSrc).not.toContain('candidate_closure_certified');
    expect(intelligenceSrc).not.toContain('handoff_promoted');
    expect(intelligenceSrc).not.toContain('handoff_enforced');
  });
});
