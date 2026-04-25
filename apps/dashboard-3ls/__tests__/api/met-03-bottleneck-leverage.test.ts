import fs from 'fs';
import path from 'path';

const appRoot = path.resolve(__dirname, '../../');
const repoRoot = path.resolve(appRoot, '../..');
const metricsDir = path.join(repoRoot, 'artifacts/dashboard_metrics');
const seedDir = path.join(repoRoot, 'artifacts/dashboard_seed');

function readJson(dir: string, file: string) {
  const raw = fs.readFileSync(path.join(dir, file), 'utf-8');
  return JSON.parse(raw);
}

const REQUIRED_ENVELOPE = [
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

describe('MET-03 — bottleneck_record', () => {
  it('exists with required envelope fields', () => {
    const file = path.join(metricsDir, 'bottleneck_record.json');
    expect(fs.existsSync(file)).toBe(true);
    const record = readJson(metricsDir, 'bottleneck_record.json');
    for (const field of REQUIRED_ENVELOPE) {
      expect(record[field]).toBeTruthy();
    }
    expect(Array.isArray(record.source_artifacts_used)).toBe(true);
    expect(Array.isArray(record.reason_codes)).toBe(true);
    expect(Array.isArray(record.warnings)).toBe(true);
  });

  it('has dominant_bottleneck_system and constrained_loop_leg', () => {
    const record = readJson(metricsDir, 'bottleneck_record.json');
    expect(typeof record.dominant_bottleneck_system).toBe('string');
    expect(record.dominant_bottleneck_system.length).toBeGreaterThan(0);
    expect(typeof record.constrained_loop_leg).toBe('string');
    expect(record.constrained_loop_leg.length).toBeGreaterThan(0);
  });

  it('has bottleneck_confidence set to a known DataSource value', () => {
    const record = readJson(metricsDir, 'bottleneck_record.json');
    const validValues = ['artifact_store', 'repo_registry', 'derived', 'derived_estimate', 'stub_fallback', 'unknown'];
    expect(validValues).toContain(record.bottleneck_confidence);
  });

  it('has evidence array with at least one entry', () => {
    const record = readJson(metricsDir, 'bottleneck_record.json');
    expect(Array.isArray(record.evidence)).toBe(true);
    expect(record.evidence.length).toBeGreaterThan(0);
  });

  it('has warning_count_by_system covering all primary loop legs', () => {
    const record = readJson(metricsDir, 'bottleneck_record.json');
    const primaryLoop = ['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL'];
    expect(typeof record.warning_count_by_system).toBe('object');
    for (const leg of primaryLoop) {
      expect(typeof record.warning_count_by_system[leg]).toBe('number');
    }
  });

  it('does not mark bottleneck as PASS or healthy (warn is the honest state)', () => {
    const record = readJson(metricsDir, 'bottleneck_record.json');
    expect(record.status).not.toBe('pass');
    expect(record.status).not.toBe('PASS');
    expect(record.status).not.toBe('healthy');
  });
});

describe('MET-03 — leverage_queue_record', () => {
  it('exists with required envelope fields', () => {
    const file = path.join(metricsDir, 'leverage_queue_record.json');
    expect(fs.existsSync(file)).toBe(true);
    const record = readJson(metricsDir, 'leverage_queue_record.json');
    for (const field of REQUIRED_ENVELOPE) {
      expect(record[field]).toBeTruthy();
    }
  });

  it('has items array with at least one entry', () => {
    const record = readJson(metricsDir, 'leverage_queue_record.json');
    expect(Array.isArray(record.items)).toBe(true);
    expect(record.items.length).toBeGreaterThan(0);
  });

  it('no leverage item lacks data_source', () => {
    const record = readJson(metricsDir, 'leverage_queue_record.json');
    for (const item of record.items) {
      expect(item.data_source).toBeTruthy();
    }
  });

  it('no leverage item lacks failure_prevented', () => {
    const record = readJson(metricsDir, 'leverage_queue_record.json');
    for (const item of record.items) {
      expect(typeof item.failure_prevented).toBe('string');
      expect(item.failure_prevented.length).toBeGreaterThan(0);
    }
  });

  it('no leverage item lacks signal_improved', () => {
    const record = readJson(metricsDir, 'leverage_queue_record.json');
    for (const item of record.items) {
      expect(typeof item.signal_improved).toBe('string');
      expect(item.signal_improved.length).toBeGreaterThan(0);
    }
  });

  it('no leverage item lacks systems_affected', () => {
    const record = readJson(metricsDir, 'leverage_queue_record.json');
    for (const item of record.items) {
      expect(Array.isArray(item.systems_affected)).toBe(true);
      expect(item.systems_affected.length).toBeGreaterThan(0);
    }
  });

  it('no leverage item lacks confidence', () => {
    const record = readJson(metricsDir, 'leverage_queue_record.json');
    for (const item of record.items) {
      expect(item.confidence).toBeTruthy();
    }
  });

  it('all leverage_scores are positive numbers', () => {
    const record = readJson(metricsDir, 'leverage_queue_record.json');
    for (const item of record.items) {
      expect(typeof item.leverage_score).toBe('number');
      expect(item.leverage_score).toBeGreaterThan(0);
    }
  });

  it('items are sorted by leverage_score descending', () => {
    const record = readJson(metricsDir, 'leverage_queue_record.json');
    for (let i = 0; i < record.items.length - 1; i++) {
      expect(record.items[i].leverage_score).toBeGreaterThanOrEqual(record.items[i + 1].leverage_score);
    }
  });

  it('has a formula field documenting computation method', () => {
    const record = readJson(metricsDir, 'leverage_queue_record.json');
    expect(typeof record.formula).toBe('string');
    expect(record.formula.length).toBeGreaterThan(0);
  });
});

describe('MET-03 — risk_summary_record', () => {
  it('exists with required envelope fields', () => {
    const file = path.join(metricsDir, 'risk_summary_record.json');
    expect(fs.existsSync(file)).toBe(true);
    const record = readJson(metricsDir, 'risk_summary_record.json');
    for (const field of REQUIRED_ENVELOPE) {
      expect(record[field]).toBeTruthy();
    }
  });

  it('has fallback_signal_count, unknown_signal_count, missing_eval_count, missing_trace_count', () => {
    const record = readJson(metricsDir, 'risk_summary_record.json');
    expect(record.fallback_signal_count !== undefined).toBe(true);
    expect(record.unknown_signal_count !== undefined).toBe(true);
    expect(record.missing_eval_count !== undefined).toBe(true);
    expect(record.missing_trace_count !== undefined).toBe(true);
  });

  it('has proof_chain_coverage with required subfields', () => {
    const record = readJson(metricsDir, 'risk_summary_record.json');
    expect(typeof record.proof_chain_coverage).toBe('object');
    expect(typeof record.proof_chain_coverage.total).toBe('number');
    expect(typeof record.proof_chain_coverage.present).toBe('number');
    expect(typeof record.proof_chain_coverage.partial).toBe('number');
    expect(typeof record.proof_chain_coverage.percent_present_or_partial).toBe('number');
    expect(typeof record.proof_chain_coverage.percent_fully_present).toBe('number');
  });

  it('has top_risks array with at least one entry', () => {
    const record = readJson(metricsDir, 'risk_summary_record.json');
    expect(Array.isArray(record.top_risks)).toBe(true);
    expect(record.top_risks.length).toBeGreaterThan(0);
  });

  it('proof_chain_coverage percent_present_or_partial >= percent_fully_present', () => {
    const record = readJson(metricsDir, 'risk_summary_record.json');
    expect(record.proof_chain_coverage.percent_present_or_partial).toBeGreaterThanOrEqual(
      record.proof_chain_coverage.percent_fully_present
    );
  });
});

describe('MET-03 — failure_mode_dashboard_record extension', () => {
  it('failure modes now include frequency, systems_affected, and trend fields', () => {
    const record = readJson(seedDir, 'failure_mode_dashboard_record.json');
    for (const fm of record.failure_modes) {
      expect(fm.frequency !== undefined).toBe(true);
      expect(Array.isArray(fm.systems_affected)).toBe(true);
      expect(fm.systems_affected.length).toBeGreaterThan(0);
      expect(fm.trend !== undefined).toBe(true);
    }
  });

  it('failure mode trend is unknown (no historical baseline)', () => {
    const record = readJson(seedDir, 'failure_mode_dashboard_record.json');
    for (const fm of record.failure_modes) {
      expect(fm.trend).toBe('unknown');
    }
  });
});

describe('MET-03 — API wiring checks', () => {
  const intelligenceSrc = fs.readFileSync(
    path.resolve(appRoot, 'app/api/intelligence/route.ts'),
    'utf-8'
  );
  const pageSrc = fs.readFileSync(path.resolve(appRoot, 'app/page.tsx'), 'utf-8');

  it('intelligence route exposes bottleneck, leverage_queue, risk_summary', () => {
    expect(intelligenceSrc).toContain('bottleneck_record.json');
    expect(intelligenceSrc).toContain('leverage_queue_record.json');
    expect(intelligenceSrc).toContain('risk_summary_record.json');
    expect(intelligenceSrc).toContain('bottleneck,');
    expect(intelligenceSrc).toContain('leverage_queue: leverageQueue');
    expect(intelligenceSrc).toContain('risk_summary: riskSummary');
  });

  it('intelligence route includes data_source and source_artifacts_used on all new fields', () => {
    expect(intelligenceSrc).toContain("data_source: 'artifact_store' as const");
    expect(intelligenceSrc).toContain('ARTIFACT_PATHS.bottleneckRecord');
    expect(intelligenceSrc).toContain('ARTIFACT_PATHS.leverageQueueRecord');
    expect(intelligenceSrc).toContain('ARTIFACT_PATHS.riskSummaryRecord');
    expect(intelligenceSrc).toContain('source_artifacts_used');
  });

  it('intelligence route degrades to unknown when metrics artifacts not found', () => {
    expect(intelligenceSrc).toContain("data_source: 'unknown' as const");
    expect(intelligenceSrc).toContain('bottleneck_record artifact not loaded');
    expect(intelligenceSrc).toContain('leverage_queue_record not found');
    expect(intelligenceSrc).toContain('risk_summary_record not found');
  });

  it('fallback signals still degrade trust state in dashboard page', () => {
    expect(pageSrc).toContain('stub_fallback');
    expect(pageSrc).toContain('dataSourceAllowsHealthy');
    expect(pageSrc).toContain('trustState');
    expect(pageSrc).toContain("trustState = 'BLOCK'");
    expect(pageSrc).toContain("trustState = 'FREEZE'");
  });

  it('unknown signals cannot produce green/pass status in dashboard', () => {
    expect(pageSrc).toContain("sourceMix.unknown > 0");
    expect(pageSrc).toContain("'FREEZE'");
    expect(pageSrc).toContain('unknown_source_present');
    // PASS is the initial default; FREEZE/BLOCK overwrite it when unknown/fallback found
    expect(pageSrc).toContain("TrustState = 'PASS'");
    const passIndex = pageSrc.indexOf("TrustState = 'PASS'");
    const freezeIndex = pageSrc.indexOf("trustState = 'FREEZE'");
    expect(passIndex).toBeGreaterThan(-1);
    expect(freezeIndex).toBeGreaterThan(-1);
    expect(passIndex).toBeLessThan(freezeIndex);
  });

  it('dashboard loop panel highlights bottleneck node', () => {
    expect(pageSrc).toContain('isBottleneck');
    expect(pageSrc).toContain('data-bottleneck');
    expect(pageSrc).toContain('border-amber-400');
    expect(pageSrc).toContain('bottleneck-reason');
  });

  it('dashboard risk panel uses displayTopRisks from API risk_summary', () => {
    expect(pageSrc).toContain('displayTopRisks');
    expect(pageSrc).toContain('apiRiskSummary');
    expect(pageSrc).toContain('proof_chain_coverage');
  });

  it('leverage queue prefers API artifact items when available', () => {
    expect(pageSrc).toContain('apiLeverageItems');
    expect(pageSrc).toContain('intelligence?.leverage_queue?.items');
    expect(pageSrc).toContain('localLeverageQueue');
  });
});
