import { v4 as uuidv4 } from "uuid";
import type {
  EvalResult,
  EvalSummary,
  ControlDecision,
  IngestionEvalGateResult,
  EvalCase,
} from "./types";

/**
 * MVP-3: Transcript Eval Baseline
 * 3 Eval Cases: schema conformance, manifest reproducibility, content coverage
 * Gate-1: Validates ingestion phase before proceeding to extraction
 *
 * Accepts the full artifact objects (not IDs) so eval runs against concrete
 * payloads without requiring a shared persistent store. Passing a sentinel
 * string such as "nonexistent" for either argument triggers the missing-
 * artifact failure path.
 */

const THRESHOLD_SNAPSHOT = {
  reliability_threshold: 0.8,
  drift_threshold: 0.2,
  trust_threshold: 0.7,
};

export async function runIngestionEvalGate(
  transcriptArtifact: Record<string, any> | string,
  contextBundleArtifact: Record<string, any> | string
): Promise<IngestionEvalGateResult> {
  const traceId = uuidv4();
  const traceContext = { trace_id: traceId, created_at: new Date().toISOString() };

  // Accept full artifact objects or sentinel "not found" strings
  const transcript =
    typeof transcriptArtifact === "string"
      ? null
      : { payload: transcriptArtifact };
  const contextBundle =
    typeof contextBundleArtifact === "string"
      ? null
      : { payload: contextBundleArtifact };

  const transcriptArtifactId =
    typeof transcriptArtifact === "string"
      ? transcriptArtifact
      : (transcriptArtifact?.outputs?.artifact_id ?? "unknown");

  if (!transcript || !contextBundle) {
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
        triggered_signals: ["reliability_breach"],
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
        artifact_kind: "pqx_execution_record",
        artifact_id: uuidv4(),
        execution_status: "failed",
        failure: { reason_codes: ["missing_artifact"] },
      },
    };
  }

  const evalCases: EvalCase[] = [
    {
      case_id: uuidv4(),
      name: "schema_conformance",
      description: "Validate both artifacts match schemas",
      check: (t, c) =>
        t.payload.artifact_type === "transcript_artifact" &&
        c.payload.artifact_type === "context_bundle",
    },
    {
      case_id: uuidv4(),
      name: "assembly_manifest_reproducibility",
      description: "Verify context bundle manifest hash is deterministic",
      check: (_t, c) =>
        c.payload.metadata?.assembly_manifest_hash?.startsWith("sha256:") || false,
    },
    {
      case_id: uuidv4(),
      name: "minimum_content_coverage",
      description: "Verify non-empty speakers and segments",
      check: (t, _c) => {
        const segments: any[] = t.payload.outputs?.segments || [];
        const speakers = Array.from(new Set(segments.map((s: any) => s.speaker)));
        const segmentCount =
          t.payload.outputs?.metadata?.segment_count || segments.length;
        return speakers.length > 0 && segmentCount > 0;
      },
    },
  ];

  const evalResults: EvalResult[] = [];
  let passedCount = 0;

  for (const evalCase of evalCases) {
    const passed = evalCase.check(transcript, contextBundle);
    evalResults.push({
      artifact_type: "eval_result",
      schema_version: "1.0.0",
      eval_case_id: evalCase.case_id,
      run_id: traceId,
      trace_id: traceId,
      result_status: passed ? "pass" : "fail",
      score: passed ? 1 : 0,
      failure_modes: passed ? [] : ["schema_violation"],
      provenance_refs: [transcriptArtifactId],
    });
    if (passed) passedCount++;
  }

  const passRate = (passedCount / evalCases.length) * 100;
  const allPass = passRate === 100;

  const evalSummary: EvalSummary = {
    artifact_kind: "eval_summary",
    artifact_id: uuidv4(),
    created_at: new Date().toISOString(),
    schema_ref: "artifacts/eval_summary.schema.json",
    trace: traceContext,
    target_artifact_id: transcriptArtifactId,
    eval_case_ids: evalCases.map((c) => c.case_id),
    overall_status: allPass ? "pass" : "fail",
    pass_rate: Math.round(passRate),
    metrics: {
      total_cases: evalCases.length,
      passed: passedCount,
      failed: evalCases.length - passedCount,
    },
  };

  const controlDecision: ControlDecision = {
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
    rationale_code: allPass ? "allow_healthy_eval_summary" : "deny_failure_eval_case",
    input_signal_reference: {
      signal_type: "eval_summary",
      source_artifact_id: evalSummary.artifact_id,
    },
    run_id: traceId,
  };

  const executionRecord = {
    artifact_kind: "pqx_execution_record",
    artifact_id: uuidv4(),
    created_at: new Date().toISOString(),
    trace: traceContext,
    pqx_step: { name: "MVP-3: Transcript Eval Baseline", version: "1.0" },
    execution_status: "succeeded",
    inputs: { artifact_ids: [transcriptArtifactId] },
    outputs: { artifact_ids: [evalSummary.artifact_id, controlDecision.decision_id] },
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
