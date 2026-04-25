import { normalizeSignalStatus, safeCardStatus } from '@/lib/signalStatus';
import type { DashboardSignal } from '@/lib/types';

function baseSignal(overrides: Partial<DashboardSignal<number>> = {}): DashboardSignal<number> {
  return {
    signal_id: 'test_signal',
    label: 'Test Signal',
    value: 1,
    status: 'healthy',
    data_source: 'artifact_store',
    confidence: 1.0,
    source_artifacts_used: ['a.json'],
    warnings: [],
    reason_codes: [],
    last_updated: '2026-04-25T00:00:00Z',
    ...overrides,
  };
}

describe('normalizeSignalStatus — DSH-04 no green without source', () => {
  it('artifact_store may render healthy', () => {
    const out = normalizeSignalStatus(baseSignal({ data_source: 'artifact_store' }));
    expect(out.status).toBe('healthy');
  });

  it('repo_registry may render healthy', () => {
    const out = normalizeSignalStatus(baseSignal({ data_source: 'repo_registry' }));
    expect(out.status).toBe('healthy');
  });

  it('derived renders healthy when all source artifacts are present', () => {
    const out = normalizeSignalStatus(
      baseSignal({
        data_source: 'derived',
        source_artifacts_used: ['a.json', 'b.json'],
      }),
      { requiredArtifactCount: 2, loadedArtifactCount: 2 }
    );
    expect(out.status).toBe('healthy');
  });

  it('derived degrades to warning when not all source artifacts are present', () => {
    const out = normalizeSignalStatus(
      baseSignal({
        data_source: 'derived',
        source_artifacts_used: ['a.json'],
      }),
      { requiredArtifactCount: 2, loadedArtifactCount: 1 }
    );
    expect(out.status).toBe('warning');
    expect(out.reason_codes).toContain('derived_partial_inputs');
  });

  it('derived_estimate caps at warning, never green', () => {
    const out = normalizeSignalStatus(baseSignal({ data_source: 'derived_estimate' }));
    expect(out.status).toBe('warning');
    expect(out.reason_codes).toContain('provisional_truth');
  });

  it('stub_fallback caps at unknown, never green', () => {
    const out = normalizeSignalStatus(baseSignal({ data_source: 'stub_fallback' }));
    expect(out.status).toBe('unknown');
    expect(out.reason_codes).toContain('stub_fallback_no_source');
  });

  it('stub_fallback preserves critical (fail-closed beats unknown)', () => {
    const out = normalizeSignalStatus(
      baseSignal({ data_source: 'stub_fallback', status: 'critical' })
    );
    expect(out.status).toBe('critical');
  });

  it('unknown source renders unknown or critical', () => {
    expect(normalizeSignalStatus(baseSignal({ data_source: 'unknown' })).status).toBe('unknown');
    expect(
      normalizeSignalStatus(baseSignal({ data_source: 'unknown', status: 'critical' })).status
    ).toBe('critical');
  });

  it('unknown value never renders healthy', () => {
    const out = normalizeSignalStatus(
      baseSignal({ data_source: 'artifact_store', value: 'unknown' })
    );
    expect(out.status).not.toBe('healthy');
    expect(out.reason_codes).toContain('value_unknown');
  });

  it('emits healthy_blocked_by_source reason when status is healthy but source forbids it', () => {
    const out = normalizeSignalStatus(
      baseSignal({ data_source: 'derived_estimate', status: 'healthy' })
    );
    // derived_estimate path produces 'warning' first; check stub branch produces unknown.
    const stub = normalizeSignalStatus(
      baseSignal({ data_source: 'stub_fallback', status: 'healthy' })
    );
    expect(out.status).toBe('warning');
    expect(stub.status).toBe('unknown');
    expect(stub.reason_codes).toContain('stub_fallback_no_source');
  });
});

describe('safeCardStatus', () => {
  it('keeps healthy for artifact_store', () => {
    expect(safeCardStatus('healthy', 'artifact_store')).toBe('healthy');
  });

  it('downgrades healthy to unknown for stub_fallback', () => {
    expect(safeCardStatus('healthy', 'stub_fallback')).toBe('unknown');
  });

  it('downgrades healthy to warning for derived_estimate', () => {
    expect(safeCardStatus('healthy', 'derived_estimate')).toBe('warning');
  });

  it('preserves warning regardless of source', () => {
    expect(safeCardStatus('warning', 'stub_fallback')).toBe('warning');
    expect(safeCardStatus('warning', 'artifact_store')).toBe('warning');
  });

  it('preserves critical regardless of source', () => {
    expect(safeCardStatus('critical', 'stub_fallback')).toBe('critical');
  });
});
