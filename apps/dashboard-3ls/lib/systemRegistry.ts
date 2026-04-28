// D3L-MASTER-01 Phase 0 — registry-aligned ranking/maturity helper.
//
// Single source of truth for which system_ids are eligible to appear in
// ranking and maturity surfaces. The registry contract artifact at
// artifacts/tls/d3l_registry_contract.json is canonical:
//   * active_system_ids ⇒ ranking_universe ⇒ maturity_universe
//   * future_system_ids, deprecated_or_merged_system_ids ⇒ excluded
//   * forbidden_node_examples (H01, TLS-BND-*, D3L-FIX-*, …) MUST never
//     become a graph node, ranking row, or maturity row.
//
// The dashboard never re-ranks or re-classifies. It reads upstream artifacts
// and filters them through this contract; anything outside the contract is
// a fail-closed signal back to the operator.

import { loadArtifact } from './artifactLoader';

export const D3L_REGISTRY_CONTRACT_PATH =
  'artifacts/tls/d3l_registry_contract.json';

export interface D3LRegistryContract {
  artifact_type: 'd3l_registry_contract';
  phase: string;
  schema_version: string;
  generated_at?: string;
  source_artifact: string;
  active_system_ids: string[];
  future_system_ids: string[];
  deprecated_or_merged_system_ids: string[];
  excluded_ids: string[];
  ranking_universe: string[];
  maturity_universe: string[];
  forbidden_node_examples: string[];
  rules: string[];
}

export interface RegistryAdmissionResult {
  admitted: string[];
  rejected_excluded: string[];
  rejected_forbidden: string[];
  rejected_unknown: string[];
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((v) => typeof v === 'string');
}

function isContract(value: unknown): value is D3LRegistryContract {
  if (!value || typeof value !== 'object') return false;
  const obj = value as Record<string, unknown>;
  if (obj.artifact_type !== 'd3l_registry_contract') return false;
  if (typeof obj.phase !== 'string') return false;
  if (!isStringArray(obj.active_system_ids)) return false;
  if (!isStringArray(obj.ranking_universe)) return false;
  if (!isStringArray(obj.maturity_universe)) return false;
  if (!isStringArray(obj.forbidden_node_examples)) return false;
  if (!isStringArray(obj.excluded_ids)) return false;
  return true;
}

/**
 * Load the canonical D3L registry contract artifact. Returns null when the
 * artifact is missing or malformed; callers MUST fail-closed in that case.
 */
export function loadD3LRegistryContract(): D3LRegistryContract | null {
  const payload = loadArtifact<unknown>(D3L_REGISTRY_CONTRACT_PATH);
  if (!isContract(payload)) return null;
  return payload;
}

/** Returns true iff system_id is in ranking_universe (= active_system_ids). */
export function isInRankingUniverse(
  contract: D3LRegistryContract | null,
  systemId: string,
): boolean {
  if (!contract) return false;
  return contract.ranking_universe.includes(systemId);
}

/** Returns true iff system_id is in maturity_universe (= active_system_ids). */
export function isInMaturityUniverse(
  contract: D3LRegistryContract | null,
  systemId: string,
): boolean {
  if (!contract) return false;
  return contract.maturity_universe.includes(systemId);
}

/** Returns true iff system_id appears in the forbidden examples list. */
export function isForbiddenNodeLabel(
  contract: D3LRegistryContract | null,
  systemId: string,
): boolean {
  if (!contract) return false;
  return contract.forbidden_node_examples.includes(systemId);
}

/**
 * Filter a candidate list against the registry contract. Used by the
 * dashboard ranking surface so future / deprecated / forbidden ids never
 * leak into Top 3 / Top 10 / All views.
 *
 * The order of `systemIds` is preserved for admitted entries. Each rejected
 * entry is bucketed by reason so the dashboard can surface "contract
 * filtered N entries" as a fail-closed operator signal.
 */
export function admitAgainstRegistry(
  contract: D3LRegistryContract | null,
  systemIds: ReadonlyArray<string>,
): RegistryAdmissionResult {
  const result: RegistryAdmissionResult = {
    admitted: [],
    rejected_excluded: [],
    rejected_forbidden: [],
    rejected_unknown: [],
  };
  if (!contract) {
    // Without a contract, we cannot admit anything. Treat every candidate
    // as unknown so the operator sees the missing-contract state instead
    // of a silently empty surface.
    result.rejected_unknown = Array.from(systemIds);
    return result;
  }
  const active = new Set(contract.active_system_ids);
  const excluded = new Set(contract.excluded_ids);
  const forbidden = new Set(contract.forbidden_node_examples);
  const seen = new Set<string>();
  for (const id of systemIds) {
    if (seen.has(id)) continue;
    seen.add(id);
    if (active.has(id)) {
      result.admitted.push(id);
      continue;
    }
    if (forbidden.has(id)) {
      result.rejected_forbidden.push(id);
      continue;
    }
    if (excluded.has(id)) {
      result.rejected_excluded.push(id);
      continue;
    }
    result.rejected_unknown.push(id);
  }
  return result;
}

/**
 * Convenience: filter raw rows by their system_id field through the
 * ranking universe and report the rejected ids alongside the admitted
 * rows. The order of admitted rows preserves the artifact ordering.
 */
export function filterRowsByRanking<T extends { system_id: string }>(
  contract: D3LRegistryContract | null,
  rows: ReadonlyArray<T>,
): { admitted: T[]; admission: RegistryAdmissionResult } {
  const admission = admitAgainstRegistry(contract, rows.map((r) => r.system_id));
  const admittedSet = new Set(admission.admitted);
  return {
    admitted: rows.filter((row) => admittedSet.has(row.system_id)),
    admission,
  };
}
