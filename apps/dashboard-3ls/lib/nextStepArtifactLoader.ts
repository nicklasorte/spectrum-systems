import fs from 'fs';
import path from 'path';
import { getRepoRoot } from '@/lib/artifactLoader';

export interface NextStepSourceRef {
  path: string;
  required: boolean;
  present: boolean;
  content_hash: string | null;
}

export interface NextStepReport {
  artifact_type: 'next_step_recommendation_report';
  schema_version: '1.0.0';
  generated_at: string;
  status: 'pass' | 'blocked';
  readiness_state: 'ready' | 'blocked';
  source_refs: NextStepSourceRef[];
  completed_work: string[];
  partial_work: string[];
  remaining_work_table: Array<Record<string, unknown>>;
  ranked_priorities: Array<Record<string, unknown>>;
  selected_recommendation: Record<string, unknown> | null;
  rejected_next_steps: Array<Record<string, unknown>>;
  dependency_observations: string[];
  red_team_findings: Array<Record<string, unknown>>;
  warnings: string[];
  reason_codes: string[];
}

export interface NextStepLoadResult {
  state: 'ok' | 'missing' | 'invalid_schema';
  payload: NextStepReport;
}

const NEXT_STEP_PATH = 'artifacts/next_step_recommendation_report.json';

function fallbackMissing(pathRef: string): NextStepLoadResult {
  return {
    state: 'missing',
    payload: {
      artifact_type: 'next_step_recommendation_report',
      schema_version: '1.0.0',
      generated_at: new Date().toISOString(),
      status: 'blocked',
      readiness_state: 'blocked',
      source_refs: [{ path: pathRef, required: true, present: false, content_hash: null }],
      completed_work: [],
      partial_work: [],
      remaining_work_table: [],
      ranked_priorities: [],
      selected_recommendation: null,
      rejected_next_steps: [],
      dependency_observations: [],
      red_team_findings: [],
      warnings: ['next_step_artifact_missing'],
      reason_codes: [`missing_required_artifact:${pathRef}`],
    },
  };
}

function isNextStepReport(value: unknown): value is NextStepReport {
  if (!value || typeof value !== 'object') return false;
  const obj = value as Record<string, unknown>;
  return obj.artifact_type === 'next_step_recommendation_report'
    && obj.schema_version === '1.0.0'
    && Array.isArray(obj.source_refs)
    && Array.isArray(obj.reason_codes);
}

export function loadNextStepArtifact(relativePath: string = NEXT_STEP_PATH): NextStepLoadResult {
  const fullPath = path.join(getRepoRoot(), relativePath);
  if (!fs.existsSync(fullPath)) {
    return fallbackMissing(relativePath);
  }
  try {
    const parsed = JSON.parse(fs.readFileSync(fullPath, 'utf-8')) as unknown;
    if (!isNextStepReport(parsed)) {
      return {
        state: 'invalid_schema',
        payload: {
          ...fallbackMissing(relativePath).payload,
          reason_codes: ['invalid_next_step_artifact_shape'],
          warnings: ['next_step_artifact_invalid_schema'],
          source_refs: [{ path: relativePath, required: true, present: true, content_hash: null }],
        },
      };
    }
    return { state: 'ok', payload: parsed };
  } catch {
    return {
      state: 'invalid_schema',
      payload: {
        ...fallbackMissing(relativePath).payload,
        reason_codes: ['invalid_next_step_artifact_json'],
        warnings: ['next_step_artifact_invalid_json'],
        source_refs: [{ path: relativePath, required: true, present: true, content_hash: null }],
      },
    };
  }
}
