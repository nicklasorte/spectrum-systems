import fs from 'fs';
import path from 'path';

const appRoot = path.resolve(__dirname, '../../');
const intelligenceSrc = fs.readFileSync(
  path.resolve(appRoot, 'app/api/intelligence/route.ts'),
  'utf-8',
);

describe('MET-34-47 — /api/intelligence compact blocks', () => {
  it('exposes all new compact blocks', () => {
    expect(intelligenceSrc).toContain('owner_read_observations:');
    expect(intelligenceSrc).toContain('materialization_observation_mapper:');
    expect(intelligenceSrc).toContain('comparable_case_qualification_gate:');
    expect(intelligenceSrc).toContain('trend_ready_case_pack:');
    expect(intelligenceSrc).toContain('override_evidence_source_adapter:');
    expect(intelligenceSrc).toContain('fold_candidate_proof_check:');
    expect(intelligenceSrc).toContain('operator_debuggability_drill:');
    expect(intelligenceSrc).toContain('generated_artifact_policy_handoff:');
  });

  it('new blocks preserve envelope fields', () => {
    [
      'ownerReadObservationsBlock',
      'materializationObservationMapperBlock',
      'comparableCaseQualificationGateBlock',
      'trendReadyCasePackBlock',
      'overrideEvidenceSourceAdapterBlock',
      'foldCandidateProofCheckBlock',
      'operatorDebuggabilityDrillBlock',
      'generatedArtifactPolicyHandoffBlock',
    ].forEach((blockName) => {
      const idx = intelligenceSrc.indexOf(`const ${blockName}`);
      expect(idx).toBeGreaterThan(-1);
      const block = intelligenceSrc.slice(idx, idx + 3000);
      expect(block).toContain('data_source');
      expect(block).toContain('source_artifacts_used');
      expect(block).toContain('warnings');
    });
  });

  it('degrades missing artifacts to unknown not zero', () => {
    expect(intelligenceSrc).toContain("override_evidence_count: 'unknown'");
    expect(intelligenceSrc).toContain("data_source: 'unknown'");
  });

  it('keeps sourced filtering guard for recommendations', () => {
    expect(intelligenceSrc).toContain('filteredCandidateItems');
    expect(intelligenceSrc).toContain('filteredEvalCandidates');
    expect(intelligenceSrc).toContain('filteredPolicySignals');
  });
});
