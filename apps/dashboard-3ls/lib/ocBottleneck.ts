// D3L-DATA-REGISTRY-01 — OC bottleneck steering loader.
//
// OC-ALL-01 introduces operational closure and bottleneck steering
// artifacts. This loader is the dashboard's only entry point into those
// artifacts. It is fail-closed by design: when the artifact / schema /
// script is not present in the working tree, the loader returns
// state='unavailable' so the dashboard can surface "OC unavailable"
// instead of fabricating a bottleneck.
//
// This module never invents a bottleneck. It does not compute closure.
// It does not guess an owner.

import { loadArtifact } from './artifactLoader';

export type OcBottleneckState =
  | 'ok'
  | 'unavailable'
  | 'invalid_schema'
  | 'stale_proof'
  | 'conflict_proof'
  | 'ambiguous';

export interface OcBottleneckCard {
  /** Top-level category (e.g. eval_coverage, trust_handoff). */
  category: string;
  /** Owning system (registry-active id) or null when unknown. */
  owner_system: string | null;
  /** Reason code drawn from the OC artifact taxonomy. */
  reason_code: string;
  /** Evidence status: artifact-backed | partial | missing. */
  evidence_status: 'artifact_backed' | 'partial' | 'missing';
  /** One-line operator action. */
  next_safe_action: string;
  /** Optional warnings to surface (stale proof, conflict, ambiguous). */
  warnings: string[];
}

export interface OcBottleneckResult {
  state: OcBottleneckState;
  card: OcBottleneckCard | null;
  /** Reason text shown in the unavailable / fail-closed UI. */
  reason: string;
  /** Source artifact / script paths the loader consulted. */
  sources: string[];
}

const OC_BOTTLENECK_PATH = 'artifacts/operational_closure/oc_bottleneck_steering.json';
const OC_BUNDLE_PATH = 'artifacts/operational_closure/operational_closure_bundle.json';
const OC_SCHEMA_PATH = 'contracts/schemas/operational_closure_bundle.schema.json';

interface RawBottleneckArtifact {
  artifact_type?: string;
  generated_at?: string;
  bottleneck?: {
    category?: string;
    owner_system?: string | null;
    reason_code?: string;
    evidence_status?: 'artifact_backed' | 'partial' | 'missing';
    next_safe_action?: string;
    warnings?: string[];
    stale_proof?: boolean;
    conflict_proof?: boolean;
    ambiguous?: boolean;
  };
}

function isBottleneckArtifact(value: unknown): value is RawBottleneckArtifact {
  if (!value || typeof value !== 'object') return false;
  const obj = value as Record<string, unknown>;
  if (obj.artifact_type !== 'oc_bottleneck_steering') return false;
  if (!obj.bottleneck || typeof obj.bottleneck !== 'object') return false;
  return true;
}

/**
 * Load the OC bottleneck card.
 *
 * Fail-closed contract:
 *   * Artifact missing on disk → state='unavailable'.
 *   * Artifact present but does not match shape → state='invalid_schema'.
 *   * Artifact carries stale_proof/conflict_proof/ambiguous flags → those
 *     specific states, never silently rendered as ok.
 *   * Otherwise → state='ok' and a populated card.
 */
export function loadOcBottleneck(): OcBottleneckResult {
  const raw = loadArtifact<unknown>(OC_BOTTLENECK_PATH);
  if (!raw) {
    return {
      state: 'unavailable',
      card: null,
      reason: `OC bottleneck artifact not present: ${OC_BOTTLENECK_PATH}`,
      sources: [OC_BOTTLENECK_PATH, OC_BUNDLE_PATH, OC_SCHEMA_PATH],
    };
  }
  if (!isBottleneckArtifact(raw)) {
    return {
      state: 'invalid_schema',
      card: null,
      reason: `OC bottleneck artifact present but did not match shape (${OC_BOTTLENECK_PATH})`,
      sources: [OC_BOTTLENECK_PATH],
    };
  }
  const b = raw.bottleneck ?? {};
  const baseCard: OcBottleneckCard = {
    category: typeof b.category === 'string' ? b.category : 'unknown',
    owner_system: typeof b.owner_system === 'string' ? b.owner_system : null,
    reason_code: typeof b.reason_code === 'string' ? b.reason_code : 'unknown',
    evidence_status: b.evidence_status ?? 'missing',
    next_safe_action: typeof b.next_safe_action === 'string' ? b.next_safe_action : 'unknown',
    warnings: Array.isArray(b.warnings) ? b.warnings.filter((w): w is string => typeof w === 'string') : [],
  };
  if (b.stale_proof) {
    return {
      state: 'stale_proof',
      card: baseCard,
      reason: 'OC bottleneck proof is stale; dashboard refuses to surface it as actionable',
      sources: [OC_BOTTLENECK_PATH],
    };
  }
  if (b.conflict_proof) {
    return {
      state: 'conflict_proof',
      card: baseCard,
      reason: 'OC bottleneck proof conflicts with another OC artifact; dashboard refuses to pick a winner',
      sources: [OC_BOTTLENECK_PATH, OC_BUNDLE_PATH],
    };
  }
  if (b.ambiguous) {
    return {
      state: 'ambiguous',
      card: baseCard,
      reason: 'OC bottleneck proof is ambiguous; multiple categories or owners share evidence',
      sources: [OC_BOTTLENECK_PATH],
    };
  }
  return {
    state: 'ok',
    card: baseCard,
    reason: 'ok',
    sources: [OC_BOTTLENECK_PATH],
  };
}
