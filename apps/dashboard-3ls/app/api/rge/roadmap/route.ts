import { NextRequest, NextResponse } from 'next/server';
import { loadArtifact } from '@/lib/artifactLoader';
import type { RoadmapTable, GapAnalysis, SystemState, DataSource } from '@/lib/types';

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

    const warnings: string[] = [];
    const source_artifacts_used: string[] = [];

    if (roadmapTable) source_artifacts_used.push(ARTIFACT_PATHS.roadmapTable);
    else warnings.push('roadmap_table unavailable: roadmap_table.json not found');

    if (gapAnalysis) source_artifacts_used.push(ARTIFACT_PATHS.gapAnalysis);
    else warnings.push('gap_analysis unavailable: gap_analysis.json not found');

    if (systemState) source_artifacts_used.push(ARTIFACT_PATHS.systemState);
    else warnings.push('system_state unavailable: system_state.json not found');

    const loadedCount = source_artifacts_used.length;
    let data_source: DataSource;
    if (loadedCount === 0) {
      data_source = 'stub_fallback';
    } else if (loadedCount === 3) {
      data_source = 'artifact_store';
    } else {
      data_source = 'derived';
    }

    const active_drift_legs: string[] = [];
    if (gapAnalysis?.dominant_bottleneck?.id === 'BN-006') {
      active_drift_legs.push('EVL');
    }

    return NextResponse.json({
      artifact_type: 'rge_roadmap_record',
      schema_version: '1.0.0',
      record_id: `RRM-${Date.now()}`,
      data_source,
      generated_at: new Date().toISOString(),
      source_artifacts_used,
      warnings,
      step_count: roadmapTable?.step_count ?? 0,
      steps: roadmapTable?.steps ?? [],
      not_to_build: roadmapTable?.not_to_build ?? [],
      dominant_bottleneck: gapAnalysis?.dominant_bottleneck ?? null,
      highest_risk_trust_gap: gapAnalysis?.highest_risk_trust_gap ?? null,
      top_risks: gapAnalysis?.top_risks ?? [],
      gap_classes: gapAnalysis?.gap_classes ?? {},
      domain_state: systemState?.domain_state ?? {},
      active_drift_legs,
      rge_can_operate: loadedCount > 0,
      // kept for RGE page compatibility
      admitted_count: roadmapTable?.step_count ?? 0,
      blocked_count: gapAnalysis?.top_risks?.length ?? 0,
    });
  } catch (error) {
    console.error('Error fetching roadmap:', error);
    return NextResponse.json({ error: 'Failed to fetch roadmap' }, { status: 500 });
  }
}
