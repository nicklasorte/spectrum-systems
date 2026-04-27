import fs from 'fs';
import path from 'path';
import { loadNextStepArtifact } from '@/lib/nextStepArtifactLoader';

describe('nextStepArtifactLoader', () => {
  const root = path.resolve(process.cwd(), '../..');
  const artifactPath = path.join(root, 'artifacts/next_step_decision_report.json');

  afterEach(() => {
    if (fs.existsSync(artifactPath)) {
      fs.unlinkSync(artifactPath);
    }
  });

  it('loads artifact successfully', () => {
    fs.mkdirSync(path.dirname(artifactPath), { recursive: true });
    fs.writeFileSync(
      artifactPath,
      JSON.stringify({
        artifact_type: 'next_step_decision_report',
        schema_version: '1.0.0',
        generated_at: '2026-04-27T00:00:00Z',
        status: 'pass',
        readiness_state: 'ready',
        source_refs: [],
        completed_work: [],
        partial_work: [],
        remaining_work_table: [],
        ranked_priorities: [],
        selected_next_step: { id: 'RFX-PROOF-01' },
        rejected_next_steps: [],
        dependency_reasoning: [],
        red_team_findings: [],
        warnings: [],
        reason_codes: [],
      }),
    );
    const result = loadNextStepArtifact();
    expect(result.state).toBe('ok');
    expect(result.payload.selected_next_step).toEqual({ id: 'RFX-PROOF-01' });
  });

  it('returns blocked missing payload when artifact is absent', () => {
    const result = loadNextStepArtifact('artifacts/does_not_exist.json');
    expect(result.state).toBe('missing');
    expect(result.payload.status).toBe('blocked');
    expect(result.payload.reason_codes.join(',')).toContain('missing_required_artifact');
  });
});
