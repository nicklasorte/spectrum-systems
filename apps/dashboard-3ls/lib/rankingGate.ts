import type { PriorityArtifactLoadResult } from '@/lib/artifactLoader';

export interface RankingBlockDecision {
  blocked: boolean;
  reason: string;
  recompute_command: string;
}

const DEFAULT_RECOMPUTE = 'python scripts/build_tls_dependency_priority.py --candidates HOP,RAX,RSM,CAP,SEC,EVL,OBS,SLO --fail-if-missing && python scripts/build_dashboard_3ls_with_tls.py --skip-next-build';

export function getRankingBlockDecision(priority: PriorityArtifactLoadResult | null | undefined): RankingBlockDecision {
  const gate = (priority as unknown as { freshness_gate?: { ok?: boolean; status?: string; recompute_command?: string; blocking_reasons?: string[] } } | null)?.freshness_gate;
  const loaderState = priority?.state ?? 'missing';
  const hardBlocked = loaderState !== 'ok';
  const missingGate = !gate;
  const gateBlocked = gate ? gate.ok !== true : false;
  const blocked = hardBlocked || missingGate || gateBlocked;
  const recompute = gate?.recompute_command ?? priority?.recompute_command ?? DEFAULT_RECOMPUTE;

  if (!blocked) {
    return { blocked: false, reason: 'freshness_gate_ok', recompute_command: recompute };
  }
  const reason = hardBlocked
    ? `priority_state:${loaderState}${priority?.reason ? `:${priority.reason}` : ''}`
    : missingGate
      ? 'freshness_gate_missing'
      : `freshness_gate_blocked:${gate?.status ?? 'unknown'}${gate?.blocking_reasons?.length ? `:${gate.blocking_reasons.join(',')}` : ''}`;
  return { blocked: true, reason, recompute_command: recompute };
}
