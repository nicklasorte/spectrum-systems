import React from 'react';
import type { PriorityArtifactLoadResult, RankedSystem, RequestedCandidateRow } from '@/lib/artifactLoader';
import { SourceBreadcrumbs } from './SourceBreadcrumbs';

interface Props {
  priority: PriorityArtifactLoadResult | null;
}

const PRIORITY_PATH = 'artifacts/system_dependency_priority_report.json';
const PRIORITY_SCHEMA_PATH = 'schemas/tls/system_dependency_priority_report.schema.json';
const PRODUCING_SCRIPT = 'python scripts/build_tls_dependency_priority.py --candidates H01,RFX,HOP,MET,METS --fail-if-missing';
const MISSING = 'Unknown / Missing';

function findRanked(payload: PriorityArtifactLoadResult['payload'], systemId: string): RankedSystem | null {
  if (!payload) return null;
  const all = (payload.global_ranked_systems ?? []).concat(payload.ranked_systems ?? []);
  return all.find((row) => row.system_id === systemId) ?? null;
}

function rowExplanation(row: RequestedCandidateRow, ranked: RankedSystem | null) {
  return {
    system_id: row.system_id,
    why_ranked_here: row.rank_explanation || MISSING,
    supporting_artifact: row.evidence_summary || MISSING,
    blocking_dependency: row.prerequisite_systems.length > 0 ? row.prerequisite_systems.join(', ') : 'none declared',
    safe_prompt_scope: row.minimum_safe_prompt_scope || MISSING,
    do_not_touch_boundary: row.risk_if_built_before_prerequisites || MISSING,
    next_prompt: ranked?.next_prompt ?? MISSING,
  };
}

export function RecommendationDebugPanel({ priority }: Props) {
  if (!priority || priority.state !== 'ok' || !priority.payload) {
    return (
      <div className="border border-slate-200 dark:border-slate-700 rounded p-3 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 space-y-2" data-testid="recommendation-debug-panel">
        <h3 className="font-semibold">Recommendation Debug</h3>
        <p className="text-sm text-red-700 dark:text-red-300" data-testid="recommendation-debug-fail-closed">
          ⚠ Priority artifact unavailable; recommendation explanations cannot be shown. Fail-closed: dashboard
          will not synthesise rankings.
        </p>
      </div>
    );
  }

  const rows = priority.payload.requested_candidate_ranking ?? [];
  const top = rows.slice(0, 3);

  return (
    <div className="border border-slate-200 dark:border-slate-700 rounded p-3 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 space-y-2" data-testid="recommendation-debug-panel">
      <h3 className="font-semibold">Recommendation Debug (artifact-backed only)</h3>
      <p className="text-xs text-slate-600 dark:text-slate-300">
        Rankings are read directly from artifact; the dashboard does not compute order or score.
      </p>
      <ul className="space-y-2">
        {top.map((row) => {
          const ranked = findRanked(priority.payload, row.system_id);
          const data = rowExplanation(row, ranked);
          return (
            <li
              key={row.system_id}
              className="border rounded p-2 text-sm"
              data-testid={`rec-debug-card-${row.system_id}`}
            >
              <p>
                <strong>system_id:</strong> {data.system_id}
              </p>
              <p data-testid={`rec-debug-why-${row.system_id}`}>
                <strong>why ranked here:</strong> {data.why_ranked_here}
              </p>
              <p data-testid={`rec-debug-support-${row.system_id}`}>
                <strong>supporting artifact:</strong> {data.supporting_artifact}
              </p>
              <p data-testid={`rec-debug-block-${row.system_id}`}>
                <strong>blocking dependency:</strong> {data.blocking_dependency}
              </p>
              <p data-testid={`rec-debug-scope-${row.system_id}`}>
                <strong>safe prompt scope:</strong> {data.safe_prompt_scope}
              </p>
              <p data-testid={`rec-debug-boundary-${row.system_id}`}>
                <strong>do-not-touch boundary:</strong> {data.do_not_touch_boundary}
              </p>
              <p data-testid={`rec-debug-next-${row.system_id}`}>
                <strong>next bundle / prompt:</strong> {data.next_prompt}
              </p>
              <SourceBreadcrumbs
                artifactPaths={[PRIORITY_PATH]}
                schemaPaths={[PRIORITY_SCHEMA_PATH]}
                producingScript={PRODUCING_SCRIPT}
                lastValidated={priority.generated_at ?? null}
                testid={`rec-debug-breadcrumbs-${row.system_id}`}
              />
            </li>
          );
        })}
      </ul>
    </div>
  );
}
