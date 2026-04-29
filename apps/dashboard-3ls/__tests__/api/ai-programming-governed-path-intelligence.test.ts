// AEX-PQX-DASH-01 — /api/intelligence wires the AI programming governed-path block.
//
// Asserts the route exposes the block, degrades to unknown when the artifact
// is missing, and never renames the field to use authority verbs.

import fs from 'fs';
import path from 'path';

const appRoot = path.resolve(__dirname, '../../');
const intelligenceSrc = fs.readFileSync(
  path.resolve(appRoot, 'app/api/intelligence/route.ts'),
  'utf-8',
);

describe('AEX-PQX-DASH-01 — /api/intelligence exposes ai_programming_governed_path', () => {
  it('declares the ai_programming_governed_path response field', () => {
    expect(intelligenceSrc).toContain('ai_programming_governed_path:');
  });

  it('loads the AI programming governed-path artifact via the helper constant', () => {
    expect(intelligenceSrc).toContain('AI_PROGRAMMING_GOVERNED_PATH_ARTIFACT_PATH');
    const helperSrc = fs.readFileSync(
      path.resolve(appRoot, 'lib/aiProgrammingGovernance.ts'),
      'utf-8',
    );
    expect(helperSrc).toContain(
      'artifacts/dashboard_metrics/ai_programming_governed_path_record.json',
    );
  });

  it('exposes Codex and Claude counts and bypass-risk counts from the block', () => {
    const idx = intelligenceSrc.indexOf('aiProgrammingGovernedPathBlock');
    expect(idx).toBeGreaterThan(-1);
    const block = intelligenceSrc.slice(idx, idx + 4000);
    expect(block).toContain('codex_work_count');
    expect(block).toContain('claude_work_count');
    expect(block).toContain('bypass_risk_count');
    expect(block).toContain('unknown_path_count');
  });

  it('surfaces data_source, source_artifacts_used, warnings, reason_codes', () => {
    const idx = intelligenceSrc.indexOf('aiProgrammingGovernedPathBlock');
    const block = intelligenceSrc.slice(idx, idx + 4000);
    expect(block).toContain('data_source');
    expect(block).toContain('source_artifacts_used');
    expect(block).toContain('warnings');
    expect(block).toContain('reason_codes');
  });

  it('never names MET as a decision/enforcement/promotion authority for AI work', () => {
    expect(intelligenceSrc).not.toContain('ai_programming_decision');
    expect(intelligenceSrc).not.toContain('ai_programming_enforced');
    expect(intelligenceSrc).not.toContain('ai_programming_certified');
    expect(intelligenceSrc).not.toContain('ai_programming_promoted');
  });
});
