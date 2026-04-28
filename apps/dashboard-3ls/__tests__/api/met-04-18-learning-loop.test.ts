import fs from 'fs';
import path from 'path';

const appRoot = path.resolve(__dirname, '../../');
const repoRoot = path.resolve(appRoot, '../..');
const metricsDir = path.join(repoRoot, 'artifacts/dashboard_metrics');
const casesDir = path.join(repoRoot, 'artifacts/dashboard_cases');
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

const REQUIRES_FAILURE_AND_SIGNAL = [
  'failure_feedback_record.json',
  'eval_candidate_record.json',
  'policy_candidate_signal_record.json',
  'feedback_loop_snapshot.json',
  'failure_explanation_packets.json',
  'override_audit_log_record.json',
  'eval_materialization_path_record.json',
  'replay_lineage_hardening_record.json',
  'fallback_reduction_plan_record.json',
  'sel_compliance_signal_input_record.json',
];

const BANNED_AUTHORITY_TOKENS = [
  'enforcement_action',
  'certification_status',
  'certified',
  'promoted',
  'promotion_ready',
];

const ALLOWED_OWNER_BOUNDARY_PHRASES = [
  'EVL is the canonical owner',
  'TPA, CDE, SEL, and GOV remain canonical owners',
  'SEL is the canonical enforcement authority',
  'SEL is the canonical owner',
  'TPA is the canonical owner',
  'CDE is the canonical owner',
  'EVL/TPA/CDE/SEL/GOV',
  'EVL/TPA/CDE/SEL',
  'CDE is the sole',
  'SEL is the sole',
];

describe('MET-04-18 — required artifact existence and envelope', () => {
  REQUIRES_FAILURE_AND_SIGNAL.forEach((name) => {
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
  });
});

describe('MET-04 — failure feedback record links to existing failures and leverage', () => {
  const filePath = path.join(metricsDir, 'failure_feedback_record.json');

  it('every feedback item has source_artifacts_used and links to a known source_type', () => {
    const parsed = readJson(filePath);
    expect(Array.isArray(parsed.feedback_items)).toBe(true);
    expect(parsed.feedback_items.length).toBeGreaterThan(0);
    parsed.feedback_items.forEach((item: Record<string, unknown>) => {
      expect(['failure_mode', 'near_miss', 'leverage_item']).toContain(item.source_type);
      expect(typeof item.source_record).toBe('string');
      expect(typeof item.failure_prevented).toBe('string');
      expect(typeof item.signal_improved).toBe('string');
      expect(Array.isArray(item.affected_systems)).toBe(true);
      expect(['proposed', 'materialized', 'rejected', 'superseded', 'expired', 'unknown']).toContain(
        item.feedback_status,
      );
      expect(Array.isArray(item.source_artifacts_used)).toBe(true);
      expect((item.source_artifacts_used as string[]).length).toBeGreaterThan(0);
    });
  });
});

describe('MET-04 — eval candidates remain proposed and sourced', () => {
  const filePath = path.join(metricsDir, 'eval_candidate_record.json');

  it('every candidate is proposed and has source_artifacts_used', () => {
    const parsed = readJson(filePath);
    expect(Array.isArray(parsed.candidates)).toBe(true);
    expect(parsed.candidates.length).toBeGreaterThan(0);
    parsed.candidates.forEach((c: Record<string, unknown>) => {
      expect(c.status).toBe('proposed');
      expect(c.owner_recommendation).toBe('EVL');
      expect(typeof c.failure_prevented).toBe('string');
      expect(typeof c.signal_improved).toBe('string');
      expect(Array.isArray(c.source_artifacts_used)).toBe(true);
      expect((c.source_artifacts_used as string[]).length).toBeGreaterThan(0);
      expect([
        'schema_conformance',
        'evidence_coverage',
        'trace_completeness',
        'replay_consistency',
        'authority_boundary',
        'dashboard_truth',
      ]).toContain(c.candidate_eval_type);
    });
  });
});

describe('MET-04 — policy candidate signals remain proposed and sourced', () => {
  const filePath = path.join(metricsDir, 'policy_candidate_signal_record.json');

  it('every candidate is proposed and addressed to a canonical owner', () => {
    const parsed = readJson(filePath);
    expect(Array.isArray(parsed.candidates)).toBe(true);
    expect(parsed.candidates.length).toBeGreaterThan(0);
    parsed.candidates.forEach((c: Record<string, unknown>) => {
      expect(c.status).toBe('proposed');
      expect(['TPA', 'CDE', 'SEL', 'GOV']).toContain(c.suggested_owner_system);
      expect(typeof c.failure_prevented).toBe('string');
      expect(typeof c.signal_improved).toBe('string');
      expect(Array.isArray(c.source_artifacts_used)).toBe(true);
      expect((c.source_artifacts_used as string[]).length).toBeGreaterThan(0);
      expect(Array.isArray(c.required_evidence_before_adoption)).toBe(true);
    });
  });
});

describe('MET-04 — feedback loop snapshot reports unknown counts honestly', () => {
  const filePath = path.join(metricsDir, 'feedback_loop_snapshot.json');

  it('loop_status is partial and counts are non-negative numbers', () => {
    const parsed = readJson(filePath);
    expect(parsed.loop_status).toBe('partial');
    expect(typeof parsed.feedback_items_count).toBe('number');
    expect(typeof parsed.eval_candidates_count).toBe('number');
    expect(typeof parsed.policy_candidate_signals_count).toBe('number');
    expect(parsed.feedback_items_count).toBeGreaterThan(0);
  });
});

describe('MET-06 — override audit log holds at unknown without history', () => {
  const filePath = path.join(metricsDir, 'override_audit_log_record.json');

  it('override_count is unknown and reason_codes name override_history_missing', () => {
    const parsed = readJson(filePath);
    expect(parsed.override_count).toBe('unknown');
    expect(parsed.reason_codes).toContain('override_history_missing');
    expect(parsed.next_recommended_input).toBeTruthy();
  });

  it('overrides[] is empty and not fabricated', () => {
    const parsed = readJson(filePath);
    expect(Array.isArray(parsed.overrides)).toBe(true);
    expect(parsed.overrides.length).toBe(0);
  });
});

describe('MET-09 — eval materialization path is proposed only', () => {
  const filePath = path.join(metricsDir, 'eval_materialization_path_record.json');

  it('materialization_status is proposed and owner_recommendation is EVL', () => {
    const parsed = readJson(filePath);
    expect(parsed.materialization_status).toBe('proposed');
    expect(parsed.owner_recommendation).toBe('EVL');
    expect(Array.isArray(parsed.required_authority_inputs)).toBe(true);
    expect(parsed.required_authority_inputs.length).toBeGreaterThan(0);
    expect(Array.isArray(parsed.required_artifacts_before_materialization)).toBe(true);
    expect(Array.isArray(parsed.required_tests)).toBe(true);
  });
});

describe('MET-10 — additional dashboard cases (3+ comparable, no fake pass)', () => {
  it('case index exists and references at least 3 cases', () => {
    const filePath = path.join(casesDir, 'case_index_record.json');
    expect(fs.existsSync(filePath)).toBe(true);
    const parsed = readJson(filePath);
    expect(Array.isArray(parsed.cases)).toBe(true);
    expect(parsed.cases.length).toBeGreaterThanOrEqual(3);
  });

  it('every case ties to a real failure mode, near miss, or leverage item and reports warn/partial', () => {
    const indexPath = path.join(casesDir, 'case_index_record.json');
    const index = readJson(indexPath);
    index.cases.forEach((rel: string) => {
      const casePath = path.join(casesDir, rel);
      expect(fs.existsSync(casePath)).toBe(true);
      const c = readJson(casePath);
      expect(c.owner_system).toBe('MET');
      expect(c.data_source).toBe('artifact_store');
      expect(['warn', 'partial', 'unknown']).toContain(c.status);
      const ties = [c.ties_to_failure_mode, c.ties_to_near_miss, c.ties_to_leverage_item];
      expect(ties.some((t) => typeof t === 'string' && t.length > 0)).toBe(true);
      expect(typeof c.failure_prevented).toBe('string');
      expect(typeof c.signal_improved).toBe('string');
    });
  });
});

describe('MET-12 — fallback reduction targets only high-leverage core/overlay systems', () => {
  const filePath = path.join(metricsDir, 'fallback_reduction_plan_record.json');

  it('every fallback_item is in the core or overlay set with required fields', () => {
    const parsed = readJson(filePath);
    const allowed = ['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL', 'REP', 'LIN', 'OBS', 'SLO'];
    expect(Array.isArray(parsed.fallback_items)).toBe(true);
    expect(parsed.fallback_items.length).toBeGreaterThan(0);
    parsed.fallback_items.forEach((item: Record<string, unknown>) => {
      expect(allowed).toContain(item.system_id);
      expect(typeof item.replacement_signal_needed).toBe('string');
      expect(typeof item.failure_prevented).toBe('string');
      expect(typeof item.signal_improved).toBe('string');
      expect(['high', 'medium', 'low']).toContain(item.priority);
      expect(Array.isArray(item.source_artifacts_used)).toBe(true);
      expect((item.source_artifacts_used as string[]).length).toBeGreaterThan(0);
    });
  });
});

describe('MET-13 — SEL compliance signal input is authority-neutral', () => {
  const filePath = path.join(metricsDir, 'sel_compliance_signal_input_record.json');

  it('suggests SEL as owner and reports proposed', () => {
    const parsed = readJson(filePath);
    expect(parsed.suggested_owner_system).toBe('SEL');
    expect(parsed.status_label).toBe('proposed');
    expect(typeof parsed.observed_gap).toBe('string');
    expect(typeof parsed.compliance_signal_needed).toBe('string');
  });
});

describe('MET-04-18 — review docs exist', () => {
  ['MET-07-learning-loop-truth-redteam.md',
   'MET-08-learning-loop-fixes.md',
   'MET-14-removable-metric-system-audit.md',
   'MET-15-core-loop-strength-redteam.md',
   'MET-16-core-loop-fixes.md',
   'MET-17-dashboard-usefulness-redteam.md',
   'MET-18-dashboard-usefulness-fixes.md',
   'MET-04-18-final-integration-review.md',
  ].forEach((name) => {
    it(`${name} exists`, () => {
      expect(fs.existsSync(path.join(reviewsDir, name))).toBe(true);
    });
  });
});

describe('MET-04-18 — authority vocabulary discipline in MET-owned artifacts', () => {
  REQUIRES_FAILURE_AND_SIGNAL.forEach((name) => {
    it(`${name} contains no banned authority field tokens at top level`, () => {
      const parsed = readJson(path.join(metricsDir, name));
      const topKeys = Object.keys(parsed);
      BANNED_AUTHORITY_TOKENS.forEach((tok) => {
        expect(topKeys).not.toContain(tok);
      });
    });
  });

  it('MET-owned review docs do not assert MET as a decision/enforcement/promotion authority', () => {
    const docs = [
      'MET-07-learning-loop-truth-redteam.md',
      'MET-08-learning-loop-fixes.md',
      'MET-14-removable-metric-system-audit.md',
      'MET-15-core-loop-strength-redteam.md',
      'MET-16-core-loop-fixes.md',
      'MET-17-dashboard-usefulness-redteam.md',
      'MET-18-dashboard-usefulness-fixes.md',
      'MET-04-18-final-integration-review.md',
    ];
    const bannedAssertions = [
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
    ];
    docs.forEach((d) => {
      const content = fs.readFileSync(path.join(reviewsDir, d), 'utf-8');
      bannedAssertions.forEach((phrase) => {
        expect(content).not.toContain(phrase);
      });
    });
  });
});

describe('MET-04-18 — no fake pass / no fake green / no fake trend', () => {
  REQUIRES_FAILURE_AND_SIGNAL.forEach((name) => {
    it(`${name} status is never 'pass'`, () => {
      const parsed = readJson(path.join(metricsDir, name));
      expect(parsed.status).not.toBe('pass');
    });
  });

  it('case index does not declare a comparable trend below the threshold', () => {
    const idx = readJson(path.join(casesDir, 'case_index_record.json'));
    const reasonCodes: string[] = idx.reason_codes ?? [];
    expect(reasonCodes).toContain('trend_remains_unknown_below_three_comparable_cases');
  });
});
