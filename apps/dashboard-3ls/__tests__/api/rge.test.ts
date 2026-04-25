/**
 * Tests for the RGE data layer.
 * Route handlers import next/server which requires browser globals not available
 * in jsdom test environment, so we test the underlying signal logic and verify
 * route source files directly.
 */
import path from 'path';
import { deriveRGESignals } from '@/lib/rgeSignals';

const mockCheckpointSummary = {
  artifact_type: 'meta_governance_checkpoint_summary',
  run_id: 'MG-KERNEL-24-01-TEST',
  status: 'PASS',
  checkpoints: [
    {
      umbrella: 'ROADMAP_AND_PROMPT_BURDEN',
      status: 'PASS',
      checkpoint_artifact: 'roadmap_admission_bundle',
      run_id: 'MG-KERNEL-24-01-TEST',
    },
  ],
};

const mockRunSummary = {
  artifact_type: 'meta_governance_run_summary',
  run_id: 'MG-KERNEL-24-01-TEST',
  status: 'PASS',
  manual_residue_steps: 2,
};

const mockLiveTruth = {
  artifact_type: 'live_truth_and_risk_bundle',
  production_dashboard_truth_probe: {
    matches_artifact_truth: true,
    status: 'PASS',
    owner: 'SEL',
  },
  live_deploy_truth_verification: {
    repo_live_divergence: false,
    status: 'PASS',
    owner: 'SEL',
  },
  stability_score: { stability: 0.84, bottleneck_persistence: 0.18, owner: 'PRG' },
};

const mockRegistryCrossCheck = {
  artifact_type: 'meta_governance_registry_cross_check',
  status: 'PASS',
  checks: { '1_each_slice_has_exactly_one_owner': true },
};

const mockLearningDebt = {
  artifact_type: 'learning_and_debt_bundle',
  governance_debt_register: {
    manual_residue_steps: 3,
    prompt_residue_ratio: 0.27,
    non_zero_when_manual_work_remains: true,
    owner: 'PRG',
  },
};

const mockGapAnalysis = {
  artifact_type: 'roadmap_compiler_gap_analysis',
  timestamp: '2026-04-12T000000Z',
  dominant_bottleneck: { id: 'BN-006', statement: 'Orchestration gaps.', evidence: [] },
  highest_risk_trust_gap: { id: 'TG-001', statement: 'Docs-to-runtime drift.', evidence: [] },
  gap_classes: {
    A_foundation: ['gap1'],
    B_governed_operation: ['gap2'],
    C_learning: [],
    D_control: [],
    E_application: [],
    F_hardening: [],
    G_constitutional_alignment: [],
  },
  top_risks: ['BN-006 orchestration drift'],
};

const mockSystemState = {
  artifact_type: 'roadmap_compiler_system_state',
  timestamp: '2026-04-12T000000Z',
  authority_precheck: {
    status: 'pass',
    missing_required_paths: [],
    missing_source_files: [],
    missing_structured_artifacts: [],
    digest_mismatches: [],
    authority_gaps: [],
  },
  domain_state: {
    schemas: { status: 'present_and_governed', evidence: [] },
    eval: { status: 'partial', evidence: [] },
    control: { status: 'present_and_governed', evidence: [] },
    enforcement: { status: 'present_and_governed', evidence: [] },
    replay: { status: 'present_and_governed', evidence: [] },
    trace: { status: 'present_and_governed', evidence: [] },
    certification: { status: 'partial', evidence: [] },
  },
  repo_reality: {
    implemented_modules: [],
    schema_backed_components: [],
    test_backed_systems: [],
    docs_only_systems: [],
    dead_or_unused_surfaces: [],
  },
};

const allArtifacts = {
  checkpointSummary: mockCheckpointSummary,
  runSummary: mockRunSummary,
  liveTruth: mockLiveTruth,
  registryCrossCheck: mockRegistryCrossCheck,
  learningDebt: mockLearningDebt,
  gapAnalysis: mockGapAnalysis,
  systemState: mockSystemState,
};

const noArtifacts = {
  checkpointSummary: null,
  runSummary: null,
  liveTruth: null,
  registryCrossCheck: null,
  learningDebt: null,
  gapAnalysis: null,
  systemState: null,
};

describe('deriveRGESignals — artifact-backed signals', () => {
  it('returns correct mg_kernel_status from checkpoint_summary', () => {
    const signals = deriveRGESignals(allArtifacts);
    expect(signals.mg_kernel_status).toBe('pass');
    expect(signals.mg_kernel_run_id).toBe('MG-KERNEL-24-01-TEST');
  });

  it('returns manual_residue_steps from run_summary', () => {
    const signals = deriveRGESignals(allArtifacts);
    expect(signals.manual_residue_steps).toBe(2);
  });

  it('falls back to learning_and_debt_bundle for manual_residue when run_summary missing', () => {
    const signals = deriveRGESignals({ ...allArtifacts, runSummary: null });
    expect(signals.manual_residue_steps).toBe(3); // from learningDebt
    expect(signals.warnings).toContain(
      'manual_residue_steps sourced from learning_and_debt_bundle (run_summary.json not found)'
    );
  });

  it('returns dashboard_truth_status from live_truth bundle', () => {
    const signals = deriveRGESignals(allArtifacts);
    expect(signals.dashboard_truth_status).toBe('verified');
  });

  it('returns registry_alignment_status from registry_cross_check', () => {
    const signals = deriveRGESignals(allArtifacts);
    expect(signals.registry_alignment_status).toBe('aligned');
  });

  it('derives active_drift_legs from BN-006 dominant bottleneck', () => {
    const signals = deriveRGESignals(allArtifacts);
    expect(signals.active_drift_legs).toContain('EVL');
  });

  it('derives entropy_vectors from gap_classes', () => {
    const signals = deriveRGESignals(allArtifacts);
    expect(signals.entropy_vectors.foundation_gaps).toBe('warn');
    expect(signals.entropy_vectors.learning_gaps).toBe('clean');
  });

  it('sets rge_max_autonomy to warn_gated when drift legs present', () => {
    const signals = deriveRGESignals(allArtifacts);
    expect(signals.rge_max_autonomy).toBe('warn_gated');
  });

  it('sets rge_can_operate true when mg_kernel passes and registry aligned', () => {
    const signals = deriveRGESignals(allArtifacts);
    expect(signals.rge_can_operate).toBe(true);
  });

  it('returns no warnings when all artifacts present', () => {
    const signals = deriveRGESignals(allArtifacts);
    // Only possible warning is the run_summary fallback note — should not be triggered
    const unexpectedWarnings = signals.warnings.filter(
      (w) => !w.includes('sourced from learning_and_debt_bundle')
    );
    expect(unexpectedWarnings).toHaveLength(0);
  });
});

describe('deriveRGESignals — stub_fallback when artifacts missing', () => {
  it('returns unknown for all values when no artifacts provided', () => {
    const signals = deriveRGESignals(noArtifacts);
    expect(signals.mg_kernel_status).toBe('unknown');
    expect(signals.manual_residue_steps).toBe('unknown');
    expect(signals.dashboard_truth_status).toBe('unknown');
    expect(signals.registry_alignment_status).toBe('unknown');
    expect(signals.context_maturity_level).toBe('unknown');
    expect(signals.wave_status).toBe('unknown');
  });

  it('emits a warning for each missing artifact type', () => {
    const signals = deriveRGESignals(noArtifacts);
    expect(signals.warnings).toContain(
      'mg_kernel status unavailable: checkpoint_summary.json not found'
    );
    expect(signals.warnings).toContain(
      'dashboard_truth_status unavailable: live_truth_and_risk_bundle.json not found'
    );
    expect(signals.warnings).toContain(
      'registry_alignment_status unavailable: registry_cross_check.json not found'
    );
    expect(signals.warnings).toContain(
      'entropy_vectors unavailable: gap_analysis.json not found'
    );
    expect(signals.warnings).toContain(
      'context_maturity_level and wave_status unavailable: system_state.json not found'
    );
  });

  it('sets rge_can_operate false when mg_kernel unknown', () => {
    const signals = deriveRGESignals(noArtifacts);
    expect(signals.rge_can_operate).toBe(false);
  });
});

describe('RGE route source — no LIVE claims', () => {
  const routes = [
    'app/api/rge/analysis/route.ts',
    'app/api/rge/roadmap/route.ts',
    'app/api/rge/proposals/route.ts',
  ];

  for (const route of routes) {
    it(`${route} contains no hardcoded LIVE record IDs`, () => {
      const source = require('fs').readFileSync(
        path.resolve(__dirname, '../../', route),
        'utf-8'
      );
      expect(source).not.toMatch(/ANA-LIVE/);
      expect(source).not.toMatch(/RRM-LIVE/);
      expect(source).not.toMatch(/run-\d{4}-\d{2}-\d{2}-live/);
      expect(source).not.toMatch(/trace-live/);
    });

    it(`${route} includes stub_fallback data_source path`, () => {
      const source = require('fs').readFileSync(
        path.resolve(__dirname, '../../', route),
        'utf-8'
      );
      expect(source).toContain('stub_fallback');
    });

    it(`${route} includes source_artifacts_used in response`, () => {
      const source = require('fs').readFileSync(
        path.resolve(__dirname, '../../', route),
        'utf-8'
      );
      expect(source).toContain('source_artifacts_used');
    });
  }
});
