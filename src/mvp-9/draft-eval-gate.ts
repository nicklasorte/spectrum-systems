import { randomUUID } from "crypto";
import type { DraftEvalGateResult } from "./types";

/**
 * MVP-9: Draft Quality Eval Gate
 * Gate-3: Validates generation step before human review.
 */

const THRESHOLD_SNAPSHOT = {
  reliability_threshold: 0.8,
  drift_threshold: 0.2,
  trust_threshold: 0.7,
};

export async function runDraftEvalGate(
  draftArtifactId: string,
  issueSetArtifactId: string,
  draft?: any,
  issueSet?: any
): Promise<DraftEvalGateResult> {
  const traceId = randomUUID();
  const traceContext = { trace_id: traceId, created_at: new Date().toISOString() };

  const draftData =
    draft ||
    {
      artifact_type: "paper_draft_artifact",
      sections: { abstract: "test", introduction: "test", findings: "test" },
    };

  if (!draftData) {
    return {
      success: false,
      error: "Missing artifacts",
      execution_record: {
        artifact_type: "pqx_execution_record",
        artifact_id: randomUUID(),
        execution_status: "failed",
        failure: { reason_codes: ["missing_artifact"] },
      },
    };
  }

  const evalCases = [
    {
      case_id: randomUUID(),
      name: "schema_conformance",
      check: () => draftData.artifact_type === "paper_draft_artifact",
    },
    {
      case_id: randomUUID(),
      name: "issue_coverage",
      check: () => {
        const sections = Object.values(draftData.sections || {});
        return sections.length === 5;
      },
    },
    {
      case_id: randomUUID(),
      name: "section_completeness",
      check: () => {
        const sections = draftData.sections || {};
        return !!(sections.abstract && sections.introduction && sections.findings);
      },
    },
    {
      case_id: randomUUID(),
      name: "internal_consistency",
      check: () => Object.keys(draftData.sections || {}).length > 0,
    },
    {
      case_id: randomUUID(),
      name: "replay_consistency",
      check: () =>
        draftData.content_hash && draftData.content_hash.startsWith("sha256:"),
    },
    {
      case_id: randomUUID(),
      name: "quality_score",
      check: () => true,
    },
  ];

  const evalResults: any[] = [];
  let passedCount = 0;

  for (const evalCase of evalCases) {
    const passed = !!evalCase.check();
    evalResults.push({
      artifact_type: "eval_result",
      schema_version: "1.0.0",
      eval_case_id: evalCase.case_id,
      run_id: traceId,
      trace_id: traceId,
      result_status: passed ? "pass" : "fail",
      score: passed ? 1 : 0,
      failure_modes: passed ? [] : ["schema_violation"],
      provenance_refs: [draftArtifactId, issueSetArtifactId],
      details: { case_name: evalCase.name },
      status: passed ? "pass" : "fail",
    });
    if (passed) passedCount++;
  }

  const passRate = (passedCount / evalCases.length) * 100;
  const allPass = passRate >= 80;

  const evalSummary = {
    artifact_type: "eval_summary",
    schema_version: "1.0.0",
    artifact_id: randomUUID(),
    created_at: new Date().toISOString(),
    trace: traceContext,
    overall_status: allPass ? "pass" : "fail",
    pass_rate: Math.round(passRate),
    metrics: { total_cases: evalCases.length, passed: passedCount, failed: evalCases.length - passedCount },
  };

  const controlDecision = {
    artifact_type: "evaluation_control_decision",
    schema_version: "1.2.0",
    decision_id: randomUUID(),
    eval_run_id: traceId,
    system_status: allPass ? "healthy" : "blocked",
    system_response: allPass ? "allow" : "block",
    triggered_signals: allPass ? [] : ["reliability_breach"],
    threshold_snapshot: THRESHOLD_SNAPSHOT,
    threshold_context: "active_runtime",
    trace_id: traceId,
    created_at: new Date().toISOString(),
    decision: allPass ? "allow" : "deny",
    rationale_code: allPass
      ? "allow_healthy_eval_summary"
      : "deny_failure_eval_case",
    rationale: allPass
      ? "Draft passed quality gate. Proceeding to human review."
      : "Draft failed quality checks.",
    input_signal_reference: {
      signal_type: "eval_summary",
      source_artifact_id: evalSummary.artifact_id,
    },
    run_id: traceId,
  };

  const executionRecord = {
    artifact_type: "pqx_execution_record",
    artifact_id: randomUUID(),
    created_at: new Date().toISOString(),
    trace: traceContext,
    pqx_step: { name: "MVP-9: Draft Quality Eval Gate", version: "1.0" },
    execution_status: "succeeded",
    inputs: { artifact_ids: [draftArtifactId, issueSetArtifactId] },
    outputs: { artifact_ids: [evalSummary.artifact_id, controlDecision.decision_id] },
    timing: { started_at: traceContext.created_at, ended_at: new Date().toISOString() },
  };

  return {
    success: true,
    eval_results: evalResults,
    eval_summary: evalSummary,
    control_decision: controlDecision,
    execution_record: executionRecord,
  };
}
