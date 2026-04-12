export type NormalizedStatus = 'allow' | 'warn' | 'freeze' | 'block' | 'pass' | 'failed' | 'unknown_blocked'

const DECISION_STATUS_MAP: Record<string, Exclude<NormalizedStatus, 'unknown_blocked'>> = {
  allow: 'allow',
  warn: 'warn',
  freeze: 'freeze',
  block: 'block',
  pass: 'pass',
  failed: 'failed',
  fail: 'failed',
  ready: 'pass',
  blocked: 'block',
  fresh: 'pass',
  stale: 'block',
  success: 'pass'
}

export function normalizeDecisionStatus(raw: unknown): NormalizedStatus {
  if (typeof raw !== 'string') return 'unknown_blocked'
  const normalized = DECISION_STATUS_MAP[raw.trim().toLowerCase()]
  return normalized ?? 'unknown_blocked'
}
