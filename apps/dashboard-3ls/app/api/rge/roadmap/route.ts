import { NextRequest, NextResponse } from 'next/server';
import { loadArtifact } from '@/lib/artifactLoader';
import { buildSourceEnvelope } from '@/lib/sourceClassification';
import type { RoadmapTable, GapAnalysis, SystemState } from '@/lib/types';

const ARTIFACT_PATHS = {
  roadmapTable: 'artifacts/roadmap/latest/roadmap_table.json',
  gapAnalysis: 'artifacts/roadmap/latest/gap_analysis.json',
  systemState: 'artifacts/roadmap/latest/system_state.json',
};

export async function GET(_req: NextRequest) {
  try {
    const roadmapTable = loadArtifact<RoadmapTable>(ARTIFACT_PATHS.roadmapTable);
    const gapAnalysis = loadArtifact<GapAnalysis>(ARTIFACT_PATHS.gapAnalysis);
    const systemState = loadArtifact<SystemState>(ARTIFACT_PATHS.systemState);

    const envelope = buildSourceEnvelope({
      slots: [
        { path: ARTIFACT_PATHS.roadmapTable, loaded: roadmapTable !== null },
        { path: ARTIFACT_PATHS.gapAnalysis, loaded: gapAnalysis !== null },
        { path: ARTIFACT_PATHS.systemState, loaded: systemState !== null },
      ],
      // The roadmap response surfaces values directly from the loaded
      // artifacts; it does not invent aggregates. So it is artifact_store
      // when complete, derived (with warnings) when partial — not estimate.
      isComputed: false,
    });

    const active_drift_legs: string[] = [];
    if (gapAnalysis?.dominant_bottleneck?.id === 'BN-006') {
      active_drift_legs.push('EVL');
    }

    return NextResponse.json({
      artifact_type: 'rge_roadmap_record',
      schema_version: '1.0.0',
      record_id: `RRM-${Date.now()}`,
      data_source: envelope.data_source,
      generated_at: envelope.generated_at,
      source_artifacts_used: envelope.source_artifacts_used,
      warnings: envelope.warnings,
      step_count: roadmapTable?.step_count ?? 0,
      steps: roadmapTable?.steps ?? [],
      not_to_build: roadmapTable?.not_to_build ?? [],
      dominant_bottleneck: gapAnalysis?.dominant_bottleneck ?? null,
      highest_risk_trust_gap: gapAnalysis?.highest_risk_trust_gap ?? null,
      top_risks: gapAnalysis?.top_risks ?? [],
      gap_classes: gapAnalysis?.gap_classes ?? {},
      domain_state: systemState?.domain_state ?? {},
      active_drift_legs,
      rge_can_operate: envelope.source_artifacts_used.length > 0,
      // kept for RGE page compatibility
      admitted_count: roadmapTable?.step_count ?? 0,
      blocked_count: gapAnalysis?.top_risks?.length ?? 0,
    });
  } catch (error) {
    console.error('Error fetching roadmap:', error);
    return NextResponse.json(
      { error: 'Failed to fetch roadmap', data_source: 'stub_fallback' },
      { status: 500 }
    );
  }
}
