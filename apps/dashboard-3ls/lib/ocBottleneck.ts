// D3L-DATA-REGISTRY-01 Phase 7 — OC bottleneck steering loader.
//
// Consumes the OC-ALL-01 governed artifacts:
//   * artifacts/operational_closure/dashboard_truth_projection.json
//     (preferred — schema dashboard_truth_projection v1.0.0;
//      the dashboard projection of the OC layer)
//   * artifacts/operational_closure/operational_closure_bundle.json
//     (fallback — schema operational_closure_bundle v1.0.0; richer
//      evidence refs but more refs the dashboard must thread)
//
// Schemas:
//   contracts/schemas/dashboard_truth_projection.schema.json
//   contracts/schemas/operational_closure_bundle.schema.json
//
// Fail-closed contract: when neither artifact is present, the loader
// returns state='unavailable' and the dashboard surfaces the unavailable
// reason. The dashboard NEVER fabricates a bottleneck. OC-ALL-01 is the
// authority; this loader is a non-owning view-only seam.

import { loadArtifact } from './artifactLoader';

export type OcBottleneckState =
  | 'ok'
  | 'unavailable'
  | 'invalid_schema'
  | 'stale_proof'
  | 'conflict_proof'
  | 'ambiguous';

export type OcOverallStatus = 'pass' | 'block' | 'freeze' | 'unknown';

export type OcBottleneckCategory =
  | 'eval'
  | 'replay'
  | 'lineage'
  | 'context_admission'
  | 'registry'
  | 'slo'
  | 'certification'
  | 'authority_shape'
  | 'dashboard'
  | 'unknown'
  | 'none';

export interface OcBottleneckCard {
  /** "pass" | "block" | "freeze" | "unknown". */
  overall_status: OcOverallStatus;
  /** OC-ALL-01 enum, e.g. eval / replay / lineage / registry / slo / ... */
  category: OcBottleneckCategory;
  /** OC-ALL-01 reason_code. Non-empty per schema. */
  reason_code: string;
  /** Owning 3-letter system or null when not yet determined. */
  owning_system: string | null;
  /** Operator action surfaced compactly on the dashboard. */
  next_safe_action: string;
  /** Source artifact: dashboard_truth_projection or operational_closure_bundle. */
  source_artifact_type: 'dashboard_truth_projection' | 'operational_closure_bundle';
  /** Optional warnings to surface (e.g. drifted alignment, stale freshness). */
  warnings: string[];
}

export interface OcBottleneckResult {
  state: OcBottleneckState;
  card: OcBottleneckCard | null;
  /** Reason text shown in the unavailable / fail-closed UI. */
  reason: string;
  /** Source artifact / schema paths the loader consulted. */
  sources: string[];
}

const PROJECTION_PATH = 'artifacts/operational_closure/dashboard_truth_projection.json';
const BUNDLE_PATH = 'artifacts/operational_closure/operational_closure_bundle.json';
const PROJECTION_SCHEMA = 'contracts/schemas/dashboard_truth_projection.schema.json';
const BUNDLE_SCHEMA = 'contracts/schemas/operational_closure_bundle.schema.json';

const CATEGORY_VALUES: ReadonlySet<string> = new Set([
  'eval',
  'replay',
  'lineage',
  'context_admission',
  'registry',
  'slo',
  'certification',
  'authority_shape',
  'dashboard',
  'unknown',
  'none',
]);
const STATUS_VALUES: ReadonlySet<string> = new Set(['pass', 'block', 'freeze', 'unknown']);
const FRESHNESS_VALUES: ReadonlySet<string> = new Set(['fresh', 'stale', 'unknown']);
const ALIGNMENT_VALUES: ReadonlySet<string> = new Set(['aligned', 'drifted', 'missing', 'corrupt', 'unknown']);

interface RawProjection {
  artifact_type?: string;
  schema_version?: string;
  current_status?: string;
  reason_code?: string;
  owning_system?: string | null;
  bottleneck_category?: string;
  next_safe_action?: string;
  freshness_status?: string;
  alignment_status?: string;
}

interface RawBundle {
  artifact_type?: string;
  schema_version?: string;
  overall_status?: string;
  current_bottleneck?: { category?: string; reason_code?: string };
  owning_system?: string | null;
  dashboard_alignment?: string;
  fast_trust_gate_sufficiency?: string;
  next_work_item?: { work_item_id?: string | null; selection_status?: string };
  justifying_signal_or_failure?: string;
}

function isProjection(value: unknown): value is RawProjection {
  if (!value || typeof value !== 'object') return false;
  const obj = value as Record<string, unknown>;
  if (obj.artifact_type !== 'dashboard_truth_projection') return false;
  if (typeof obj.current_status !== 'string' || !STATUS_VALUES.has(obj.current_status)) return false;
  if (typeof obj.reason_code !== 'string' || obj.reason_code.length === 0) return false;
  if (typeof obj.bottleneck_category !== 'string' || !CATEGORY_VALUES.has(obj.bottleneck_category)) return false;
  if (typeof obj.next_safe_action !== 'string' || obj.next_safe_action.length === 0) return false;
  if (typeof obj.freshness_status !== 'string' || !FRESHNESS_VALUES.has(obj.freshness_status)) return false;
  if (typeof obj.alignment_status !== 'string' || !ALIGNMENT_VALUES.has(obj.alignment_status)) return false;
  return true;
}

function isBundle(value: unknown): value is RawBundle {
  if (!value || typeof value !== 'object') return false;
  const obj = value as Record<string, unknown>;
  if (obj.artifact_type !== 'operational_closure_bundle') return false;
  if (typeof obj.overall_status !== 'string' || !STATUS_VALUES.has(obj.overall_status)) return false;
  if (typeof obj.dashboard_alignment !== 'string' || !ALIGNMENT_VALUES.has(obj.dashboard_alignment)) return false;
  const bn = obj.current_bottleneck as Record<string, unknown> | undefined;
  if (!bn || typeof bn !== 'object') return false;
  if (typeof bn.category !== 'string' || !CATEGORY_VALUES.has(bn.category as string)) return false;
  if (typeof bn.reason_code !== 'string' || (bn.reason_code as string).length === 0) return false;
  return true;
}

function projectionToCard(p: RawProjection): { card: OcBottleneckCard; warnings: string[] } {
  const warnings: string[] = [];
  if (p.alignment_status && p.alignment_status !== 'aligned') {
    warnings.push(`alignment_status=${p.alignment_status}`);
  }
  if (p.freshness_status && p.freshness_status !== 'fresh') {
    warnings.push(`freshness_status=${p.freshness_status}`);
  }
  return {
    card: {
      overall_status: (p.current_status ?? 'unknown') as OcOverallStatus,
      category: (p.bottleneck_category ?? 'unknown') as OcBottleneckCategory,
      reason_code: p.reason_code ?? 'unknown',
      owning_system: typeof p.owning_system === 'string' ? p.owning_system : null,
      next_safe_action: p.next_safe_action ?? 'unknown',
      source_artifact_type: 'dashboard_truth_projection',
      warnings,
    },
    warnings,
  };
}

function bundleToCard(b: RawBundle): { card: OcBottleneckCard; warnings: string[] } {
  const warnings: string[] = [];
  if (b.dashboard_alignment && b.dashboard_alignment !== 'aligned') {
    warnings.push(`dashboard_alignment=${b.dashboard_alignment}`);
  }
  if (b.fast_trust_gate_sufficiency && b.fast_trust_gate_sufficiency !== 'sufficient') {
    warnings.push(`fast_trust_gate_sufficiency=${b.fast_trust_gate_sufficiency}`);
  }
  const next = b.next_work_item ?? {};
  const nextSafeAction = next.work_item_id ?? next.selection_status ?? 'unknown';
  return {
    card: {
      overall_status: (b.overall_status ?? 'unknown') as OcOverallStatus,
      category: (b.current_bottleneck?.category ?? 'unknown') as OcBottleneckCategory,
      reason_code: b.current_bottleneck?.reason_code ?? 'unknown',
      owning_system: typeof b.owning_system === 'string' ? b.owning_system : null,
      next_safe_action: nextSafeAction,
      source_artifact_type: 'operational_closure_bundle',
      warnings,
    },
    warnings,
  };
}

/**
 * Decide the fail-closed state from card + raw artifact signals.
 *
 *   * freshness_status=stale or alignment_status=stale → stale_proof
 *   * alignment_status in {drifted, corrupt} or dashboard_alignment in
 *     {drifted, corrupt} → conflict_proof
 *   * alignment_status=missing or dashboard_alignment=missing →
 *     conflict_proof (the OC layer says its own evidence is missing)
 *   * category=unknown OR overall_status=unknown OR work_selection
 *     ambiguous → ambiguous
 *   * otherwise → ok
 */
function classifyState(
  card: OcBottleneckCard,
  signals: { freshness?: string; alignment?: string; selection?: string },
): OcBottleneckState {
  if (signals.freshness === 'stale') return 'stale_proof';
  if (signals.alignment === 'drifted' || signals.alignment === 'corrupt') return 'conflict_proof';
  if (signals.alignment === 'missing') return 'conflict_proof';
  if (card.overall_status === 'unknown') return 'ambiguous';
  if (card.category === 'unknown') return 'ambiguous';
  if (signals.selection === 'unknown') return 'ambiguous';
  return 'ok';
}

/**
 * Load the OC bottleneck card.
 *
 * Source order:
 *   1. dashboard_truth_projection (preferred)
 *   2. operational_closure_bundle (fallback)
 *
 * When neither artifact is present, returns state='unavailable'. When an
 * artifact loads but does not match its declared schema shape, returns
 * state='invalid_schema'. The OC layer's own self-reported drift is
 * surfaced via stale_proof / conflict_proof / ambiguous states so the
 * operator can never confuse "OC says blocked" with "OC's own evidence
 * is stale".
 */
export function loadOcBottleneck(): OcBottleneckResult {
  const projectionRaw = loadArtifact<unknown>(PROJECTION_PATH);
  if (projectionRaw) {
    if (!isProjection(projectionRaw)) {
      return {
        state: 'invalid_schema',
        card: null,
        reason: `OC dashboard truth projection present but did not match shape (${PROJECTION_PATH})`,
        sources: [PROJECTION_PATH, PROJECTION_SCHEMA],
      };
    }
    const { card } = projectionToCard(projectionRaw);
    const state = classifyState(card, {
      freshness: projectionRaw.freshness_status,
      alignment: projectionRaw.alignment_status,
    });
    return {
      state,
      card,
      reason: state === 'ok' ? 'ok' : `OC projection signals ${state}`,
      sources: [PROJECTION_PATH, PROJECTION_SCHEMA],
    };
  }

  const bundleRaw = loadArtifact<unknown>(BUNDLE_PATH);
  if (bundleRaw) {
    if (!isBundle(bundleRaw)) {
      return {
        state: 'invalid_schema',
        card: null,
        reason: `OC operational closure bundle present but did not match shape (${BUNDLE_PATH})`,
        sources: [BUNDLE_PATH, BUNDLE_SCHEMA],
      };
    }
    const { card } = bundleToCard(bundleRaw);
    const state = classifyState(card, {
      alignment: bundleRaw.dashboard_alignment,
      selection: bundleRaw.next_work_item?.selection_status,
    });
    return {
      state,
      card,
      reason: state === 'ok' ? 'ok' : `OC bundle signals ${state}`,
      sources: [BUNDLE_PATH, BUNDLE_SCHEMA],
    };
  }

  return {
    state: 'unavailable',
    card: null,
    reason: `OC artifacts not present: ${PROJECTION_PATH}, ${BUNDLE_PATH}`,
    sources: [PROJECTION_PATH, BUNDLE_PATH, PROJECTION_SCHEMA, BUNDLE_SCHEMA],
  };
}
