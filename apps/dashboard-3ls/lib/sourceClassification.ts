import type { DataSource } from './types';
import { classifySignalSource } from './truthClassifier';

// DSH-08: Loader hardening.
//
// All API routes pass their loaded artifact map through this single helper so
// the data_source value is computed by one rule, not by ad-hoc per-route
// arithmetic. Routes must NOT compute data_source inline.

export interface ArtifactSlot {
  // Repo-relative path of the artifact this slot expects.
  path: string;
  // Whether the loader successfully loaded a parsed artifact.
  loaded: boolean;
  // Whether this slot is a repo registry rather than an artifact-store file.
  registry?: boolean;
}

export interface SourceEnvelope {
  data_source: DataSource;
  generated_at: string;
  source_artifacts_used: string[];
  warnings: string[];
}

export interface BuildEnvelopeArgs {
  slots: ArtifactSlot[];
  // True when the route's value is computed/aggregated rather than read
  // straight from a single artifact field.
  isComputed?: boolean;
  // Free-text warnings to surface alongside the loader-derived ones.
  warnings?: string[];
  // Override generated_at for deterministic tests.
  generatedAt?: string;
}

// Build the envelope every API route returns. Single rule, single helper.
export function buildSourceEnvelope(args: BuildEnvelopeArgs): SourceEnvelope {
  const { slots, isComputed = false, warnings = [], generatedAt } = args;

  const loadedSlots = slots.filter((s) => s.loaded);
  const registryBacked = loadedSlots.some((s) => s.registry === true);

  const data_source = classifySignalSource({
    expectedArtifacts: slots.length,
    loadedArtifacts: loadedSlots.length,
    registryBacked,
    isComputed,
  });

  const missingWarnings = slots
    .filter((s) => !s.loaded)
    .map((s) => `${s.path} unavailable; signals derived from this file will be marked unknown.`);

  return {
    data_source,
    generated_at: generatedAt ?? new Date().toISOString(),
    source_artifacts_used: loadedSlots.map((s) => s.path),
    warnings: [...warnings, ...missingWarnings],
  };
}
