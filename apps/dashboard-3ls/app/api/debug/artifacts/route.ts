import fs from 'fs';
import path from 'path';
import { NextResponse } from 'next/server';
import { getRepoRoot } from '@/lib/artifactLoader';

const EXPECTED_SEED_FILES = [
  'source_artifact_record.json',
  'output_artifact_record.json',
  'eval_summary_record.json',
  'trust_policy_decision_record.json',
  'control_decision_record.json',
  'enforcement_action_record.json',
  'lineage_record.json',
  'replay_record.json',
  'observability_metrics_record.json',
  'slo_status_record.json',
  'failure_mode_dashboard_record.json',
  'near_miss_record.json',
  'minimal_loop_snapshot.json',
];

export async function GET() {
  const repoRoot = getRepoRoot();
  const artifactsDir = path.join(repoRoot, 'artifacts');
  const seedDir = path.join(artifactsDir, 'dashboard_seed');

  const artifactsFound = fs.existsSync(artifactsDir);
  const dashboardSeedFound = fs.existsSync(seedDir);

  const files = dashboardSeedFound
    ? fs
        .readdirSync(seedDir)
        .filter((f) => f.endsWith('.json'))
        .sort()
    : [];

  const missingExpectedFiles = EXPECTED_SEED_FILES.filter((f) => !files.includes(f));

  return NextResponse.json({
    data_source: 'repo_registry',
    generated_at: new Date().toISOString(),
    source_artifacts_used: dashboardSeedFound
      ? files.slice(0, 10).map((f) => `artifacts/dashboard_seed/${f}`)
      : [],
    repo_root: repoRoot,
    dashboard_seed_found: dashboardSeedFound,
    artifacts_found: artifactsFound,
    sample_files: files.slice(0, 10),
    missing_expected_files: missingExpectedFiles,
    warnings: [
      ...(artifactsFound ? [] : ['artifacts directory not found at resolved repo root.']),
      ...(dashboardSeedFound ? [] : ['dashboard_seed directory missing.']),
      ...(missingExpectedFiles.length > 0
        ? ['dashboard_seed is present but one or more expected seed artifacts are missing.']
        : []),
    ],
  });
}
