import fs from 'fs';
import path from 'path';

const appRoot = path.resolve(__dirname, '../../');
const intelligenceSrc = fs.readFileSync(
  path.resolve(appRoot, 'app/api/intelligence/route.ts'),
  'utf-8',
);

describe('AEX-PQX-DASH-01-REFINE — /api/intelligence AI programming core-loop block', () => {
  it('exposes the ai_programming_governed_path block in the response', () => {
    expect(intelligenceSrc).toContain('ai_programming_governed_path: aiProgrammingGovernedPathBlock');
  });

  it('loads the AI programming governed-path artifact', () => {
    expect(intelligenceSrc).toContain(
      "'artifacts/dashboard_metrics/ai_programming_governed_path_record.json'",
    );
    expect(intelligenceSrc).toContain('ARTIFACT_PATHS.aiProgrammingGovernedPath');
  });

  it('exposes per-leg counts: AEX, PQX, EVL, TPA, CDE, SEL', () => {
    [
      'aex_present_count',
      'pqx_present_count',
      'evl_present_count',
      'tpa_present_count',
      'cde_present_count',
      'sel_present_count',
    ].forEach((field) => {
      expect(intelligenceSrc).toContain(field);
    });
  });

  it('exposes missing_by_leg, blocked_work_items, and weakest_leg', () => {
    expect(intelligenceSrc).toContain('missing_by_leg');
    expect(intelligenceSrc).toContain('blocked_work_items');
    expect(intelligenceSrc).toContain('weakest_leg');
  });

  it('exposes core_loop_summary with codex_count and claude_count', () => {
    expect(intelligenceSrc).toContain('core_loop_summary');
    expect(intelligenceSrc).toContain('codex_count');
    expect(intelligenceSrc).toContain('claude_count');
  });

  it('does not use forbidden authority verb "Execute" in the block construction', () => {
    // AEX-PQX-DASH-01-REFINE rule: dashboard observes; do not use "Execute".
    const block = intelligenceSrc.slice(
      intelligenceSrc.indexOf('aiProgrammingGovernedPathBlock'),
      intelligenceSrc.indexOf('aiProgrammingGovernedPathBlock') + 4000,
    );
    expect(/\bExecute\b/.test(block)).toBe(false);
  });
});

describe('AEX-PQX-DASH-01-REFINE — seed artifact shape', () => {
  const repoRoot = path.resolve(appRoot, '../../');
  const recordPath = path.join(
    repoRoot,
    'artifacts/dashboard_metrics/ai_programming_governed_path_record.json',
  );

  it('record exists on disk', () => {
    expect(fs.existsSync(recordPath)).toBe(true);
  });

  it('every work item has a six-leg observation row with sourced fields', () => {
    const raw = JSON.parse(fs.readFileSync(recordPath, 'utf-8'));
    expect(Array.isArray(raw.ai_programming_work_items)).toBe(true);
    const legs = ['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL'];
    for (const item of raw.ai_programming_work_items) {
      for (const leg of legs) {
        expect(item.core_loop_observations).toHaveProperty(leg);
        const obs = item.core_loop_observations[leg];
        expect(['present', 'partial', 'missing', 'unknown']).toContain(obs.observation);
        expect(Array.isArray(obs.source_artifacts_used)).toBe(true);
        expect(Array.isArray(obs.reason_codes)).toBe(true);
      }
      expect(item).toHaveProperty('first_missing_leg');
      expect(item).toHaveProperty('weakest_leg');
      expect(item).toHaveProperty('core_loop_complete');
      expect(item).toHaveProperty('hard_block_reason');
      expect(item).toHaveProperty('next_recommended_input');
    }
  });

  it('uses no banned authority verbs in observation strings', () => {
    // The seed artifact must not claim MET decides/enforces/blocks/executes.
    const raw = fs.readFileSync(recordPath, 'utf-8');
    // Banned authority claim verbs that would imply MET acts as an authority.
    // The status label "BLOCK" is allowed (it names an observation state);
    // the verb forms (executes, enforces, etc.) are not.
    const bannedVerbs = [
      /\bexecutes\b/,
      /\benforces\b/,
      /\bcertifies\b/,
      /\bowns\b/,
      /\bdecides\b/,
      /\bcontrols\b/,
      /\bapproves\b/,
      /\bgates\b/,
      /\bpromotes\b/,
      /\badjudicates\b/,
      /\bfinalizes\b/,
    ];
    bannedVerbs.forEach((re) => {
      expect(re.test(raw)).toBe(false);
    });
  });
});
