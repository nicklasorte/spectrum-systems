'use client';

import React, { useEffect, useState } from 'react';
import type { NextStepLoadResult } from '@/lib/nextStepArtifactLoader';

const loadingPayload: NextStepLoadResult = {
  state: 'missing',
  payload: {
    artifact_type: 'next_step_recommendation_report',
    schema_version: '1.0.0',
    generated_at: '',
    status: 'blocked',
    readiness_state: 'blocked',
    source_refs: [],
    completed_work: [],
    partial_work: [],
    remaining_work_table: [],
    ranked_priorities: [],
    selected_recommendation: null,
    rejected_next_steps: [],
    dependency_observations: [],
    red_team_findings: [],
    warnings: ['loading_next_step_artifact'],
    reason_codes: [],
  },
};

export function NextStepPanel() {
  const [result, setResult] = useState<NextStepLoadResult>(loadingPayload);

  useEffect(() => {
    fetch('/api/next-step')
      .then((res) => res.json())
      .then((payload: NextStepLoadResult) => {
        if (!payload || typeof payload !== 'object' || !('payload' in payload)) {
          throw new Error('invalid_next_step_payload');
        }
        setResult(payload);
      })
      .catch(() => {
        setResult({
          state: 'missing',
          payload: {
            ...loadingPayload.payload,
            warnings: ['next_step_fetch_failed'],
            reason_codes: ['missing_required_artifact:artifacts/next_step_recommendation_report.json'],
          },
        });
      });
  }, []);

  const selected = result.payload.selected_recommendation as Record<string, unknown> | null;
  const topFive = result.payload.ranked_priorities.slice(0, 5);
  const missing = result.payload.source_refs.filter((ref) => ref.required && !ref.present);

  return (
    <section className="bg-white border rounded p-4 space-y-3" data-testid="next-step-panel">
      <h2 className="font-semibold">Next Best Step</h2>
      {result.payload.status === 'blocked' && (
        <div className="text-sm text-red-700" data-testid="next-step-blocked">Next-step recommendation blocked</div>
      )}
      <div className="text-sm" data-testid="next-step-readiness">readiness_state: {result.payload.readiness_state}</div>
      {selected && (
        <div className="text-sm space-y-1" data-testid="next-step-selected">
          <div><strong>{String(selected.work_item ?? selected.id ?? 'unknown')}</strong></div>
          <div>{String(selected.why ?? '')}</div>
          <div>depends_on: {Array.isArray(selected.depends_on) ? selected.depends_on.join(', ') : 'none'}</div>
          <div>unlocks: {Array.isArray(selected.unlocks) ? selected.unlocks.join(', ') : 'none'}</div>
        </div>
      )}
      <div data-testid="next-step-top5" className="text-xs">
        <div className="font-medium">Top priorities</div>
        <ul>
          {topFive.map((row, idx) => (
            <li key={idx}>{String((row as { id?: string; work_item?: string }).id ?? '')}: {String((row as { work_item?: string }).work_item ?? '')}</li>
          ))}
        </ul>
      </div>
      <div className="text-xs" data-testid="next-step-rejected">
        <div className="font-medium">Rejected next steps</div>
        <ul>
          {result.payload.rejected_next_steps.map((row, idx) => (
            <li key={idx}>{String((row as { work_item?: string }).work_item ?? 'unknown')}: {String((row as { reason?: string }).reason ?? '')}</li>
          ))}
        </ul>
      </div>
      <div className="text-xs" data-testid="next-step-redteam">
        <div className="font-medium">Red-team findings</div>
        <ul>
          {result.payload.red_team_findings.map((row, idx) => (
            <li key={idx}>{String((row as { id?: string }).id ?? 'finding')}: {String((row as { finding?: string }).finding ?? '')}</li>
          ))}
        </ul>
      </div>
      <div className="text-xs" data-testid="next-step-reasons">reason_codes: {result.payload.reason_codes.join(', ') || 'none'}</div>
      {missing.length > 0 && (
        <div className="text-xs" data-testid="next-step-missing-sources">
          missing source_refs: {missing.map((ref) => ref.path).join(', ')}
        </div>
      )}
    </section>
  );
}
