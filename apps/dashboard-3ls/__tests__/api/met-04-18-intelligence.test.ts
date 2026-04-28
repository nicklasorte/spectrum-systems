import fs from 'fs';
import path from 'path';

const appRoot = path.resolve(__dirname, '../../');
const intelligenceSrc = fs.readFileSync(
  path.resolve(appRoot, 'app/api/intelligence/route.ts'),
  'utf-8',
);

describe('MET-04-18 — /api/intelligence wires new MET fields', () => {
  it('exposes feedback_loop, feedback_loop_status, unresolved_feedback_count', () => {
    expect(intelligenceSrc).toContain('feedback_loop:');
    expect(intelligenceSrc).toContain('feedback_loop_status:');
    expect(intelligenceSrc).toContain('unresolved_feedback_count:');
  });

  it('exposes eval_candidates and policy_candidate_signals blocks', () => {
    expect(intelligenceSrc).toContain('eval_candidates:');
    expect(intelligenceSrc).toContain('policy_candidate_signals:');
  });

  it('exposes failure_explanation_packets, override_audit, eval_materialization_path', () => {
    expect(intelligenceSrc).toContain('failure_explanation_packets:');
    expect(intelligenceSrc).toContain('override_audit:');
    expect(intelligenceSrc).toContain('eval_materialization_path:');
  });

  it('exposes additional_cases_summary, replay_lineage_hardening, fallback_reduction_plan, sel_compliance_signal_input', () => {
    expect(intelligenceSrc).toContain('additional_cases_summary:');
    expect(intelligenceSrc).toContain('replay_lineage_hardening:');
    expect(intelligenceSrc).toContain('fallback_reduction_plan:');
    expect(intelligenceSrc).toContain('sel_compliance_signal_input:');
  });

  it('every new block surfaces data_source, source_artifacts_used, warnings', () => {
    [
      'feedbackLoopBlock',
      'evalCandidatesBlock',
      'policyCandidateSignalsBlock',
      'failureExplanationPacketsBlock',
      'overrideAuditBlock',
      'evalMaterializationPathBlock',
      'additionalCasesSummaryBlock',
      'replayLineageHardeningBlock',
      'fallbackReductionPlanBlock',
      'selComplianceSignalInputBlock',
    ].forEach((blockName) => {
      const idx = intelligenceSrc.indexOf(`const ${blockName}`);
      expect(idx).toBeGreaterThan(-1);
      const block = intelligenceSrc.slice(idx, idx + 4000);
      expect(block).toContain('data_source');
      expect(block).toContain('source_artifacts_used');
      expect(block).toContain('warnings');
    });
  });

  it('override_count never silently substitutes 0; degrades to unknown', () => {
    const idx = intelligenceSrc.indexOf('const overrideAuditBlock');
    const block = intelligenceSrc.slice(idx, idx + 2000);
    // Match the truthy branch: override_count: overrideAuditLog.override_count ?? 'unknown'
    expect(block).toMatch(/override_count: overrideAuditLog\.override_count \?\? 'unknown'/);
    // Match the missing-artifact branch: override_count: 'unknown'
    expect(block).toMatch(/override_count: 'unknown'/);
  });

  it('feedback loop counts degrade to unknown when artifact missing', () => {
    const idx = intelligenceSrc.indexOf('const feedbackLoopBlock');
    const block = intelligenceSrc.slice(idx, idx + 4000);
    [
      'feedback_items_count',
      'eval_candidates_count',
      'policy_candidate_signals_count',
      'unresolved_feedback_count',
      'expired_feedback_count',
    ].forEach((field) => {
      expect(block).toMatch(new RegExp(`${field}: 'unknown'`));
    });
  });

  it('filters out unsourced eval candidates, policy candidates, packets, and fallback items', () => {
    expect(intelligenceSrc).toContain('filteredEvalCandidates');
    expect(intelligenceSrc).toContain('filteredPolicySignals');
    expect(intelligenceSrc).toContain('filteredPackets');
    expect(intelligenceSrc).toContain('filteredFallbackItems');
  });

  it('does not name MET as a decision/enforcement/promotion authority', () => {
    // MET-15 must_fix MF2-01: ensure the field name 'feedback_loop_decision'
    // is never reintroduced.
    expect(intelligenceSrc).not.toContain('feedback_loop_decision');
  });
});
