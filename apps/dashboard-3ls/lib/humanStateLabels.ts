// D3L-DATA-REGISTRY-01 — Human-readable trust state labels.
//
// Internal trust-state codes (e.g. blocked_signal, freeze_signal,
// caution_signal, trusted_signal, unknown_signal, degraded_signal) come
// from the governed TLS / graph pipelines. They MUST appear verbatim in
// diagnostics / inspector / raw-artifact views so the operator can trace
// signals back to their producing artifact, but they are confusing in
// the operator overview because they look like an internal enum.
//
// This module maps the internal code to a short operator label and a
// 1-line human description. The mapping is intentionally conservative —
// any unrecognised code falls through to "Unknown" rather than being
// renamed silently.

export type HumanTrustLabel =
  | 'Blocked'
  | 'Frozen'
  | 'Caution'
  | 'Ready'
  | 'Unknown';

export interface HumanTrustState {
  /** Operator-facing label. */
  label: HumanTrustLabel;
  /** 1-line description shown next to or under the label. */
  description: string;
  /** The raw code that the artifact emitted, for diagnostics. */
  raw: string;
  /** Tone classifier UI can use to choose colour. */
  tone: 'critical' | 'warning' | 'info' | 'ok';
}

const MAP: Record<string, { label: HumanTrustLabel; description: string; tone: HumanTrustState['tone'] }> = {
  // Blocked family.
  blocked_signal: { label: 'Blocked', description: 'control authority halted progression on this system', tone: 'critical' },
  blocked: { label: 'Blocked', description: 'control authority halted progression on this system', tone: 'critical' },

  // Frozen family.
  freeze_signal: { label: 'Frozen', description: 'control authority froze the system pending evidence', tone: 'critical' },
  freeze: { label: 'Frozen', description: 'control authority froze the system pending evidence', tone: 'critical' },
  frozen: { label: 'Frozen', description: 'control authority froze the system pending evidence', tone: 'critical' },

  // Caution family.
  caution_signal: { label: 'Caution', description: 'evidence is degraded; act only with care', tone: 'warning' },
  caution: { label: 'Caution', description: 'evidence is degraded; act only with care', tone: 'warning' },
  warning: { label: 'Caution', description: 'evidence is degraded; act only with care', tone: 'warning' },
  warn: { label: 'Caution', description: 'evidence is degraded; act only with care', tone: 'warning' },
  degraded_signal: { label: 'Caution', description: 'graph or eval evidence is partially degraded', tone: 'warning' },
  degraded: { label: 'Caution', description: 'graph or eval evidence is partially degraded', tone: 'warning' },

  // Ready family.
  trusted_signal: { label: 'Ready', description: 'evidence is current and authorities approve progression', tone: 'ok' },
  trusted: { label: 'Ready', description: 'evidence is current and authorities approve progression', tone: 'ok' },
  ready: { label: 'Ready', description: 'evidence is current and authorities approve progression', tone: 'ok' },
  pass: { label: 'Ready', description: 'evidence is current and authorities approve progression', tone: 'ok' },
  ready_signal: { label: 'Ready', description: 'evidence is current and authorities approve progression', tone: 'ok' },

  // Unknown family.
  unknown_signal: { label: 'Unknown', description: 'evidence is missing or insufficient to classify', tone: 'info' },
  unknown: { label: 'Unknown', description: 'evidence is missing or insufficient to classify', tone: 'info' },
  missing: { label: 'Unknown', description: 'no evidence available for this system', tone: 'info' },
  invalid: { label: 'Unknown', description: 'evidence is malformed or fails schema validation', tone: 'info' },
};

/**
 * Map an internal trust-state code to its operator-facing label.
 * Unrecognised codes return Unknown — the dashboard never silently
 * renames a state it does not understand.
 */
export function humanTrustState(rawInput: string | null | undefined): HumanTrustState {
  const raw = (rawInput ?? '').trim();
  if (!raw) {
    return { label: 'Unknown', description: 'evidence is missing or insufficient to classify', raw: '', tone: 'info' };
  }
  const lookup = MAP[raw.toLowerCase()];
  if (!lookup) {
    return { label: 'Unknown', description: `unrecognised trust state '${raw}' — falling back to Unknown`, raw, tone: 'info' };
  }
  return { ...lookup, raw };
}

/** Convenience accessor that returns just the label. */
export function humanTrustLabel(raw: string | null | undefined): HumanTrustLabel {
  return humanTrustState(raw).label;
}
