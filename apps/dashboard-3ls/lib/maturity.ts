// D3L-MASTER-01 Phase 4 — maturity engine.
//
// Per-system maturity is derived from upstream artifacts; the dashboard
// never invents scores. Inputs:
//   * artifact presence (system_evidence_attachment.json)
//   * trust-gap signals (system_trust_gap_report.json) — covers
//     missing_eval / lineage / replay / observability / control / enforcement /
//     readiness / tests / schema_weakness
//   * priority freshness (recent recompute pipeline)
//
// Levels:
//   0 Unknown    — no evidence at all (or contract missing)
//   1 Emerging   — evidence present but several authority signals failing
//   2 Developing — only one of the structural signals failing
//   3 Stable     — no failing structural signals, but freshness or trust caution
//   4 Trusted    — no failing signals, fresh evidence, trust=ready

import type { D3LRegistryContract } from './systemRegistry';

export const MATURITY_LEVELS = {
  0: { id: 0, label: 'Unknown' },
  1: { id: 1, label: 'Emerging' },
  2: { id: 2, label: 'Developing' },
  3: { id: 3, label: 'Stable' },
  4: { id: 4, label: 'Trusted' },
} as const;

export type MaturityLevel = 0 | 1 | 2 | 3 | 4;
export type MaturityStatus = 'unknown' | 'fail-closed' | 'caution_signal' | 'ready_signal';

/**
 * Structural signals the engine inspects per system. The taxonomy comes
 * from system_trust_gap_report.signal_taxonomy. Anything in this list
 * counts toward the structural-signals score; non-structural signals
 * (e.g. missing_tests) flow through but don't downgrade structural.
 */
export const STRUCTURAL_SIGNALS = [
  'missing_eval',
  'missing_lineage',
  'missing_replay',
  'missing_observability',
  'missing_control',
  'missing_enforcement_signal',
  'missing_readiness_evidence',
] as const;

export type StructuralSignal = (typeof STRUCTURAL_SIGNALS)[number];

export interface MaturityRow {
  system_id: string;
  level: MaturityLevel;
  level_label: string;
  status: MaturityStatus;
  evidence_count: number;
  has_evidence: boolean;
  failing_signals: string[];
  failing_structural_signals: StructuralSignal[];
  trust_state: string;
  freshness_ok: boolean;
  key_gap: string;
  blocking_reasons: string[];
}

export interface MaturityReport {
  generated_at: string;
  status: 'ok' | 'fail-closed';
  blocking_reasons: string[];
  rows: MaturityRow[];
  /** universe size; equals the number of registry-active systems. */
  maturity_universe_size: number;
  /** Roll-up counts keyed by level. */
  level_counts: Record<MaturityLevel, number>;
  /** Caps applied because evidence was stale. */
  staleness_caps_applied: number;
  warnings: string[];
}

interface EvidenceRow {
  system_id: string;
  has_evidence: boolean;
  evidence_count: number;
}

interface TrustGapRow {
  system_id: string;
  trust_state: string;
  failing_signals: string[];
}

export interface MaturityInputs {
  contract: D3LRegistryContract | null;
  evidence: EvidenceRow[];
  trustGap: TrustGapRow[];
  priorityFresh: boolean;
  priorityGeneratedAt?: string | null;
  /** When we evaluate the report (default: now). */
  now?: Date;
}

function chooseKeyGap(failing: string[]): string {
  // Order signals by structural priority. The first match becomes the
  // operator-facing "key gap" — what to fix next.
  const order: string[] = [
    'missing_enforcement_signal',
    'missing_lineage',
    'missing_replay',
    'missing_observability',
    'missing_control',
    'missing_eval',
    'missing_readiness_evidence',
    'missing_tests',
    'schema_weakness',
  ];
  for (const sig of order) {
    if (failing.includes(sig)) return sig;
  }
  return failing[0] ?? 'no_recorded_gap';
}

function structuralLevel(opts: {
  hasEvidence: boolean;
  failingStructural: StructuralSignal[];
  trustState: string;
}): { level: MaturityLevel; status: MaturityStatus } {
  if (!opts.hasEvidence) return { level: 0, status: 'unknown' };
  const failing = opts.failingStructural.length;
  if (failing >= 3) return { level: 1, status: 'fail-closed' };
  if (failing >= 2) return { level: 1, status: 'caution_signal' };
  if (failing === 1) return { level: 2, status: 'caution_signal' };
  // No structural failures: trust decides.
  const trust = opts.trustState;
  if (trust === 'blocked_signal' || trust === 'freeze_signal') {
    return { level: 3, status: 'caution_signal' };
  }
  if (trust === 'caution_signal' || trust === 'warn') {
    return { level: 3, status: 'caution_signal' };
  }
  return { level: 4, status: 'ready_signal' };
}

/**
 * Build the maturity report. Returns fail-closed when contract or
 * inputs are missing — the dashboard surface must not invent rows.
 */
export function computeMaturityReport(inputs: MaturityInputs): MaturityReport {
  const blocking: string[] = [];
  const warnings: string[] = [];
  const now = (inputs.now ?? new Date()).toISOString();
  const counts: Record<MaturityLevel, number> = { 0: 0, 1: 0, 2: 0, 3: 0, 4: 0 };
  if (!inputs.contract) {
    blocking.push('contract_missing');
    return {
      generated_at: now,
      status: 'fail-closed',
      blocking_reasons: blocking,
      rows: [],
      maturity_universe_size: 0,
      level_counts: counts,
      staleness_caps_applied: 0,
      warnings,
    };
  }

  const evidenceById = new Map<string, EvidenceRow>(
    inputs.evidence.map((row) => [row.system_id, row]),
  );
  const trustById = new Map<string, TrustGapRow>(
    inputs.trustGap.map((row) => [row.system_id, row]),
  );

  let stalenessCaps = 0;
  const rows: MaturityRow[] = [];
  for (const sid of inputs.contract.maturity_universe) {
    const evidence = evidenceById.get(sid);
    const trust = trustById.get(sid);
    const hasEvidence = !!evidence?.has_evidence;
    const evidenceCount = evidence?.evidence_count ?? 0;
    const failingSignals = trust?.failing_signals ?? [];
    const failingStructural = failingSignals.filter((s): s is StructuralSignal =>
      (STRUCTURAL_SIGNALS as readonly string[]).includes(s),
    );
    const trustState = trust?.trust_state ?? 'unknown_signal';

    const computed = structuralLevel({
      hasEvidence,
      failingStructural,
      trustState,
    });

    // Staleness cap: if priority artifact is not fresh, no system can
    // exceed level 3, even with everything else green. The cap is
    // applied AFTER the structural decision so we still record why it
    // dropped.
    let level: MaturityLevel = computed.level;
    if (!inputs.priorityFresh && level === 4) {
      level = 3;
      stalenessCaps += 1;
    }
    const blockingForRow: string[] = [];
    if (!hasEvidence) blockingForRow.push('missing_evidence');
    if (failingStructural.length > 0) {
      blockingForRow.push(`structural_signals:${failingStructural.join(',')}`);
    }
    if (!inputs.priorityFresh) blockingForRow.push('priority_artifact_not_fresh');

    rows.push({
      system_id: sid,
      level,
      level_label: MATURITY_LEVELS[level].label,
      status: level === 4 ? 'ready_signal' : computed.status,
      evidence_count: evidenceCount,
      has_evidence: hasEvidence,
      failing_signals: failingSignals,
      failing_structural_signals: failingStructural,
      trust_state: trustState,
      freshness_ok: inputs.priorityFresh,
      key_gap: chooseKeyGap(failingSignals),
      blocking_reasons: blockingForRow,
    });
    counts[level] = (counts[level] ?? 0) + 1;
  }

  return {
    generated_at: now,
    status: 'ok',
    blocking_reasons: [],
    rows,
    maturity_universe_size: inputs.contract.maturity_universe.length,
    level_counts: counts,
    staleness_caps_applied: stalenessCaps,
    warnings,
  };
}
