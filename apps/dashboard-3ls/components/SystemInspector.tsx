import React from 'react';
import type { SystemGraphNode } from '@/lib/systemGraph';
import { deriveDebugStatus } from '@/lib/systemGraph';
import { SourceBreadcrumbs } from './SourceBreadcrumbs';

interface Props {
  node: SystemGraphNode | null;
  replayCommands: string[];
}

const MISSING = 'Unknown / Missing';

function listOrMissing(items: string[] | undefined | null): string {
  if (!items || items.length === 0) return MISSING;
  return items.join(', ');
}

const STATUS_COLORS: Record<string, string> = {
  OK: 'bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-900 dark:text-emerald-200 dark:border-emerald-700',
  MISSING: 'bg-red-100 text-red-800 border-red-300 dark:bg-red-900 dark:text-red-200 dark:border-red-700',
  STALE: 'bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-900 dark:text-amber-200 dark:border-amber-700',
  FAILED: 'bg-orange-100 text-orange-800 border-orange-300 dark:bg-orange-900 dark:text-orange-200 dark:border-orange-700',
  FALLBACK: 'bg-yellow-100 text-yellow-800 border-yellow-300 dark:bg-yellow-900 dark:text-yellow-200 dark:border-yellow-700',
  BLOCKING: 'bg-red-200 text-red-900 border-red-400 dark:bg-red-950 dark:text-red-200 dark:border-red-700',
  UNKNOWN: 'bg-slate-100 text-slate-700 border-slate-300 dark:bg-slate-800 dark:text-slate-200 dark:border-slate-600',
};

export function SystemInspector({ node, replayCommands }: Props) {
  if (!node) {
    return (
      <div className="border dark:border-slate-700 rounded p-3 text-sm text-gray-600 dark:text-slate-300 bg-white dark:bg-slate-900" data-testid="system-inspector">
        Select a node to investigate.
      </div>
    );
  }

  const status = node.debug_status ?? deriveDebugStatus(node);
  const statusClass = STATUS_COLORS[status] ?? STATUS_COLORS.UNKNOWN;
  const debuggerComplete =
    !!node.system_id &&
    !!node.last_recompute &&
    (node.source_artifact_refs?.length ?? 0) > 0;
  const downstreamDependents = node.downstream_dependents ?? node.downstream;

  return (
    <div className="border dark:border-slate-700 rounded p-3 text-sm space-y-2 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100" data-testid="system-inspector">
      <header className="flex items-center justify-between gap-2">
        <h3 className="font-semibold">Investigate: {node.system_id}</h3>
        <span
          className={`text-xs px-2 py-0.5 rounded border ${statusClass}`}
          data-testid="inspector-status"
          data-status={status}
        >
          {status}
        </span>
      </header>

      {!debuggerComplete && (
        <p className="text-xs text-red-700 dark:text-red-300" data-testid="inspector-fail-closed-warning">
          ⚠ Debugger data incomplete; fields below may show Unknown / Missing.
        </p>
      )}

      <dl className="grid grid-cols-1 gap-y-1">
        <div data-testid="inspector-why-blocked">
          <dt className="font-medium">why blocked:</dt>
          <dd>{node.why_blocked ?? (status === 'OK' ? 'not blocked' : MISSING)}</dd>
        </div>
        <div data-testid="inspector-missing-artifacts">
          <dt className="font-medium">missing artifacts:</dt>
          <dd>{listOrMissing(node.missing_artifacts)}</dd>
        </div>
        <div data-testid="inspector-failed-evals">
          <dt className="font-medium">failed evals:</dt>
          <dd>{listOrMissing(node.failed_evals)}</dd>
        </div>
        <div data-testid="inspector-trace-gaps">
          <dt className="font-medium">trace gaps:</dt>
          <dd>{listOrMissing(node.trace_gaps)}</dd>
        </div>
        <div data-testid="inspector-upstream-blockers">
          <dt className="font-medium">upstream blockers:</dt>
          <dd>{listOrMissing(node.upstream_blockers)}</dd>
        </div>
        <div data-testid="inspector-downstream-dependents">
          <dt className="font-medium">downstream dependents:</dt>
          <dd>{listOrMissing(downstreamDependents)}</dd>
        </div>
        <div data-testid="inspector-last-recompute">
          <dt className="font-medium">last recompute:</dt>
          <dd>{node.last_recompute ?? MISSING}</dd>
        </div>
      </dl>

      <p className="text-xs text-gray-600 dark:text-slate-300">
        minimum safe prompt scope: recommendation: single-system hardening for {node.system_id} trust-gap signals.
      </p>

      <SourceBreadcrumbs
        artifactPaths={node.source_artifact_refs}
        schemaPaths={node.schema_paths}
        producingScript={node.producing_script}
        lastValidated={node.last_recompute}
        testid="inspector-breadcrumbs"
      />

      <p className="text-xs text-gray-500 dark:text-slate-400">replay command refs: {replayCommands.join(' | ')}</p>
    </div>
  );
}
