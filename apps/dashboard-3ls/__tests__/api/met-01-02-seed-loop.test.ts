import fs from 'fs';
import path from 'path';

const appRoot = path.resolve(__dirname, '../../');
const repoRoot = path.resolve(appRoot, '../..');
const seedDir = path.join(repoRoot, 'artifacts/dashboard_seed');

function readJson(file: string) {
  const raw = fs.readFileSync(path.join(seedDir, file), 'utf-8');
  return JSON.parse(raw);
}

describe('MET-01-02 — dashboard seed artifacts', () => {
  const expected = [
    'source_artifact_record.json',
    'output_artifact_record.json',
    'eval_summary_record.json',
    'trust_policy_decision_record.json',
    'control_decision_record.json',
    'enforcement_action_record.json',
    'lineage_record.json',
    'replay_record.json',
    'observability_metrics_record.json',
    'slo_status_record.json',
    'failure_mode_dashboard_record.json',
    'near_miss_record.json',
    'minimal_loop_snapshot.json',
  ];

  it('seed artifacts exist and are valid JSON with required envelope fields', () => {
    for (const file of expected) {
      expect(fs.existsSync(path.join(seedDir, file))).toBe(true);
      const parsed = readJson(file);
      expect(parsed.artifact_type).toBeTruthy();
      expect(parsed.schema_version).toBeTruthy();
      expect(parsed.record_id).toBeTruthy();
      expect(parsed.created_at).toBeTruthy();
      expect(parsed.owner_system).toBeTruthy();
      expect(parsed.data_source).toBe('artifact_store');
      expect(Array.isArray(parsed.source_artifacts_used)).toBe(true);
      expect(Array.isArray(parsed.reason_codes)).toBe(true);
      expect(parsed.status).toBeTruthy();
      expect(Array.isArray(parsed.warnings)).toBe(true);
    }
  });

  it('minimal_loop_snapshot links all seeded records', () => {
    const snapshot = readJson('minimal_loop_snapshot.json');
    const stages = snapshot.proof_chain.map((s: { stage: string }) => s.stage);
    expect(stages).toEqual(expect.arrayContaining(['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL', 'REP', 'LIN', 'OBS', 'SLO']));
    expect(snapshot.source_artifacts_used).toHaveLength(12);
  });

  it('eval_summary_record is partial warn and not fake pass', () => {
    const evalSummary = readJson('eval_summary_record.json');
    expect(evalSummary.data_source).toBe('artifact_store');
    expect(evalSummary.status).toBe('warn');
    expect(evalSummary.reason_codes).toContain('eval_partial_coverage');
  });

  it('lineage_record links source -> output -> eval -> decision -> enforcement', () => {
    const lineage = readJson('lineage_record.json');
    const links = lineage.payload.links;
    expect(links).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ from: 'SRC-DASH-SEED-001', to: 'OUT-DASH-SEED-001' }),
        expect.objectContaining({ from: 'OUT-DASH-SEED-001', to: 'EVL-DASH-SEED-001' }),
        expect.objectContaining({ from: 'EVL-DASH-SEED-001', to: 'TPA-DASH-SEED-001' }),
        expect.objectContaining({ from: 'TPA-DASH-SEED-001', to: 'CDE-DASH-SEED-001' }),
        expect.objectContaining({ from: 'CDE-DASH-SEED-001', to: 'SEL-DASH-SEED-001' }),
      ])
    );
  });

  it('includes at least one real failure mode and one near miss', () => {
    const failure = readJson('failure_mode_dashboard_record.json');
    const nearMiss = readJson('near_miss_record.json');
    expect((failure.failure_modes ?? []).length).toBeGreaterThan(0);
    expect((nearMiss.near_misses ?? []).length).toBeGreaterThan(0);
  });

  it('does not encode full-pass posture in seeded loop', () => {
    const snapshot = readJson('minimal_loop_snapshot.json');
    expect(snapshot.minimal_loop_status).not.toBe('pass');
    expect(snapshot.status).toBe('warn');
  });
});

describe('MET-01-02 — dashboard API wiring', () => {
  const intelligenceSrc = fs.readFileSync(
    path.resolve(appRoot, 'app/api/intelligence/route.ts'),
    'utf-8'
  );
  const healthSrc = fs.readFileSync(path.resolve(appRoot, 'app/api/health/route.ts'), 'utf-8');
  const debugSrc = fs.readFileSync(
    path.resolve(appRoot, 'app/api/debug/artifacts/route.ts'),
    'utf-8'
  );

  it('intelligence route detects seed artifacts and exposes coverage/fallback counters', () => {
    expect(intelligenceSrc).toContain('seed_artifacts_present');
    expect(intelligenceSrc).toContain('proof_chain_coverage');
    expect(intelligenceSrc).toContain('artifact_backed_signal_count');
    expect(intelligenceSrc).toContain('fallback_signal_count');
    expect(intelligenceSrc).toContain('unknown_signal_count');
    expect(intelligenceSrc).toContain('failure_modes');
    expect(intelligenceSrc).toContain('near_misses');
    expect(intelligenceSrc).toContain('minimal_loop_status');
    expect(intelligenceSrc).toContain('source_artifacts_used');
    expect(intelligenceSrc).toContain('warnings');
  });

  it('health route seeds artifact-backed loop systems so artifact-backed percentage can exceed zero', () => {
    expect(healthSrc).toContain('seed_artifacts_present');
    expect(healthSrc).toContain('AEX');
    expect(healthSrc).toContain('EVL');
    expect(healthSrc).toContain('LIN');
  });

  it('health route keeps fallback behavior for non-seeded systems', () => {
    expect(healthSrc).toContain('stub_fallback');
    expect(healthSrc).toContain('stub_fallback');
  });

  it('debug artifacts route reports dashboard_seed discovery and missing expected files', () => {
    expect(debugSrc).toContain('dashboard_seed_found');
    expect(debugSrc).toContain('artifacts_found');
    expect(debugSrc).toContain('sample_files');
    expect(debugSrc).toContain('missing_expected_files');
    expect(debugSrc).toContain('warnings');
  });
});
