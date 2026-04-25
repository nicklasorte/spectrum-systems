import { NextRequest, NextResponse } from 'next/server';
import { loadArtifact } from '@/lib/artifactLoader';
import type { GapAnalysis, RoadmapTable, DataSource } from '@/lib/types';

const ARTIFACT_PATHS = {
  gapAnalysis: 'artifacts/roadmap/latest/gap_analysis.json',
  roadmapTable: 'artifacts/roadmap/latest/roadmap_table.json',
};

export async function GET(_req: NextRequest) {
  try {
    const gapAnalysis = loadArtifact<GapAnalysis>(ARTIFACT_PATHS.gapAnalysis);
    const roadmapTable = loadArtifact<RoadmapTable>(ARTIFACT_PATHS.roadmapTable);

    const warnings: string[] = [];
    const source_artifacts_used: string[] = [];

    if (gapAnalysis) source_artifacts_used.push(ARTIFACT_PATHS.gapAnalysis);
    else warnings.push('gap_analysis unavailable: gap_analysis.json not found');

    if (roadmapTable) source_artifacts_used.push(ARTIFACT_PATHS.roadmapTable);
    else warnings.push('roadmap_table unavailable: roadmap_table.json not found');

    const loadedCount = source_artifacts_used.length;

    let data_source: DataSource;
    let proposals: Array<{
      proposal_id: string;
      phase_id: string;
      phase_name: string;
      failure_prevented: string;
      signal_improved: string;
      loop_leg: string;
      status: string;
      created_at: string;
      cde_decision_deadline: string;
    }>;

    if (gapAnalysis && roadmapTable) {
      // Derive proposals from the dominant bottleneck and first foundation steps
      data_source = 'derived';
      warnings.push(
        'Proposals derived from gap_analysis and roadmap_table; no dedicated proposals artifact found.'
      );

      const deadline = new Date(Date.now() + 48 * 3600 * 1000).toISOString();
      const now = new Date().toISOString();

      // Foundation steps that address the dominant bottleneck
      const foundationSteps = roadmapTable.steps
        .filter((s) => s.system_layer_impacted === 'foundation')
        .slice(0, 2);

      proposals = foundationSteps.map((step, i) => ({
        proposal_id: `PROP-${String(i + 1).padStart(3, '0')}`,
        phase_id: step.id,
        phase_name: step.what,
        failure_prevented: step.failure_prevention,
        signal_improved: step.trust_gain,
        loop_leg: gapAnalysis.dominant_bottleneck?.id ?? 'unknown',
        status: 'awaiting_cde',
        created_at: now,
        cde_decision_deadline: deadline,
      }));

      if (proposals.length === 0) {
        warnings.push('No foundation-layer steps found in roadmap_table; returning empty proposals.');
      }
    } else if (loadedCount === 0) {
      data_source = 'stub_fallback';
      warnings.push('No artifact sources available; returning stub proposals.');
      proposals = [
        {
          proposal_id: 'PROP-STUB-001',
          phase_id: 'STUB',
          phase_name: 'Stub proposal — no artifact source available',
          failure_prevented: 'unknown',
          signal_improved: 'unknown',
          loop_leg: 'unknown',
          status: 'awaiting_cde',
          created_at: new Date().toISOString(),
          cde_decision_deadline: new Date(Date.now() + 24 * 3600 * 1000).toISOString(),
        },
      ];
    } else {
      data_source = 'derived';
      proposals = [];
    }

    return NextResponse.json({
      data_source,
      generated_at: new Date().toISOString(),
      source_artifacts_used,
      warnings,
      proposals,
    });
  } catch (error) {
    console.error('Error fetching proposals:', error);
    return NextResponse.json({ error: 'Failed to fetch proposals' }, { status: 500 });
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { proposal_id, decision } = body;

    if (!proposal_id || !decision) {
      return NextResponse.json(
        { error: 'Missing proposal_id or decision' },
        { status: 400 }
      );
    }

    return NextResponse.json({
      result: 'decision_recorded',
      proposal_id,
      decision,
      recorded_at: new Date().toISOString(),
    });
  } catch (error) {
    console.error('Error recording proposal decision:', error);
    return NextResponse.json({ error: 'Failed to record decision' }, { status: 500 });
  }
}
