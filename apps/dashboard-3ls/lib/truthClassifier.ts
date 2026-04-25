import type { DataSource } from './types';

// DSH-03: Truth-first dashboard audit helper.
//
// Single, authoritative classifier for every dashboard signal. Routes,
// loaders, and components must call this helper instead of hand-rolling
// data_source strings — that is the only way "no green without source"
// can be enforced consistently across the cockpit.

export interface ClassifyArgs {
  // Total number of upstream artifact slots the signal expects.
  expectedArtifacts: number;
  // Number of artifact slots actually loaded.
  loadedArtifacts: number;
  // True when at least one loaded source is a canonical repo registry file
  // (e.g. system_registry.md, package boundaries) rather than an artifact.
  registryBacked?: boolean;
  // True when the value is computed/aggregated rather than read directly.
  isComputed?: boolean;
  // True when we know the underlying source is a placeholder/static stub
  // even though the loader returned data.
  isStub?: boolean;
}

// Classify a single signal's provenance.
//
// Decision order matters; this function is the single source of truth:
//   stub                                          -> stub_fallback
//   nothing loaded                                -> stub_fallback (or unknown if expected==0)
//   loaded < expected and computed                -> derived_estimate
//   loaded == expected and computed               -> derived
//   registry-backed                               -> repo_registry
//   loaded == expected and not computed           -> artifact_store
//   anything else                                 -> unknown
export function classifySignalSource(args: ClassifyArgs): DataSource {
  const {
    expectedArtifacts,
    loadedArtifacts,
    registryBacked = false,
    isComputed = false,
    isStub = false,
  } = args;

  if (isStub) return 'stub_fallback';

  if (expectedArtifacts === 0 && loadedArtifacts === 0 && !registryBacked) {
    return 'unknown';
  }

  if (loadedArtifacts === 0 && !registryBacked) return 'stub_fallback';

  if (loadedArtifacts < expectedArtifacts) {
    // Partial artifact coverage. If the signal is computed from partial
    // inputs it is a derived_estimate (provisional). Otherwise the value
    // itself is incomplete and treated as derived (with warnings) — but
    // computed values dominate when both apply.
    return isComputed ? 'derived_estimate' : 'derived';
  }

  // From here loadedArtifacts >= expectedArtifacts.
  if (registryBacked && !isComputed) return 'repo_registry';
  if (isComputed) return 'derived';
  if (loadedArtifacts > 0) return 'artifact_store';

  return 'unknown';
}

// Aggregate per-source classifications for an envelope-level data_source.
// Used by API routes to summarize the response across multiple signals.
//
// Aggregation is conservative — the worst provenance wins:
//   any unknown               -> unknown
//   any stub_fallback         -> stub_fallback
//   any derived_estimate      -> derived_estimate
//   any derived               -> derived
//   all artifact_store/repo_registry mix -> if all repo_registry -> repo_registry, else artifact_store
export function aggregateDataSource(sources: DataSource[]): DataSource {
  if (sources.length === 0) return 'unknown';
  if (sources.includes('unknown')) return 'unknown';
  if (sources.includes('stub_fallback')) return 'stub_fallback';
  if (sources.includes('derived_estimate')) return 'derived_estimate';
  if (sources.includes('derived')) return 'derived';
  if (sources.every((s) => s === 'repo_registry')) return 'repo_registry';
  return 'artifact_store';
}

// Confidence floor implied by a given data_source.
// Used by signal builders that don't track per-signal confidence directly.
export function confidenceFor(ds: DataSource): number {
  switch (ds) {
    case 'artifact_store':
    case 'repo_registry':
      return 1.0;
    case 'derived':
      return 0.85;
    case 'derived_estimate':
      return 0.5;
    case 'stub_fallback':
      return 0.1;
    case 'unknown':
      return 0;
  }
}

// Whether the given data_source is allowed to render a healthy/green status
// without further evidence. The runtime check that backs DSH-04.
export function dataSourceAllowsHealthy(ds: DataSource): boolean {
  return ds === 'artifact_store' || ds === 'repo_registry' || ds === 'derived';
}
