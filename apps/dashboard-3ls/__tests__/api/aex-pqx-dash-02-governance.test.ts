import fs from 'fs';
import path from 'path';

const repoRoot = path.resolve(__dirname, '../../../../');
const appRoot = path.resolve(__dirname, '../../');

const intelligenceSrc = fs.readFileSync(
  path.resolve(appRoot, 'app/api/intelligence/route.ts'),
  'utf-8',
);
const pageSrc = fs.readFileSync(path.resolve(appRoot, 'app/page.tsx'), 'utf-8');

const governanceViolation = JSON.parse(
  fs.readFileSync(
    path.resolve(repoRoot, 'artifacts/dashboard_metrics/governance_violation_record.json'),
    'utf-8',
  ),
);
const aiProgrammingGovernedPath = JSON.parse(
  fs.readFileSync(
    path.resolve(
      repoRoot,
      'artifacts/dashboard_metrics/ai_programming_governed_path_record.json',
    ),
    'utf-8',
  ),
);

describe('AEX-PQX-DASH-02 — governance_violation_record.json', () => {
  it('declares the required envelope fields', () => {
    for (const field of [
      'artifact_type',
      'schema_version',
      'record_id',
      'created_at',
      'owner_system',
      'data_source',
      'status',
      'violation_count',
      'source_artifacts_used',
      'warnings',
      'reason_codes',
      'failure_prevented',
      'signal_improved',
      'violations',
    ]) {
      expect(governanceViolation).toHaveProperty(field);
    }
    expect(governanceViolation.owner_system).toBe('MET');
    expect(governanceViolation.data_source).toBe('artifact_store');
  });

  it('every violation declares the required fields', () => {
    expect(Array.isArray(governanceViolation.violations)).toBe(true);
    expect(governanceViolation.violations.length).toBeGreaterThan(0);
    for (const v of governanceViolation.violations) {
      for (const field of [
        'violation_id',
        'work_item_id',
        'agent_type',
        'violation_type',
        'missing_leg',
        'repo_mutating',
        'source_artifacts_used',
        'why_it_matters',
        'next_recommended_input',
      ]) {
        expect(v).toHaveProperty(field);
      }
      expect(['codex', 'claude', 'unknown_ai_agent']).toContain(v.agent_type);
      expect([
        'aex_missing',
        'pqx_missing',
        'evl_missing',
        'tpa_missing',
        'cde_missing',
        'sel_missing',
        'lineage_missing',
      ]).toContain(v.violation_type);
    }
  });

  it('violation_count is accurate (no hidden violations)', () => {
    expect(governanceViolation.violation_count).toBe(
      governanceViolation.violations.length,
    );
  });

  it('violation entries make no authority claims', () => {
    // MET observes only. Each violation must avoid claiming approve/enforce/
    // certify/decide on its own. The artifact-level warning may explicitly
    // disclaim these verbs (e.g. "does not enforce") — that disclaimer is
    // intentional and named authority owners (CDE, SEL) may appear in
    // descriptive text. The check therefore scans the violations array, not
    // the disclaimer warnings.
    const blob = JSON.stringify(governanceViolation.violations).toLowerCase();
    for (const verb of [
      'approve',
      'approves',
      'approved',
      'approving',
      'enforce ',
      'enforces',
      'enforced',
      'enforcing',
      'certify',
      'certifies',
      'certified',
      'certifying',
    ]) {
      expect(blob).not.toContain(verb);
    }
  });
});

describe('AEX-PQX-DASH-02 — ai_programming_governed_path_record.json', () => {
  it('declares core_loop_compliance with all six legs', () => {
    expect(aiProgrammingGovernedPath).toHaveProperty('core_loop_compliance');
    for (const leg of ['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL']) {
      expect(aiProgrammingGovernedPath.core_loop_compliance).toHaveProperty(leg);
      expect(['present', 'partial', 'missing', 'unknown']).toContain(
        aiProgrammingGovernedPath.core_loop_compliance[leg],
      );
    }
  });

  it('declares aggregate compliance fields', () => {
    for (const field of [
      'core_loop_complete',
      'first_missing_leg',
      'weakest_leg',
      'compliance_score',
    ]) {
      expect(aiProgrammingGovernedPath).toHaveProperty(field);
    }
  });

  it('compliance_score equals number of present legs', () => {
    const present = Object.values(
      aiProgrammingGovernedPath.core_loop_compliance,
    ).filter((s) => s === 'present').length;
    expect(aiProgrammingGovernedPath.compliance_score).toBe(present);
  });

  it('core_loop_complete is true only when score is 6/6', () => {
    if (aiProgrammingGovernedPath.compliance_score === 6) {
      expect(aiProgrammingGovernedPath.core_loop_complete).toBe(true);
    } else {
      expect(aiProgrammingGovernedPath.core_loop_complete).toBe(false);
    }
  });

  it('AEX or PQX missing forces status block', () => {
    const aex = aiProgrammingGovernedPath.core_loop_compliance.AEX;
    const pqx = aiProgrammingGovernedPath.core_loop_compliance.PQX;
    if (aex === 'missing' || pqx === 'missing') {
      expect(aiProgrammingGovernedPath.status).toBe('block');
    }
  });
});

describe('AEX-PQX-DASH-02 — /api/intelligence wiring', () => {
  it('loads the new artifacts and registers slots', () => {
    expect(intelligenceSrc).toContain(
      "governanceViolation: 'artifacts/dashboard_metrics/governance_violation_record.json'",
    );
    // After merge with main, the AI programming governed-path artifact path
    // is exported as a constant by lib/aiProgrammingGovernance.ts.
    expect(intelligenceSrc).toContain(
      'aiProgrammingGovernedPath: AI_PROGRAMMING_GOVERNED_PATH_ARTIFACT_PATH',
    );
    expect(intelligenceSrc).toContain('loaded: governanceViolation !== null');
    expect(intelligenceSrc).toContain('loaded: aiProgrammingGovernedPath !== null');
  });

  it('exposes governance_violations and core_loop_compliance_summary', () => {
    expect(intelligenceSrc).toContain('governance_violations: governanceViolationsBlock');
    expect(intelligenceSrc).toContain(
      'core_loop_compliance_summary: coreLoopComplianceSummaryBlock',
    );
  });

  it('degrades missing artifact to unknown rather than 0', () => {
    expect(intelligenceSrc).toContain("violation_count: 'unknown' as const");
    expect(intelligenceSrc).toContain("compliance_score: 'unknown' as const");
    expect(intelligenceSrc).toContain('${ARTIFACT_PATHS.governanceViolation} unavailable');
    expect(intelligenceSrc).toContain(
      '${ARTIFACT_PATHS.aiProgrammingGovernedPath} unavailable',
    );
    // Defensive: never default the missing branch to a literal 0 count.
    expect(intelligenceSrc).not.toContain('violation_count: 0,');
    expect(intelligenceSrc).not.toContain('compliance_score: 0,');
  });

  it('forces BLOCK when AEX or PQX missing', () => {
    expect(intelligenceSrc).toContain('aexOrPqxMissing');
    expect(intelligenceSrc).toContain(
      "legStates.AEX === 'missing' || legStates.PQX === 'missing'",
    );
    expect(intelligenceSrc).toContain(
      "if (aexOrPqxMissing) {\n    coreLoopStatus = 'block';",
    );
  });

  it('fail-closed: violation_count = max(declared, observed)', () => {
    // A stale declared violation_count must not under-report observed
    // violations. The route must derive the panel's count as the larger of
    // the two so a non-empty violations[] always surfaces. The "observed"
    // term uses the raw violations array length (not the well-formed-only
    // subset) so malformed-row drift cannot fall through to PASS — that
    // behavior is pinned by the dedicated raw-vs-filtered test below.
    expect(intelligenceSrc).toMatch(
      /Math\.max\(\s*declaredViolationCount(?:\s+as number)?,\s*(rawViolationsTotal|observedViolationCount)\s*\)/,
    );
  });

  it('fail-closed: declared status pass cannot override observed violations', () => {
    // If observed violation_count > 0, status must be forced to BLOCK
    // regardless of any declared status string.
    expect(intelligenceSrc).toContain('observedViolationsForce');
    expect(intelligenceSrc).toContain(
      "observedViolationsForce\n      ? 'block'",
    );
  });

  it('fail-closed: leg states are runtime-validated to LegState', () => {
    // Casting `as LegState` would let typos / casing variants bypass
    // missing/unknown checks; ensure a normalize function is present and
    // used for each leg.
    expect(intelligenceSrc).toContain('normalizeLegState');
    for (const leg of ['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL']) {
      expect(intelligenceSrc).toContain(`${leg}: normalizeLegState(compliance.${leg})`);
    }
    // The normalize function must default unknown / unexpected strings to
    // 'unknown' (fail-closed), not to 'present' or 'partial'.
    expect(intelligenceSrc).toMatch(
      /normalizeLegState[\s\S]*?value === 'present'[\s\S]*?value === 'partial'[\s\S]*?value === 'missing'[\s\S]*?value === 'unknown'[\s\S]*?: 'unknown'/,
    );
  });

  it('fail-closed: invalid governance status falls through to unknown not pass', () => {
    // When the artifact's status is an unexpected string and observed
    // violations are 0, the API must surface 'unknown' (data-quality
    // signal preserved) rather than 'pass' (fail-open).
    const tail = intelligenceSrc.slice(
      intelligenceSrc.indexOf('const governanceViolationStatus'),
      intelligenceSrc.indexOf('const governanceViolationsBlock'),
    );
    expect(tail).toContain("? (governanceViolation.status as 'pass' | 'warn' | 'block' | 'unknown')");
    expect(tail).toMatch(/:\s*'unknown';\s*$/);
    expect(tail).not.toMatch(/:\s*'pass';\s*$/);
  });

  it('fail-closed: core_loop_complete derives from observed leg states', () => {
    // Trusting declared core_loop_complete: true against missing legs would
    // make compliant_work_items=1 and blocked_work_items=1 simultaneously.
    // The API must derive core_loop_complete from `allPresent` (observed)
    // and surface a mismatch warning when the declared boolean disagrees.
    expect(intelligenceSrc).toContain(
      "const coreLoopComplete: boolean | 'unknown' = aiProgrammingGovernedPath\n    ? allPresent\n    : 'unknown'",
    );
    expect(intelligenceSrc).toContain('coreLoopCompleteDeclaredMismatch');
    expect(intelligenceSrc).toContain('disagrees with observed leg states');
  });

  it('fail-closed: work-item counts derived from per-work-item summary, not hard-coded', () => {
    // After main's PR #1287 renamed the lib to aiProgrammingGovernance,
    // counts derive from `governedPathSummary.total_ai_programming_work_items`,
    // `.governed_work_count`, `.bypass_risk_count` — never hard-coded to 1.
    expect(intelligenceSrc).toContain('rawWorkItems');
    expect(intelligenceSrc).toContain('governedPathSummary.total_ai_programming_work_items');
    expect(intelligenceSrc).toContain('governedPathSummary.governed_work_count');
    expect(intelligenceSrc).toContain('governedPathSummary.bypass_risk_count');
    expect(intelligenceSrc).not.toContain("totalWorkItems = aiProgrammingGovernedPath ? 1 : 'unknown'");
  });

  it('fail-closed: empty ai_programming_work_items[] reports 0, not 1', () => {
    // Codex P2 — when the artifact is present but the per-item array is
    // empty, counts must be 0 (no observed items). Falling through to a
    // hard-coded 1 would create a phantom work item. The follow-up Codex
    // P2 (line 1599) further requires "field absent" to surface 'unknown',
    // not 0 — pinned in a dedicated test below.
    expect(intelligenceSrc).toMatch(
      /rawWorkItems\.length === 0\s*\?\s*0/,
    );
  });

  it('fail-closed: violation_count uses raw violations[] not just filtered set', () => {
    // Malformed violation rows (missing required string fields) must still
    // count toward violation_count. Filtering them only for rendering would
    // let a stale `violation_count: 0` paired with a malformed row fall
    // through to PASS.
    expect(intelligenceSrc).toContain('rawViolations');
    expect(intelligenceSrc).toContain('rawViolationsTotal');
    expect(intelligenceSrc).toMatch(
      /Math\.max\(\s*declaredViolationCount(?:\s+as number)?,\s*rawViolationsTotal\s*\)/,
    );
    // Surface a warning when malformed rows are dropped from rendering, so
    // the data-shape drift never disappears silently.
    expect(intelligenceSrc).toContain('malformedViolationCount');
    expect(intelligenceSrc).toContain('dropped from the rendered list');
  });

  it('fail-closed: repo_mutating is normalized to boolean | unknown', () => {
    // String tokens ("true") or other non-boolean values must collapse to
    // 'unknown' so the missing-leg block rule cannot be skipped by
    // data-shape drift.
    expect(intelligenceSrc).toContain(
      "typeof rawRepoMutating === 'boolean' ? rawRepoMutating : 'unknown'",
    );
  });

  it('fail-closed: missing-leg block treats repoMutating unknown as blocking', () => {
    // Previously the rule was `repoMutating === true` — that skipped BLOCK
    // when the artifact had a non-boolean repo_mutating, downgrading to WARN.
    // The corrected rule blocks unless we *prove* it is non-mutating
    // (`repoMutating === false`).
    expect(intelligenceSrc).toContain('requiredLegMissing && repoMutating !== false');
    expect(intelligenceSrc).not.toContain('requiredLegMissing && repoMutating === true');
  });

  it('fail-closed: missing both violation_count and violations[] surfaces unknown', () => {
    // Partial-write / schema-drift: artifact present but neither
    // `violation_count` nor `violations` field exists. Must NOT degrade to
    // 0 (which could promote to PASS with status: 'pass'). Surface
    // 'unknown' instead so the data-quality signal is preserved.
    expect(intelligenceSrc).toContain('violationsFieldPresent');
    expect(intelligenceSrc).toContain('declaredViolationCountIsNumber');
    // The fallback path (neither count nor array): falls through to 'unknown'.
    expect(intelligenceSrc).toMatch(
      /violationsFieldPresent\s*\?\s*rawViolationsTotal\s*:\s*'unknown'/,
    );
  });

  it('fail-closed: missing ai_programming_work_items field reports unknown, not 0', () => {
    // Distinguish "field absent" (missing evidence → 'unknown') from
    // "array present but empty" (observed-zero → 0). Must not fall back
    // to governedPathSummary which treats missing arrays as empty.
    const block = intelligenceSrc.slice(
      intelligenceSrc.indexOf('const totalWorkItems'),
      intelligenceSrc.indexOf('const blockedWorkItems') + 600,
    );
    // totalWorkItems: rawWorkItems !== null ? length : 'unknown' (NOT
    // governedPathSummary.total_ai_programming_work_items).
    expect(block).toMatch(
      /rawWorkItems !== null\s*\?\s*rawWorkItems\.length\s*:\s*'unknown'/,
    );
    // compliant/blocked: rawWorkItems === null → 'unknown'.
    expect(block).toContain("rawWorkItems === null");
    // Defensive: the previous fallback to governedPathSummary.total_... is gone.
    expect(intelligenceSrc).not.toContain(
      "governedPathSummary.total_ai_programming_work_items ?? 'unknown'",
    );
  });

  it('summary block exposes the required surface fields', () => {
    const block = intelligenceSrc.slice(
      intelligenceSrc.indexOf('const coreLoopComplianceSummaryBlock'),
    );
    for (const field of [
      'status:',
      'violation_count:',
      'total_work_items:',
      'compliant_work_items:',
      'blocked_work_items:',
      'weakest_leg:',
      'missing_by_leg:',
      'source_artifacts_used:',
      'warnings:',
    ]) {
      expect(block).toContain(field);
    }
  });
});

describe('AEX-PQX-DASH-02 — dashboard panels', () => {
  it('renders the top governance-violations panel', () => {
    expect(pageSrc).toContain("data-testid=\"governance-violations-panel\"");
    expect(pageSrc).toContain("data-testid=\"governance-violations-status\"");
    expect(pageSrc).toContain("data-testid=\"governance-violations-count\"");
    expect(pageSrc).toContain("data-testid=\"governance-violation-item\"");
  });

  it('forces BLOCK on the panel when violation_count > 0', () => {
    expect(pageSrc).toContain(
      "typeof violationCount === 'number' && violationCount > 0\n                ? 'block'",
    );
  });

  it('renders the AI programming governance full-loop panel', () => {
    expect(pageSrc).toContain('data-testid="ai-programming-governance-panel"');
    expect(pageSrc).toContain('data-testid={`core-loop-leg-${leg}`}');
    expect(pageSrc).toContain('CORE_LOOP_LEGS_DISPLAY');
    // Every required leg label is present in the static legs list.
    expect(pageSrc).toMatch(
      /CORE_LOOP_LEGS_DISPLAY[^=]*=\s*\[[^\]]*'AEX'[^\]]*'PQX'[^\]]*'EVL'[^\]]*'TPA'[^\]]*'CDE'[^\]]*'SEL'[^\]]*\]/s,
    );
  });

  it('always-visible top panel: rendered before the legacy A. Trust Pulse panel', () => {
    const govIdx = pageSrc.indexOf('governance-violations-panel');
    const trustPulseIdx = pageSrc.indexOf('A. Trust Pulse');
    expect(govIdx).toBeGreaterThan(-1);
    expect(trustPulseIdx).toBeGreaterThan(-1);
    expect(govIdx).toBeLessThan(trustPulseIdx);
  });
});
