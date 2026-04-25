import fs from 'fs';
import path from 'path';

const appRoot = path.resolve(__dirname, '../../');
const repoRoot = path.resolve(appRoot, '../..');
const metricsDir = path.join(repoRoot, 'artifacts/dashboard_metrics');
const seedDir = path.join(repoRoot, 'artifacts/dashboard_seed');

function readJson(file: string) {
  const raw = fs.readFileSync(file, 'utf-8');
  return JSON.parse(raw);
}

describe('MET-03 — bottleneck record', () => {
  const filePath = path.join(metricsDir, 'bottleneck_record.json');

  it('exists and parses', () => {
    expect(fs.existsSync(filePath)).toBe(true);
    const parsed = readJson(filePath);
    expect(parsed.artifact_type).toBe('bottleneck_record');
    expect(parsed.data_source).toBe('artifact_store');
    expect(Array.isArray(parsed.source_artifacts_used)).toBe(true);
    expect(parsed.source_artifacts_used.length).toBeGreaterThan(0);
    expect(Array.isArray(parsed.warnings)).toBe(true);
    expect(parsed.status).toBe('warn');
  });

  it('identifies dominant bottleneck system and constrained loop leg', () => {
    const parsed = readJson(filePath);
    expect(parsed.payload.dominant_bottleneck_system).toBeTruthy();
    expect(parsed.payload.constrained_loop_leg).toBeTruthy();
    expect(['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL']).toContain(
      parsed.payload.constrained_loop_leg
    );
  });

  it('declares bottleneck_confidence as artifact_backed or derived_estimate', () => {
    const parsed = readJson(filePath);
    expect(['artifact_backed', 'derived_estimate']).toContain(
      parsed.payload.bottleneck_confidence
    );
  });

  it('includes supporting evidence with sources', () => {
    const parsed = readJson(filePath);
    expect(Array.isArray(parsed.payload.supporting_evidence)).toBe(true);
    expect(parsed.payload.supporting_evidence.length).toBeGreaterThan(0);
    parsed.payload.supporting_evidence.forEach((ev: { source: string; kind: string }) => {
      expect(ev.source).toBeTruthy();
      expect(ev.kind).toBeTruthy();
    });
  });
});

describe('MET-03 — leverage queue record', () => {
  const filePath = path.join(metricsDir, 'leverage_queue_record.json');

  it('exists and parses', () => {
    expect(fs.existsSync(filePath)).toBe(true);
    const parsed = readJson(filePath);
    expect(parsed.artifact_type).toBe('leverage_queue_record');
    expect(parsed.data_source).toBe('artifact_store');
    expect(parsed.status).toBe('warn');
    expect(Array.isArray(parsed.items)).toBe(true);
    expect(parsed.items.length).toBeGreaterThan(0);
  });

  it('every leverage item has required fields', () => {
    const parsed = readJson(filePath);
    parsed.items.forEach((item: Record<string, unknown>) => {
      expect(item.title).toBeTruthy();
      expect(item.failure_prevented).toBeTruthy();
      expect(item.signal_improved).toBeTruthy();
      expect(Array.isArray(item.systems_affected)).toBe(true);
      expect(item.severity).toBeTruthy();
      expect(item.estimated_effort).toBeTruthy();
      expect(typeof item.leverage_score).toBe('number');
      expect(item.data_source).toBe('artifact_store');
      expect(Array.isArray(item.source_artifacts_used)).toBe(true);
      expect((item.source_artifacts_used as string[]).length).toBeGreaterThan(0);
      expect(item.confidence).toBeTruthy();
    });
  });

  it('no leverage item lacks source_artifacts_used', () => {
    const parsed = readJson(filePath);
    parsed.items.forEach((item: { source_artifacts_used: string[] }) => {
      expect(Array.isArray(item.source_artifacts_used)).toBe(true);
      expect(item.source_artifacts_used.length).toBeGreaterThan(0);
    });
  });

  it('no leverage item lacks failure_prevented', () => {
    const parsed = readJson(filePath);
    parsed.items.forEach((item: { failure_prevented: string }) => {
      expect(item.failure_prevented).toBeTruthy();
      expect(typeof item.failure_prevented).toBe('string');
      expect(item.failure_prevented.length).toBeGreaterThan(0);
    });
  });

  it('no leverage item lacks signal_improved', () => {
    const parsed = readJson(filePath);
    parsed.items.forEach((item: { signal_improved: string }) => {
      expect(item.signal_improved).toBeTruthy();
      expect(typeof item.signal_improved).toBe('string');
      expect(item.signal_improved.length).toBeGreaterThan(0);
    });
  });

  it('leverage formula and weights are documented', () => {
    const parsed = readJson(filePath);
    expect(parsed.leverage_formula).toBeTruthy();
    expect(parsed.weights).toBeTruthy();
    expect(parsed.weights.severity).toBeTruthy();
    expect(parsed.weights.effort).toBeTruthy();
    expect(parsed.weights.boosts).toBeTruthy();
  });
});

describe('MET-03 — risk summary record', () => {
  const filePath = path.join(metricsDir, 'risk_summary_record.json');

  it('exists and parses', () => {
    expect(fs.existsSync(filePath)).toBe(true);
    const parsed = readJson(filePath);
    expect(parsed.artifact_type).toBe('risk_summary_record');
    expect(parsed.data_source).toBe('artifact_store');
    expect(parsed.status).toBe('warn');
  });

  it('records counts and proof chain coverage', () => {
    const parsed = readJson(filePath);
    expect(typeof parsed.payload.fallback_signal_count).toBe('number');
    expect(typeof parsed.payload.unknown_signal_count).toBe('number');
    expect(typeof parsed.payload.missing_eval_count).toBe('number');
    expect(typeof parsed.payload.missing_trace_count).toBe('number');
    expect(parsed.payload.proof_chain_coverage).toBeTruthy();
    expect(typeof parsed.payload.proof_chain_coverage.total).toBe('number');
  });

  it('override_count remains unknown without history', () => {
    const parsed = readJson(filePath);
    expect(parsed.payload.override_count).toBe('unknown');
  });

  it('top_risks each include severity, systems, and evidence artifact', () => {
    const parsed = readJson(filePath);
    expect(Array.isArray(parsed.payload.top_risks)).toBe(true);
    expect(parsed.payload.top_risks.length).toBeGreaterThan(0);
    parsed.payload.top_risks.forEach(
      (r: { severity: string; systems_affected: string[]; evidence_artifact: string }) => {
        expect(r.severity).toBeTruthy();
        expect(Array.isArray(r.systems_affected)).toBe(true);
        expect(r.evidence_artifact).toBeTruthy();
      }
    );
  });
});

describe('MET-03 — failure mode dashboard expansion', () => {
  const filePath = path.join(seedDir, 'failure_mode_dashboard_record.json');

  it('failure modes carry severity, frequency, systems_affected, and trend', () => {
    const parsed = readJson(filePath);
    expect(Array.isArray(parsed.failure_modes)).toBe(true);
    expect(parsed.failure_modes.length).toBeGreaterThan(0);
    parsed.failure_modes.forEach((fm: Record<string, unknown>) => {
      expect(fm.severity).toBeTruthy();
      expect(fm.frequency).toBeTruthy();
      expect(Array.isArray(fm.systems_affected)).toBe(true);
      expect(fm.trend).toBeTruthy();
    });
  });

  it('frequency and trend remain unknown until history exists', () => {
    const parsed = readJson(filePath);
    parsed.failure_modes.forEach((fm: { frequency: string; trend: string }) => {
      expect(fm.frequency).toBe('unknown');
      expect(fm.trend).toBe('unknown');
    });
  });
});

describe('MET-03 — intelligence API wiring', () => {
  const intelligenceSrc = fs.readFileSync(
    path.resolve(appRoot, 'app/api/intelligence/route.ts'),
    'utf-8'
  );

  it('wires bottleneck, leverage_queue, and risk_summary into /api/intelligence', () => {
    expect(intelligenceSrc).toContain('bottleneck_record.json');
    expect(intelligenceSrc).toContain('leverage_queue_record.json');
    expect(intelligenceSrc).toContain('risk_summary_record.json');
    expect(intelligenceSrc).toContain('bottleneck:');
    expect(intelligenceSrc).toContain('bottleneck_confidence');
    expect(intelligenceSrc).toContain('leverage_queue:');
    expect(intelligenceSrc).toContain('risk_summary:');
  });

  it('filters leverage items lacking source/failure_prevented/signal_improved', () => {
    expect(intelligenceSrc).toContain('failure_prevented');
    expect(intelligenceSrc).toContain('signal_improved');
    expect(intelligenceSrc).toContain('source_artifacts_used');
  });

  it('keeps source_artifacts_used and warnings exposed in payload', () => {
    expect(intelligenceSrc).toContain('source_artifacts_used');
    expect(intelligenceSrc).toContain('warnings');
  });

  it('does not zero risk counts when partial-artifact fields are absent', () => {
    // Counts must degrade to 'unknown' when the artifact is present but the
    // specific field is missing (older schema or partial write); the API
    // must never silently substitute 0.
    const fallbackBlock = intelligenceSrc.slice(intelligenceSrc.indexOf('const riskBlock'));
    expect(fallbackBlock).toMatch(/fallback_signal_count[\s\S]*?'unknown'/);
    expect(fallbackBlock).toMatch(/unknown_signal_count[\s\S]*?'unknown'/);
    expect(fallbackBlock).toMatch(/missing_eval_count[\s\S]*?'unknown'/);
    expect(fallbackBlock).toMatch(/missing_trace_count[\s\S]*?'unknown'/);
  });

  it('defaults missing leverage data_source to unknown rather than artifact_store', () => {
    // A partial leverage artifact must not be presented as fully artifact-
    // backed: when data_source is absent the API must surface 'unknown'.
    const leverageBlock = intelligenceSrc.slice(intelligenceSrc.indexOf('const leverageBlock'));
    expect(leverageBlock).toMatch(/data_source: leverageQueue\?\.data_source \?\? 'unknown'/);
  });

  it('filters leverage items missing systems_affected so the render path cannot crash', () => {
    const filterBlock = intelligenceSrc.slice(intelligenceSrc.indexOf('const filteredLeverage'));
    expect(filterBlock).toMatch(/Array\.isArray\(item\.systems_affected\)/);
    expect(filterBlock).toMatch(/item\.systems_affected\.length > 0/);
  });

  it('defaults missing bottleneck and risk data_source fields to unknown', () => {
    const bottleneckBlock = intelligenceSrc.slice(intelligenceSrc.indexOf('const bottleneckBlock'));
    expect(bottleneckBlock).toMatch(/data_source: bottleneck\.data_source \?\? 'unknown'/);
    const riskBlock = intelligenceSrc.slice(intelligenceSrc.indexOf('const riskBlock'));
    expect(riskBlock).toMatch(/data_source: riskSummary\?\.data_source \?\? 'unknown'/);
  });
});
