import { buildSourceEnvelope } from '@/lib/sourceClassification';

describe('buildSourceEnvelope (DSH-08 loader hardening)', () => {
  it('returns artifact_store when all slots loaded and not computed', () => {
    const env = buildSourceEnvelope({
      slots: [
        { path: 'a.json', loaded: true },
        { path: 'b.json', loaded: true },
      ],
    });
    expect(env.data_source).toBe('artifact_store');
    expect(env.source_artifacts_used).toEqual(['a.json', 'b.json']);
    expect(env.warnings).toEqual([]);
  });

  it('returns derived_estimate when computed with partial slots', () => {
    const env = buildSourceEnvelope({
      slots: [
        { path: 'a.json', loaded: true },
        { path: 'b.json', loaded: false },
      ],
      isComputed: true,
    });
    expect(env.data_source).toBe('derived_estimate');
    expect(env.source_artifacts_used).toEqual(['a.json']);
    expect(env.warnings.length).toBeGreaterThan(0);
  });

  it('returns derived when computed with all slots loaded', () => {
    const env = buildSourceEnvelope({
      slots: [{ path: 'a.json', loaded: true }],
      isComputed: true,
    });
    expect(env.data_source).toBe('derived');
  });

  it('returns stub_fallback when no slots loaded', () => {
    const env = buildSourceEnvelope({
      slots: [
        { path: 'a.json', loaded: false },
        { path: 'b.json', loaded: false },
      ],
    });
    expect(env.data_source).toBe('stub_fallback');
    expect(env.source_artifacts_used).toEqual([]);
  });

  it('emits a warning per missing slot', () => {
    const env = buildSourceEnvelope({
      slots: [
        { path: 'a.json', loaded: false },
        { path: 'b.json', loaded: true },
      ],
      isComputed: true,
    });
    expect(env.warnings.find((w) => w.includes('a.json'))).toBeDefined();
    expect(env.warnings.find((w) => w.includes('b.json'))).toBeUndefined();
  });

  it('passes upstream warnings through', () => {
    const env = buildSourceEnvelope({
      slots: [{ path: 'a.json', loaded: true }],
      warnings: ['signal-derived warning'],
    });
    expect(env.warnings).toContain('signal-derived warning');
  });

  it('returns repo_registry when all loaded slots are registry-backed', () => {
    const env = buildSourceEnvelope({
      slots: [{ path: 'docs/registry.md', loaded: true, registry: true }],
    });
    expect(env.data_source).toBe('repo_registry');
  });
});
