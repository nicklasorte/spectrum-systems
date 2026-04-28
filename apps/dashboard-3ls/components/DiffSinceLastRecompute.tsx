import React, { useMemo } from 'react';
import type { SystemGraphPayload, SystemGraphNode } from '@/lib/systemGraph';
import { deriveDebugStatus } from '@/lib/systemGraph';

interface Props {
  current: SystemGraphPayload | null;
  previous: SystemGraphPayload | null;
  recomputeStatus?: string | null;
}

const BLOCKING_STATUSES: ReadonlySet<string> = new Set(['MISSING', 'STALE', 'FAILED', 'FALLBACK', 'BLOCKING']);

function statusOf(node: SystemGraphNode): string {
  return node.debug_status ?? deriveDebugStatus(node);
}

function blockerSet(graph: SystemGraphPayload | null): Set<string> {
  if (!graph) return new Set();
  return new Set(graph.nodes.filter((n) => BLOCKING_STATUSES.has(statusOf(n))).map((n) => n.system_id));
}

function staleSet(graph: SystemGraphPayload | null): Set<string> {
  if (!graph) return new Set();
  return new Set(graph.nodes.filter((n) => statusOf(n) === 'STALE').map((n) => n.system_id));
}

function missingSet(graph: SystemGraphPayload | null): Set<string> {
  if (!graph) return new Set();
  return new Set(graph.nodes.filter((n) => statusOf(n) === 'MISSING').map((n) => n.system_id));
}

function rankingSet(graph: SystemGraphPayload | null): string[] {
  if (!graph) return [];
  return graph.focus_systems ?? [];
}

function diff(a: Set<string>, b: Set<string>): string[] {
  const out: string[] = [];
  a.forEach((value) => {
    if (!b.has(value)) out.push(value);
  });
  return out.sort();
}

export function DiffSinceLastRecompute({ current, previous, recomputeStatus }: Props) {
  const noPrevious = !previous;

  const result = useMemo(() => {
    if (noPrevious || !current) return null;
    const prevBlockers = blockerSet(previous);
    const curBlockers = blockerSet(current);
    const prevStale = staleSet(previous);
    const curStale = staleSet(current);
    const prevMissing = missingSet(previous);
    const curMissing = missingSet(current);
    const prevRanking = rankingSet(previous);
    const curRanking = rankingSet(current);
    const rankingChanged =
      prevRanking.length !== curRanking.length ||
      prevRanking.some((id, idx) => curRanking[idx] !== id);
    return {
      newBlockers: diff(curBlockers, prevBlockers),
      resolvedBlockers: diff(prevBlockers, curBlockers),
      newStale: diff(curStale, prevStale),
      newMissing: diff(curMissing, prevMissing),
      rankingChanged,
      rankingBefore: prevRanking,
      rankingAfter: curRanking,
    };
  }, [current, previous, noPrevious]);

  return (
    <div className="border rounded p-3 bg-white text-sm space-y-1" data-testid="diff-since-last-recompute">
      <h3 className="font-semibold">Diff Since Last Recompute</h3>
      {noPrevious || !current ? (
        <p className="text-gray-600" data-testid="diff-no-snapshot">
          No previous snapshot available.
        </p>
      ) : (
        <ul className="space-y-0.5 text-xs">
          <li data-testid="diff-new-blockers">
            new blockers: {result?.newBlockers.length ? result.newBlockers.join(', ') : 'none'}
          </li>
          <li data-testid="diff-resolved-blockers">
            resolved blockers: {result?.resolvedBlockers.length ? result.resolvedBlockers.join(', ') : 'none'}
          </li>
          <li data-testid="diff-ranking-changes">
            ranking changes: {result?.rankingChanged
              ? `${result.rankingBefore.join(' / ')} → ${result.rankingAfter.join(' / ')}`
              : 'no change'}
          </li>
          <li data-testid="diff-stale-artifacts">
            stale artifacts: {result?.newStale.length ? result.newStale.join(', ') : 'none new'}
          </li>
          <li data-testid="diff-missing-artifacts">
            missing artifacts: {result?.newMissing.length ? result.newMissing.join(', ') : 'none new'}
          </li>
          <li data-testid="diff-recompute-status">recompute status: {recomputeStatus ?? 'unknown'}</li>
        </ul>
      )}
    </div>
  );
}
