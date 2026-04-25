import {
  classifySignalSource,
  aggregateDataSource,
  confidenceFor,
  dataSourceAllowsHealthy,
} from '@/lib/truthClassifier';

describe('classifySignalSource', () => {
  it('returns artifact_store when all expected artifacts loaded and not computed', () => {
    expect(classifySignalSource({ expectedArtifacts: 3, loadedArtifacts: 3 })).toBe(
      'artifact_store'
    );
  });

  it('returns repo_registry when registry-backed and not computed', () => {
    expect(
      classifySignalSource({
        expectedArtifacts: 1,
        loadedArtifacts: 1,
        registryBacked: true,
      })
    ).toBe('repo_registry');
  });

  it('returns derived when fully loaded and computed', () => {
    expect(
      classifySignalSource({ expectedArtifacts: 3, loadedArtifacts: 3, isComputed: true })
    ).toBe('derived');
  });

  it('returns derived_estimate when computed with partial artifacts', () => {
    expect(
      classifySignalSource({ expectedArtifacts: 3, loadedArtifacts: 1, isComputed: true })
    ).toBe('derived_estimate');
  });

  it('returns stub_fallback when nothing loaded', () => {
    expect(classifySignalSource({ expectedArtifacts: 3, loadedArtifacts: 0 })).toBe(
      'stub_fallback'
    );
  });

  it('returns stub_fallback when isStub explicitly set', () => {
    expect(
      classifySignalSource({ expectedArtifacts: 3, loadedArtifacts: 3, isStub: true })
    ).toBe('stub_fallback');
  });

  it('returns unknown when nothing expected and nothing loaded', () => {
    expect(classifySignalSource({ expectedArtifacts: 0, loadedArtifacts: 0 })).toBe('unknown');
  });
});

describe('aggregateDataSource', () => {
  it('aggregates artifact_store when all sources agree', () => {
    expect(aggregateDataSource(['artifact_store', 'artifact_store'])).toBe('artifact_store');
  });

  it('downgrades to derived_estimate when any input is provisional', () => {
    expect(aggregateDataSource(['artifact_store', 'derived_estimate'])).toBe('derived_estimate');
  });

  it('downgrades to stub_fallback when any input is a stub', () => {
    expect(aggregateDataSource(['artifact_store', 'stub_fallback'])).toBe('stub_fallback');
  });

  it('returns unknown if any source is unknown', () => {
    expect(aggregateDataSource(['artifact_store', 'unknown'])).toBe('unknown');
  });

  it('returns unknown for empty list', () => {
    expect(aggregateDataSource([])).toBe('unknown');
  });

  it('treats all-registry as repo_registry', () => {
    expect(aggregateDataSource(['repo_registry', 'repo_registry'])).toBe('repo_registry');
  });
});

describe('confidenceFor', () => {
  it('assigns 1.0 for artifact_store and repo_registry', () => {
    expect(confidenceFor('artifact_store')).toBe(1.0);
    expect(confidenceFor('repo_registry')).toBe(1.0);
  });

  it('assigns less than 1 for derived sources', () => {
    expect(confidenceFor('derived')).toBeLessThan(1);
    expect(confidenceFor('derived_estimate')).toBeLessThan(confidenceFor('derived'));
  });

  it('assigns near zero for stub and unknown', () => {
    expect(confidenceFor('stub_fallback')).toBeLessThanOrEqual(0.2);
    expect(confidenceFor('unknown')).toBe(0);
  });
});

describe('dataSourceAllowsHealthy', () => {
  it('allows healthy for artifact_store, repo_registry, derived', () => {
    expect(dataSourceAllowsHealthy('artifact_store')).toBe(true);
    expect(dataSourceAllowsHealthy('repo_registry')).toBe(true);
    expect(dataSourceAllowsHealthy('derived')).toBe(true);
  });

  it('forbids healthy for derived_estimate, stub_fallback, unknown', () => {
    expect(dataSourceAllowsHealthy('derived_estimate')).toBe(false);
    expect(dataSourceAllowsHealthy('stub_fallback')).toBe(false);
    expect(dataSourceAllowsHealthy('unknown')).toBe(false);
  });
});
