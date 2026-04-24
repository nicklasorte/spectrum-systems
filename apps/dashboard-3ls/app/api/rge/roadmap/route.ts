import { NextRequest, NextResponse } from 'next/server';

export async function GET(_req: NextRequest) {
  try {
    const record = {
      artifact_type: 'rge_roadmap_record',
      schema_version: '1.0.0',
      record_id: 'RRM-LIVE-001',
      run_id: 'run-2026-04-24-live',
      trace_id: 'trace-live',
      created_at: new Date().toISOString(),
      analysis_record_id: 'ANA-TEST000001',
      context_maturity_level: 8,
      admitted_phases: [
        {
          phase_id: 'P1',
          phase_name: 'Wire EVL eval gate for RGE phases',
          admitted: true,
          block_gate: null,
          needs_rewrite: false,
          rewrite_gaps: [],
        },
        {
          phase_id: 'STRENGTHEN-EVL-00',
          phase_name: 'Strengthen EVL loop leg — resolve active drift',
          admitted: true,
          block_gate: null,
          needs_rewrite: false,
          rewrite_gaps: [],
        },
      ],
      blocked_phases: [
        {
          phase_id: 'VAGUE-01',
          phase_name: 'Improve things',
          admitted: false,
          block_gate: 'justification',
          block_reason: 'failure_prevented: missing',
          needs_rewrite: false,
        },
      ],
      needs_rewrite_phases: [
        {
          phase_id: 'P3',
          phase_name: 'Add monitoring',
          admitted: true,
          block_gate: null,
          needs_rewrite: true,
          rewrite_gaps: [
            'evidence_refs: missing or prose-only',
            'runbook: missing',
          ],
        },
      ],
      admitted_count: 2,
      blocked_count: 1,
      active_drift_legs: ['EVL'],
      rge_can_operate: true,
    };

    return NextResponse.json(record);
  } catch (error) {
    console.error('Error fetching roadmap:', error);
    return NextResponse.json({ error: 'Failed to fetch roadmap' }, { status: 500 });
  }
}
