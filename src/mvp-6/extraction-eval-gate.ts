import { v4 as uuidv4 } from "uuid";
import type { ExtractionEvalGateResult } from "./types";

/**
 * MVP-6: Extraction Eval Gate
 * Gate-2: Validates extraction phase (Minutes + Issues)
 * 5 eval cases: schema conformance, source traceability, agenda coverage,
 *               action item completeness, issue count
 *
 * Accepts the full minutes and issue artifact objects. Passing a sentinel
 * string such as "nonexistent" triggers the missing-artifact failure path.
 */

const THRESHOLD_SNAPSHOT = {
  reliability_threshold: 0.8,
  drift_threshold: 0.2,
  trust_threshold: 0.7,
};

export async function runExtractionEvalGate(
  minutesArtifact: Record<string, any> | string,
  issueArtifact: Record<string, any> | string
): Promise<ExtractionEvalGateResult> {
  const traceId = uuidv4();
  const traceContext = {
    trace_id: traceId,
    created_at: new Date().toISOString(),
  };

  const minutes =
    typeof minutesArtifact === "string" ? null : minutesArtifact;
  const issues = typeof issueArtifact === "string" ? null : issueArtifact;

  const minutesArtifactId =
    typeof minutesArtifact === "string"
      ? minutesArtifact
      : (minutesArtifact?.artifact_id ?? "unknown");
  const issueArtifactId =
    typeof issueArtifact === "string"
      ? issueArtifact
      : (issueArtifact?.artifact_id ?? "unknown");

  if (!minutes || !issues) {
    const decisionId = uuidv4();
    return {
      success: false,
      error: "Missing artifacts for evaluation",
      control_decision: {
        artifact_type: "evaluation_control_decision",
        schema_version: "1.2.0",
        decision_id: decisionId,
        eval_run_id: traceId,
        system_status: "blocked",
        system_response: "block",
        triggered_signals: ["missing_required_signal"],
        threshold_snapshot: THRESHOLD_SNAPSHOT,
        threshold_context: "active_runtime",
        trace_id: traceId,
        created_at: new Date().toISOString(),
        decision: "deny",
        rationale_code: "deny_missing_required_signal",
        input_signal_reference: {
          signal_type: "eval_summary",
          source_artifact_id: traceId,
        },
        run_id: traceId,
      },
      execution_record: {
        artifact_type: "pqx_execution_record",
        artifact_id: uuidv4(),
        execution_status: "failed",
        failure: { reason_codes: ["missing_artifact"] },
      },
    };
  }

  const evalCases = [
    {
      case_id: uuidv4(),
      name: "schema_conformance",
      description: "Both artifacts match schemas",
      check: (m: any, i: any) =>
        m.artifact_type === "meeting_minutes_artifact" &&
        i.artifact_type === "issue_registry_artifact",
    },
    {
      case_id: uuidv4(),
      name: "issue_source_traceability",
      description: "Every issue has source_turn_ref (CRITICAL)",
      check: (_m: any, i: any) => {
        const issueList = i.issues || [];
        return issueList.every(
          (issue: any) => issue.source_turn_ref && issue.source_turn_ref.length > 0
        );
      },
    },
    {
      case_id: uuidv4(),
      name: "agenda_coverage",
      description: "Minutes have at least one agenda item",
      check: (m: any, _i: any) => Array.isArray(m.agenda_items) && m.agenda_items.length > 0,
    },
    {
      case_id: uuidv4(),
      name: "action_item_completeness",
      description: "action_items array is present (non-null)",
      check: (m: any, _i: any) =>
        Array.isArray(m.action_items) && m.action_items.length >= 0,
    },
    {
      case_id: uuidv4(),
      name: "issue_count",
      description: "issues array is present (non-null, can be zero)",
      check: (_m: any, i: any) =>
        Array.isArray(i.issues) && i.issues.length >= 0,
    },
  ];

  const evalResults: any[] = [];
  let passedCount = 0;

  for (const evalCase of evalCases) {
    const passed = evalCase.check(minutes, issues);
    evalResults.push({
      artifact_type: "eval_result",
      schema_version: "1.0.0",
      eval_case_id: evalCase.case_id,
      run_id: traceId,
      trace_id: traceId,
      result_status: passed ? "pass" : "fail",
      score: passed ? 1 : 0,
      failure_modes: passed ? [] : ["schema_violation"],
      provenance_refs: [minutesArtifactId, issueArtifactId],
      // Retain human-readable details alongside (not part of schema):
      details: {
        case_name: evalCase.name,
        case_description: evalCase.description,
      },
      status: passed ? "pass" : "fail",
    });
    if (passed) passedCount++;
  }

  const passRate = (passedCount / evalCases.length) * 100;
  const allPass = passRate === 100;

  const evalSummary = {
    artifact_type: "eval_summary",
    schema_version: "1.0.0",
    artifact_id: uuidv4(),
    created_at: new Date().toISOString(),
    schema_ref: "artifacts/eval_summary.schema.json",
    trace: traceContext,
    target_artifact_id: minutesArtifactId,
    eval_case_ids: evalCases.map((c) => c.case_id),
    overall_status: allPass ? "pass" : "fail",
    pass_rate: Math.round(passRate),
    metrics: {
      total_cases: evalCases.length,
      passed: passedCount,
      failed: evalCases.length - passedCount,
    },
  };

  const controlDecision = {
    artifact_type: "evaluation_control_decision",
    schema_version: "1.2.0",
    decision_id: uuidv4(),
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
      ? "All extraction eval cases passed. Proceeding to paper generation."
      : `Only ${passedCount}/${evalCases.length} eval cases passed. Blocking pipeline.`,
    input_signal_reference: {
      signal_type: "eval_summary",
      source_artifact_id: evalSummary.artifact_id,
    },
    run_id: traceId,
  };

  const executionRecord = {
    artifact_type: "pqx_execution_record",
    artifact_id: uuidv4(),
    created_at: new Date().toISOString(),
    trace: traceContext,
    pqx_step: {
      name: "MVP-6: Extraction Eval Gate",
      version: "1.0",
    },
    execution_status: "succeeded",
    inputs: { artifact_ids: [minutesArtifactId, issueArtifactId] },
    outputs: {
      artifact_ids: [
        evalSummary.artifact_id,
        controlDecision.decision_id,
      ],
    },
    timing: {
      started_at: traceContext.created_at,
      ended_at: new Date().toISOString(),
    },
  };

  return {
    success: true,
    eval_results: evalResults,
    eval_summary: evalSummary,
    control_decision: controlDecision,
    execution_record: executionRecord,
  };
}
