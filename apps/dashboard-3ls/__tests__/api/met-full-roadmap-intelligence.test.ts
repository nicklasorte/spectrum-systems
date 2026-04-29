import fs from 'fs';
import path from 'path';

const appRoot = path.resolve(__dirname, '../../');
const repoRoot = path.resolve(appRoot, '../..');
const intelligenceSrc = fs.readFileSync(
  path.resolve(appRoot, 'app/api/intelligence/route.ts'),
  'utf-8',
);
const pageSrc = fs.readFileSync(path.resolve(appRoot, 'app/page.tsx'), 'utf-8');

const REQUIRED_API_BLOCKS = [
  'met_registry_status:',
  'met_cockpit:',
  'top_next_inputs:',
  'owner_handoff:',
  'stale_candidate_pressure:',
  'trend_readiness:',
  'override_evidence:',
  'fold_safety:',
  'outcome_attribution:',
  'recommendation_accuracy:',
  'calibration_drift:',
  'cross_run_consistency:',
  'error_budget_observation:',
  'next_best_slice:',
  'counterfactuals:',
  'recurring_failures:',
  'debug_readiness:',
  'signal_integrity:',
];

const REQUIRED_DASHBOARD_TEST_IDS = [
  'met-cockpit-section',
  'met-cockpit-card',
  'met-authority',
  'met-registry-status',
  'met-top-next-inputs-section',
  'met-owner-handoff-section',
  'met-outcome-attribution-section',
  'met-outcome-attribution-list',
  'met-calibration-drift-list',
  'met-recurring-failures-list',
  'met-signal-integrity-list',
];

describe('MET-FULL-ROADMAP — /api/intelligence cockpit blocks', () => {
  it('exposes every MET cockpit block', () => {
    for (const block of REQUIRED_API_BLOCKS) {
      expect(intelligenceSrc).toContain(block);
    }
  });

  it('every MET cockpit artifact path is loaded under ARTIFACT_PATHS', () => {
    const artifactRefs = [
      'stale_candidate_pressure_record.json',
      'outcome_attribution_record.json',
      'failure_reduction_signal_record.json',
      'recommendation_accuracy_record.json',
      'calibration_drift_record.json',
      'signal_confidence_record.json',
      'cross_run_consistency_record.json',
      'divergence_detection_record.json',
      'met_error_budget_observation_record.json',
      'met_freeze_recommendation_signal_record.json',
      'next_best_slice_recommendation_record.json',
      'pqx_candidate_action_bundle_record.json',
      'counterfactual_reconstruction_record.json',
      'earlier_intervention_signal_record.json',
      'recurring_failure_cluster_record.json',
      'recurrence_severity_signal_record.json',
      'time_to_explain_record.json',
      'debug_readiness_sla_record.json',
      'metric_gaming_detection_record.json',
      'misleading_signal_detection_record.json',
      'signal_integrity_check_record.json',
    ];
    for (const ref of artifactRefs) {
      expect(intelligenceSrc).toContain(ref);
    }
  });

  it('blocks degrade to unknown when artifact missing — no zero substitution', () => {
    expect(intelligenceSrc).toContain("data_source: 'unknown'");
    expect(intelligenceSrc).toContain('block reported as unknown');
  });

  it('met_registry_status declares NONE authority', () => {
    expect(intelligenceSrc).toContain("authority: 'NONE'");
  });

  it('met_registry_status forbids authority ownership', () => {
    expect(intelligenceSrc).toContain('decision_ownership');
    expect(intelligenceSrc).toContain('enforcement_ownership');
    expect(intelligenceSrc).toContain('certification_ownership');
    expect(intelligenceSrc).toContain('promotion_ownership');
    expect(intelligenceSrc).toContain('execution_ownership');
    expect(intelligenceSrc).toContain('admission_ownership');
  });

  it('every MET artifact carries failure_prevented and signal_improved', () => {
    const required = [
      'stale_candidate_pressure_record.json',
      'outcome_attribution_record.json',
      'recommendation_accuracy_record.json',
      'calibration_drift_record.json',
      'signal_confidence_record.json',
      'cross_run_consistency_record.json',
      'met_error_budget_observation_record.json',
      'next_best_slice_recommendation_record.json',
      'counterfactual_reconstruction_record.json',
      'recurring_failure_cluster_record.json',
      'time_to_explain_record.json',
      'debug_readiness_sla_record.json',
      'signal_integrity_check_record.json',
    ];
    for (const name of required) {
      const data = JSON.parse(
        fs.readFileSync(
          path.resolve(repoRoot, 'artifacts/dashboard_metrics', name),
          'utf-8',
        ),
      );
      expect(typeof data.failure_prevented).toBe('string');
      expect(typeof data.signal_improved).toBe('string');
      expect(Array.isArray(data.source_artifacts_used)).toBe(true);
      expect(data.source_artifacts_used.length).toBeGreaterThan(0);
      expect(data.owner_system).toBe('MET');
    }
  });
});

describe('MET-FULL-ROADMAP — dashboard MET Cockpit', () => {
  it('renders all required MET Cockpit data-testids', () => {
    for (const tid of REQUIRED_DASHBOARD_TEST_IDS) {
      expect(pageSrc).toContain(tid);
    }
  });

  it('does not surface an Execute button on MET Cockpit', () => {
    const cockpitStart = pageSrc.indexOf('met-cockpit-section');
    const cockpitEnd = pageSrc.indexOf('met-outcome-attribution-section');
    const cockpitSlice = pageSrc.slice(cockpitStart, cockpitEnd);
    expect(cockpitSlice).not.toMatch(/<button[^>]*>\s*Execute/i);
  });

  it('compact item maximum is enforced via slice(0, MET_COMPACT_ITEM_MAX) or slice(0, 5) or slice(0, 3)', () => {
    expect(pageSrc).toMatch(/slice\(0,\s*MET_COMPACT_ITEM_MAX\)/);
  });
});

describe('MET-FULL-ROADMAP — cockpit summary preserves unknown', () => {
  it('top_next_input_count and owner_handoff_queue_count surface unknown when source artifact is missing', () => {
    // Both counts are guarded with a presence check on the underlying source
    // artifact (nextBestSliceRecommendation / ownerReadObservationLedger);
    // when null they degrade to 'unknown' rather than 0.
    expect(intelligenceSrc).toMatch(
      /topNextInputCount[\s\S]*?nextBestSliceRecommendation[\s\S]*?'unknown'/,
    );
    expect(intelligenceSrc).toMatch(
      /ownerHandoffQueueCount[\s\S]*?ownerReadObservationLedger[\s\S]*?'unknown'/,
    );
    expect(intelligenceSrc).toContain('top_next_input_count: topNextInputCount');
    expect(intelligenceSrc).toContain('owner_handoff_queue_count: ownerHandoffQueueCount');
  });

  it('confidence_calibration_state is derived from calibration_buckets content, not file presence', () => {
    // The state must aggregate over actual bucket drift_states so it advances
    // with artifact content. A boolean file-presence ternary is forbidden.
    expect(intelligenceSrc).toContain('calibrationBucketStates');
    expect(intelligenceSrc).toMatch(/calibrationDrift\?\.calibration_buckets/);
    expect(intelligenceSrc).not.toMatch(
      /confidence_calibration_state:\s*calibrationDrift\s*\?\s*'insufficient_cases'/,
    );
  });

  it('recurrence_state is derived from clusters content, not file presence', () => {
    expect(intelligenceSrc).toContain('recurrenceClusterStates');
    expect(intelligenceSrc).toMatch(/recurringFailureCluster\?\.clusters/);
    expect(intelligenceSrc).not.toMatch(
      /recurrence_state:\s*recurringFailureCluster\s*\?\s*'insufficient_cases'/,
    );
  });
});

describe('MET-FULL-ROADMAP — anti-gaming and integrity', () => {
  it('signal_integrity_check_record aggregates flagged observations', () => {
    const data = JSON.parse(
      fs.readFileSync(
        path.resolve(
          repoRoot,
          'artifacts/dashboard_metrics/signal_integrity_check_record.json',
        ),
        'utf-8',
      ),
    );
    expect(data.integrity_summary).toBeDefined();
    expect(Array.isArray(data.integrity_checks)).toBe(true);
    expect(data.integrity_checks.length).toBeGreaterThan(0);
  });

  it('outcome attribution requires before/after evidence — insufficient_evidence is allowed', () => {
    const data = JSON.parse(
      fs.readFileSync(
        path.resolve(
          repoRoot,
          'artifacts/dashboard_metrics/outcome_attribution_record.json',
        ),
        'utf-8',
      ),
    );
    for (const entry of data.outcome_entries) {
      const status = entry.status;
      expect(['insufficient_evidence', 'partial', 'observed', 'unknown']).toContain(status);
      if (status === 'observed') {
        expect(entry.before_signal.evidence_refs.length).toBeGreaterThan(0);
        expect(entry.after_signal.evidence_refs.length).toBeGreaterThan(0);
      }
    }
  });

  it('recurrence requires multiple comparable cases — insufficient_cases is exposed', () => {
    const data = JSON.parse(
      fs.readFileSync(
        path.resolve(
          repoRoot,
          'artifacts/dashboard_metrics/recurring_failure_cluster_record.json',
        ),
        'utf-8',
      ),
    );
    expect(data.minimum_comparable_cases_for_recurrence).toBeGreaterThanOrEqual(3);
    for (const cluster of data.clusters) {
      if (cluster.recurrence_state === 'insufficient_cases') {
        expect(typeof cluster.cases_needed).toBe('number');
        expect(cluster.cases_needed).toBeGreaterThan(0);
      }
    }
  });

  it('confidence warns when evidence is thin', () => {
    const data = JSON.parse(
      fs.readFileSync(
        path.resolve(
          repoRoot,
          'artifacts/dashboard_metrics/signal_confidence_record.json',
        ),
        'utf-8',
      ),
    );
    expect(data.minimum_evidence_count_for_high_confidence).toBeGreaterThanOrEqual(3);
    for (const entry of data.signal_entries) {
      if (entry.confidence_level === 'high_claimed') {
        expect(entry.confidence_warning).toBe('high_confidence_thin_evidence');
      }
    }
  });

  it('action bundles are candidate-only — no admission claim', () => {
    const data = JSON.parse(
      fs.readFileSync(
        path.resolve(
          repoRoot,
          'artifacts/dashboard_metrics/pqx_candidate_action_bundle_record.json',
        ),
        'utf-8',
      ),
    );
    for (const bundle of data.bundle_candidates) {
      expect(bundle.readiness_state).toBe('proposed');
      expect(Array.isArray(bundle.required_evidence)).toBe(true);
      expect(bundle.required_evidence.some((e: string) => /AEX|admission/.test(e))).toBe(true);
    }
  });

  it('freeze recommendation signal stays no_recommendation when budget is unknown', () => {
    const data = JSON.parse(
      fs.readFileSync(
        path.resolve(
          repoRoot,
          'artifacts/dashboard_metrics/met_freeze_recommendation_signal_record.json',
        ),
        'utf-8',
      ),
    );
    for (const signal of data.recommendation_signals) {
      if (signal.budget_status_observed === 'unknown') {
        expect(signal.recommendation_signal).toBe('no_recommendation');
      }
      expect(['SLO', 'CDE', 'SEL']).toContain(signal.recommended_owner_system);
    }
  });

  it('cross-run consistency ignores non-material timestamp differences', () => {
    const data = JSON.parse(
      fs.readFileSync(
        path.resolve(
          repoRoot,
          'artifacts/dashboard_metrics/cross_run_consistency_record.json',
        ),
        'utf-8',
      ),
    );
    expect(data.non_material_fields_ignored).toContain('created_at');
    expect(data.non_material_fields_ignored).toContain('generated_at');
  });
});
