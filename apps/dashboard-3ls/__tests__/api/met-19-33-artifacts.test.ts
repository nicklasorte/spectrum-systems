import fs from 'fs';
import path from 'path';

const appRoot = path.resolve(__dirname, '../../');
const repoRoot = path.resolve(appRoot, '../..');
const metricsDir = path.join(repoRoot, 'artifacts/dashboard_metrics');
const reviewsDir = path.join(repoRoot, 'docs/reviews');

function readJson(file: string) {
  return JSON.parse(fs.readFileSync(file, 'utf-8'));
}

const ENVELOPE_FIELDS = [
  'artifact_type',
  'schema_version',
  'record_id',
  'created_at',
  'owner_system',
  'data_source',
  'source_artifacts_used',
  'reason_codes',
  'status',
  'warnings',
];

const ARTIFACTS = [
  'candidate_closure_ledger_record.json',
  'met_artifact_dependency_index_record.json',
  'trend_frequency_honesty_gate_record.json',
  'evl_handoff_observation_tracker_record.json',
  'override_evidence_intake_record.json',
  'debug_explanation_index_record.json',
  'met_generated_artifact_classification_record.json',
];

const BANNED_AUTHORITY_TOKENS = [
  'enforcement_action',
  'certification_status',
  'certified',
  'promoted',
  'promotion_ready',
];

describe('MET-19-33 — required artifact existence and envelope', () => {
  ARTIFACTS.forEach((name) => {
    it(`${name} exists, parses, and carries envelope fields`, () => {
      const filePath = path.join(metricsDir, name);
      expect(fs.existsSync(filePath)).toBe(true);
      const parsed = readJson(filePath);
      ENVELOPE_FIELDS.forEach((field) => {
        expect(parsed[field]).toBeDefined();
      });
      expect(parsed.owner_system).toBe('MET');
      expect(parsed.data_source).toBe('artifact_store');
      expect(Array.isArray(parsed.source_artifacts_used)).toBe(true);
      expect(parsed.source_artifacts_used.length).toBeGreaterThan(0);
      expect(['warn', 'partial', 'unknown']).toContain(parsed.status);
    });

    it(`${name} carries failure_prevented and signal_improved`, () => {
      const parsed = readJson(path.join(metricsDir, name));
      expect(typeof parsed.failure_prevented).toBe('string');
      expect(parsed.failure_prevented.length).toBeGreaterThan(0);
      expect(typeof parsed.signal_improved).toBe('string');
      expect(parsed.signal_improved.length).toBeGreaterThan(0);
    });

    it(`${name} carries no banned authority field tokens at top level`, () => {
      const parsed = readJson(path.join(metricsDir, name));
      const topKeys = Object.keys(parsed);
      BANNED_AUTHORITY_TOKENS.forEach((tok) => {
        expect(topKeys).not.toContain(tok);
      });
    });
  });
});

describe('MET-19 — candidate closure ledger invariants', () => {
  const filePath = path.join(metricsDir, 'candidate_closure_ledger_record.json');

  it('every candidate item has source_artifacts_used and a known type', () => {
    const parsed = readJson(filePath);
    const items: Array<Record<string, unknown>> = parsed.candidate_items;
    expect(Array.isArray(items)).toBe(true);
    expect(items.length).toBeGreaterThan(0);
    const validStates = [
      'proposed',
      'open',
      'materialization_observed',
      'rejected_observation',
      'superseded_observation',
      'expired_observation',
      'stale_candidate_signal',
      'unknown',
    ];
    const validTypes = [
      'eval_candidate',
      'policy_candidate_signal',
      'fallback_reduction_item',
      'replay_lineage_hardening_item',
      'sel_signal_input',
      'failure_feedback_item',
    ];
    items.forEach((item) => {
      expect(typeof item.candidate_id).toBe('string');
      expect(validTypes).toContain(item.candidate_type);
      expect(validStates).toContain(item.current_state);
      expect(Array.isArray(item.source_artifacts_used)).toBe(true);
      expect((item.source_artifacts_used as string[]).length).toBeGreaterThan(0);
    });
  });

  it('stale candidates are surfaced as stale_candidate_signal (not hidden)', () => {
    const parsed = readJson(filePath);
    const stale = (parsed.candidate_items as Array<Record<string, unknown>>).filter(
      (i) => i.current_state === 'stale_candidate_signal',
    );
    expect(stale.length).toBeGreaterThan(0);
    stale.forEach((item) => {
      // Unknown age must remain 'unknown' rather than being substituted with a number.
      const age = item.age_days;
      const valid = age === 'unknown' || typeof age === 'number';
      expect(valid).toBe(true);
    });
  });
});

describe('MET-22 — trend/frequency honesty gate stays unknown below threshold', () => {
  const filePath = path.join(metricsDir, 'trend_frequency_honesty_gate_record.json');

  it('required threshold is 3 and blocked_trend_fields is non-empty', () => {
    const parsed = readJson(filePath);
    expect(parsed.required_case_count_for_trend).toBe(3);
    expect(Array.isArray(parsed.blocked_trend_fields)).toBe(true);
    expect(parsed.blocked_trend_fields.length).toBeGreaterThan(0);
  });

  it('per-shape breakdown trend_state stays unknown when case_count < 3', () => {
    const parsed = readJson(filePath);
    (parsed.shape_breakdown as Array<Record<string, unknown>>).forEach((shape) => {
      if (typeof shape.case_count === 'number' && shape.case_count < 3) {
        expect(shape.trend_state).toBe('unknown');
      }
    });
  });
});

describe('MET-23 — EVL handoff uses observation language only', () => {
  const filePath = path.join(metricsDir, 'evl_handoff_observation_tracker_record.json');

  it('every handoff item has materialization_observation and EVL target', () => {
    const parsed = readJson(filePath);
    const items: Array<Record<string, unknown>> = parsed.handoff_items;
    expect(Array.isArray(items)).toBe(true);
    expect(items.length).toBeGreaterThan(0);
    const valid = ['none_observed', 'observed', 'blocked_observation', 'unknown'];
    items.forEach((item) => {
      expect(item.target_owner_recommendation).toBe('EVL');
      expect(item.target_loop_leg).toBe('EVL');
      expect(valid).toContain(item.materialization_observation);
      expect(Array.isArray(item.source_artifacts_used)).toBe(true);
    });
  });
});

describe('MET-24 — override evidence intake stays absent without canonical log', () => {
  const filePath = path.join(metricsDir, 'override_evidence_intake_record.json');

  it('override_evidence_count is unknown and evidence_status is absent', () => {
    const parsed = readJson(filePath);
    expect(parsed.override_evidence_count).toBe('unknown');
    expect(parsed.evidence_status).toBe('absent');
    expect(parsed.reason_codes).toContain('override_evidence_missing');
    expect(Array.isArray(parsed.override_evidence_items)).toBe(true);
    expect(parsed.override_evidence_items.length).toBe(0);
    expect(parsed.next_recommended_input).toBeTruthy();
  });
});

describe('MET-25 — debug explanation index targets under 15 minutes', () => {
  const filePath = path.join(metricsDir, 'debug_explanation_index_record.json');

  it('debug_target_minutes is 15 and entries have all five debug fields', () => {
    const parsed = readJson(filePath);
    expect(parsed.debug_target_minutes).toBe(15);
    const entries: Array<Record<string, unknown>> = parsed.explanation_entries;
    expect(Array.isArray(entries)).toBe(true);
    expect(entries.length).toBeGreaterThan(0);
    const valid = ['sufficient', 'partial', 'insufficient', 'unknown'];
    entries.forEach((e) => {
      expect(typeof e.what_failed).toBe('string');
      expect(typeof e.why).toBe('string');
      expect(typeof e.where_in_loop).toBe('string');
      expect(Array.isArray(e.source_evidence)).toBe(true);
      expect((e.source_evidence as string[]).length).toBeGreaterThan(0);
      expect(typeof e.next_recommended_input).toBe('string');
      expect(valid).toContain(e.debug_readiness);
    });
  });
});

describe('MET-26 — generated artifact classification covers MET paths', () => {
  const filePath = path.join(metricsDir, 'met_generated_artifact_classification_record.json');

  it('all MET-19-33 artifact paths appear in the classification', () => {
    const parsed = readJson(filePath);
    const paths = new Set(
      (parsed.classified_paths as Array<Record<string, unknown>>).map((p) => p.path),
    );
    ARTIFACTS.forEach((name) => {
      expect(paths.has(`artifacts/dashboard_metrics/${name}`)).toBe(true);
    });
  });

  it('every classification + merge_policy is a known value', () => {
    const parsed = readJson(filePath);
    const validClasses = [
      'canonical_seed',
      'dashboard_metric',
      'derived_metric',
      'run_specific_generated',
      'review_artifact',
      'test_fixture',
      'unknown',
    ];
    const validPolicies = [
      'normal_review',
      'regenerate_not_hand_merge',
      'canonical_review_required',
      'unknown_blocked',
    ];
    (parsed.classified_paths as Array<Record<string, unknown>>).forEach((p) => {
      expect(validClasses).toContain(p.classification);
      expect(validPolicies).toContain(p.merge_policy);
    });
  });
});

describe('MET-19-33 — review docs exist', () => {
  [
    'MET-21-metric-usefulness-pruning-audit.md',
    'MET-27-closure-authority-redteam.md',
    'MET-28-closure-authority-fixes.md',
    'MET-29-simplification-debuggability-redteam.md',
    'MET-30-simplification-debuggability-fixes.md',
    'MET-31-artifact-integrity-redteam.md',
    'MET-32-artifact-integrity-fixes.md',
    'MET-33-final-hardening-review.md',
  ].forEach((name) => {
    it(`${name} exists`, () => {
      expect(fs.existsSync(path.join(reviewsDir, name))).toBe(true);
    });
  });
});

describe('MET-19-33 — authority vocabulary discipline', () => {
  it('MET-owned review docs do not assert MET as a decision/enforcement/promotion authority', () => {
    const docs = [
      'MET-21-metric-usefulness-pruning-audit.md',
      'MET-27-closure-authority-redteam.md',
      'MET-28-closure-authority-fixes.md',
      'MET-29-simplification-debuggability-redteam.md',
      'MET-30-simplification-debuggability-fixes.md',
      'MET-31-artifact-integrity-redteam.md',
      'MET-32-artifact-integrity-fixes.md',
      'MET-33-final-hardening-review.md',
    ];
    const banned = [
      'MET decides',
      'MET will decide',
      'MET enforces',
      'MET will enforce',
      'MET certifies',
      'MET will certify',
      'MET promotes',
      'MET will promote',
      'MET adopts',
      'MET will adopt',
      'MET approves',
      'MET will approve',
      'MET approval',
      'MET decision',
      'MET enforcement',
      'MET certification',
      'MET promotion',
    ];
    docs.forEach((d) => {
      const content = fs.readFileSync(path.join(reviewsDir, d), 'utf-8');
      banned.forEach((phrase) => {
        expect(content).not.toContain(phrase);
      });
    });
  });
});

describe('MET-19-33 — no fake pass / no fake green', () => {
  ARTIFACTS.forEach((name) => {
    it(`${name} status is never 'pass'`, () => {
      const parsed = readJson(path.join(metricsDir, name));
      expect(parsed.status).not.toBe('pass');
    });
  });
});
