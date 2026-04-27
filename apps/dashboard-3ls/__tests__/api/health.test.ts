/**
 * Tests for the health data layer.
 * Route handlers import next/server which requires browser globals not available
 * in jsdom test environment, so we test the underlying signal logic and verify
 * the route source directly.
 */
import path from 'path';
import fs from 'fs';
import { deriveSystemSignals } from '@/lib/systemSignals';
import { loadArtifact } from '@/lib/artifactLoader';

const mockSnapshot = {
  generated_at: '2026-04-24T16:46:23Z',
  freshness_timestamp_utc: '2026-04-24T16:46:23Z',
  repo_name: 'spectrum-systems',
  root_counts: {
    files_total: 7872,
    runtime_modules: 264,
    tests: 650,
    contracts_total: 2759,
    schemas: 1479,
    examples: 1280,
    docs: 1509,
    run_artifacts: 152,
  },
  operational_signals: [
    { title: 'Constitution present', status: 'Strong', detail: 'Registry found.' },
  ],
  key_state: {
    current_run_state_record: {
      status: 'completed',
      batch_id: 'OPS-MASTER-01',
      generated_at: '2026-04-24T16:43:23Z',
      outcomes: [],
    },
    current_bottleneck_record: {
      bottleneck_name: 'repair_loop_latency',
      evidence: [],
      impacted_layers: [],
    },
    hard_gate_status_record: { pass_fail: 'pass', signals: [] },
  },
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
    control: { status: 'present_and_governed', evidence: [] },
  },
  repo_reality: {
    implemented_modules: [],
    schema_backed_components: [
      { system_id: 'SYS-001', system: 'Comment Resolution Engine', schema_files: [] },
    ],
    test_backed_systems: [
      { system_id: 'SYS-001', system: 'Comment Resolution Engine', evidence: 'eval/' },
    ],
    docs_only_systems: [],
    dead_or_unused_surfaces: [],
  },
};

describe('Health data layer — systemSignals', () => {
  it('reads repo counts when snapshot present', () => {
    const signals = deriveSystemSignals({ repoSnapshot: mockSnapshot, systemState: null });
    expect(signals.total_files).toBe(7872);
    expect(signals.test_count).toBe(650);
    expect(signals.hard_gate_status).toBe('pass');
    expect(signals.warnings).toHaveLength(1); // systemState missing
  });

  it('reads system breakdown when system_state present', () => {
    const signals = deriveSystemSignals({ repoSnapshot: null, systemState: mockSystemState });
    expect(signals.schema_backed_systems).toBe(1);
    expect(signals.test_backed_systems).toBe(1);
    expect(signals.warnings).toHaveLength(1); // repoSnapshot missing
  });

  it('returns unknown values and warnings when both artifacts missing', () => {
    const signals = deriveSystemSignals({ repoSnapshot: null, systemState: null });
    expect(signals.total_files).toBe('unknown');
    expect(signals.schema_backed_systems).toBe('unknown');
    expect(signals.warnings.length).toBeGreaterThan(0);
  });
});

describe('loadArtifact — file system integration', () => {
  afterEach(() => jest.restoreAllMocks());

  it('returns parsed JSON when file is readable', () => {
    jest
      .spyOn(fs, 'readFileSync')
      .mockReturnValue(JSON.stringify({ foo: 'bar' }) as never);
    const result = loadArtifact<{ foo: string }>('some/artifact.json');
    expect(result).toEqual({ foo: 'bar' });
  });

  it('returns null when file does not exist', () => {
    jest.spyOn(fs, 'readFileSync').mockImplementation(() => {
      throw Object.assign(new Error('ENOENT'), { code: 'ENOENT' });
    });
    const result = loadArtifact('missing/file.json');
    expect(result).toBeNull();
  });
});

describe('Health route source — backward compatibility', () => {
  const routePath = path.resolve(__dirname, '../../app/api/health/route.ts');
  const realFs = jest.requireActual<typeof fs>('fs');

  it('route source includes systems array for backward compatibility', () => {
    const source = realFs.readFileSync(routePath, 'utf-8');
    expect(source).toContain('systems:');
    expect(source).toContain('refreshed_at:');
    expect(source).toContain("status: 'success'");
  });

  it('route source contains no hardcoded LIVE record IDs', () => {
    const source = realFs.readFileSync(routePath, 'utf-8');
    expect(source).not.toMatch(/LIVE-\d/);
    expect(source).not.toMatch(/run-\d{4}-\d{2}-\d{2}-live/);
  });

  it('route source includes data_source and warnings envelope fields', () => {
    const source = realFs.readFileSync(routePath, 'utf-8');
    expect(source).toContain('data_source');
    expect(source).toContain('warnings');
    expect(source).toContain('source_artifacts_used');
  });

  it('route source consumes TLS integration artifact and fail-closed warnings', () => {
    const source = realFs.readFileSync(routePath, 'utf-8');
    expect(source).toContain('loadTLSIntegrationArtifact');
    expect(source).toContain('TLS_INTEGRATION_PATH');
    expect(source).toContain('fail_closed:');
    expect(source).toContain('stub_fallback for uncovered systems only');
  });
});
