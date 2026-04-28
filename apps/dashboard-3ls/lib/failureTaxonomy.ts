// D3L-REGISTRY-01 — Failure taxonomy mapping.
//
// Translates raw system signals (missing artifact, missing eval, trace gap,
// schema mismatch, replay mismatch, policy mismatch) into a single canonical
// failure-taxonomy label that is shown in the inspector and root-cause view.
//
// The taxonomy is artifact-driven only. If no signal evidence is present we
// return 'unknown' — never a guess.

export type FailureTaxonomy =
  | 'missing_artifact'
  | 'missing_eval'
  | 'schema_violation'
  | 'trace_missing'
  | 'replay_mismatch'
  | 'policy_mismatch'
  | 'internal_error'
  | 'unknown'
  | 'none';

export interface FailureTaxonomyMappingEntry {
  taxonomy: FailureTaxonomy;
  description: string;
  evidence_signals: string[];
}

export const FAILURE_TAXONOMY_TABLE: ReadonlyArray<FailureTaxonomyMappingEntry> = [
  {
    taxonomy: 'missing_artifact',
    description: 'a required source artifact is absent on disk',
    evidence_signals: ['missing_artifact', 'source artifact missing', 'not_found'],
  },
  {
    taxonomy: 'missing_eval',
    description: 'a required eval is missing or has not produced evidence',
    evidence_signals: ['missing_eval', 'missing_required_eval', 'evidence_attachment_missing'],
  },
  {
    taxonomy: 'schema_violation',
    description: 'an artifact failed schema validation',
    evidence_signals: ['schema_weakness', 'shape_mismatch', 'schema_violation'],
  },
  {
    taxonomy: 'trace_missing',
    description: 'a trace or observability record is missing',
    evidence_signals: ['missing_observability', 'missing_trace', 'trace_gap'],
  },
  {
    taxonomy: 'replay_mismatch',
    description: 'replay integrity has not been confirmed for this system',
    evidence_signals: ['missing_replay', 'replay_mismatch'],
  },
  {
    taxonomy: 'policy_mismatch',
    description: 'a policy or trust-decision artifact is missing or inconsistent',
    evidence_signals: ['missing_control', 'missing_enforcement_signal', 'policy_mismatch'],
  },
  {
    taxonomy: 'internal_error',
    description: 'a producing script or API route reported an internal error',
    evidence_signals: ['internal_error'],
  },
];

const SIGNAL_TO_TAXONOMY: Map<string, FailureTaxonomy> = (() => {
  const m = new Map<string, FailureTaxonomy>();
  for (const entry of FAILURE_TAXONOMY_TABLE) {
    for (const signal of entry.evidence_signals) {
      m.set(signal.toLowerCase(), entry.taxonomy);
    }
  }
  return m;
})();

/**
 * Map a list of raw failing signals to the strongest (lowest-numbered)
 * failure taxonomy. If no signal matches, return 'unknown' to make the
 * unknown state explicit.
 */
export function mapSignalsToTaxonomy(signals: string[]): FailureTaxonomy {
  if (!signals || signals.length === 0) return 'none';
  for (const entry of FAILURE_TAXONOMY_TABLE) {
    for (const signal of signals) {
      if (!signal) continue;
      const lower = signal.toLowerCase();
      const direct = SIGNAL_TO_TAXONOMY.get(lower);
      if (direct === entry.taxonomy) return entry.taxonomy;
      if (entry.evidence_signals.some((s) => lower.includes(s.toLowerCase()))) {
        return entry.taxonomy;
      }
    }
  }
  return 'unknown';
}

/** Human-friendly label for a taxonomy value. */
export function taxonomyLabel(taxonomy: FailureTaxonomy): string {
  switch (taxonomy) {
    case 'missing_artifact':
      return 'missing artifact';
    case 'missing_eval':
      return 'missing eval';
    case 'schema_violation':
      return 'schema violation';
    case 'trace_missing':
      return 'trace missing';
    case 'replay_mismatch':
      return 'replay mismatch';
    case 'policy_mismatch':
      return 'policy mismatch';
    case 'internal_error':
      return 'internal error';
    case 'none':
      return 'no failure';
    case 'unknown':
    default:
      return 'unknown';
  }
}
