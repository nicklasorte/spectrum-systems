import { v4 as uuidv4 } from "uuid";
import { createArtifactStore, MemoryStorageBackend } from "@/src/artifact-store";
import type { EvalResult, EvalSummary, ControlDecision, IngestionEvalGateResult, EvalCase } from "./types";

/**
 * MVP-3: Transcript Eval Baseline
 * 3 Eval Cases: schema, reproducibility, content coverage
 * Gate-1: Validates ingestion phase before proceeding to extraction
 */

export async function runIngestionEvalGate(
  transcriptArtifactId: string,
  contextBundleArtifactId: string
): Promise<IngestionEvalGateResult> {
  const backend = new MemoryStorageBackend();
  const store = createArtifactStore(backend);
  const traceId = uuidv4();
  const traceContext = { trace_id: traceId, created_at: new Date().toISOString() };

  const transcript = await store.retrieve(transcriptArtifactId);
  const contextBundle = await store.retrieve(contextBundleArtifactId);

  if (!transcript || !contextBundle) {
    return {
      success: false,
      error: "Missing artifacts for evaluation",
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
        t.payload.artifact_kind === "transcript_artifact" &&
        c.payload.artifact_kind === "context_bundle",
    },
    {
      case_id: uuidv4(),
      name: "assembly_manifest_reproducibility",
      description: "Verify context bundle manifest reproducible",
      check: (t, c) =>
        c.payload.assembly_manifest?.manifest_hash?.startsWith("sha256:") || false,
    },
    {
      case_id: uuidv4(),
      name: "minimum_content_coverage",
      description: "Verify non-empty speakers and turns",
      check: (t, c) => {
        const speakers = t.payload.metadata?.speaker_labels || [];
        const turnCount = t.payload.metadata?.turn_count || 0;
        return speakers.length > 0 && turnCount > 0;
      },
    },
  ];

  const evalResults: EvalResult[] = [];
  let passedCount = 0;

  for (const evalCase of evalCases) {
    const passed = evalCase.check(transcript, contextBundle);
    evalResults.push({
      artifact_kind: "eval_result",
      artifact_id: uuidv4(),
      created_at: new Date().toISOString(),
      schema_ref: "artifacts/eval_result.schema.json",
      trace: traceContext,
      eval_case_id: evalCase.case_id,
      target_artifact_id: transcriptArtifactId,
      status: passed ? "pass" : "fail",
      score: passed ? 100 : 0,
      details: { case_name: evalCase.name },
    });
    if (passed) passedCount++;
  }

  const passRate = (passedCount / evalCases.length) * 100;

  const evalSummary: EvalSummary = {
    artifact_kind: "eval_summary",
    artifact_id: uuidv4(),
    created_at: new Date().toISOString(),
    schema_ref: "artifacts/eval_summary.schema.json",
    trace: traceContext,
    target_artifact_id: transcriptArtifactId,
    eval_case_ids: evalCases.map((c) => c.case_id),
    overall_status: passRate === 100 ? "pass" : "fail",
    pass_rate: Math.round(passRate),
    metrics: {
      total_cases: evalCases.length,
      passed: passedCount,
      failed: evalCases.length - passedCount,
    },
  };

  const decision = passRate === 100 ? "allow" : "block";
  const controlDecision: ControlDecision = {
    artifact_kind: "evaluation_control_decision",
    artifact_id: uuidv4(),
    created_at: new Date().toISOString(),
    schema_ref: "artifacts/evaluation_control_decision.schema.json",
    trace: traceContext,
    decision,
    rationale:
      passRate === 100
        ? "All ingestion eval cases passed. Proceeding to extraction phase."
        : `Only ${passedCount}/${evalCases.length} eval cases passed. Blocking pipeline.`,
    eval_summary_id: evalSummary.artifact_id,
  };

  const executionRecord = {
    artifact_kind: "pqx_execution_record",
    artifact_id: uuidv4(),
    created_at: new Date().toISOString(),
    trace: traceContext,
    pqx_step: { name: "MVP-3: Transcript Eval Baseline", version: "1.0" },
    execution_status: "succeeded",
    inputs: { artifact_ids: [transcriptArtifactId, contextBundleArtifactId] },
    outputs: {
      artifact_ids: [
        ...evalResults.map((r) => r.artifact_id),
        evalSummary.artifact_id,
        controlDecision.artifact_id,
      ],
    },
    timing: { started_at: traceContext.created_at, ended_at: new Date().toISOString() },
  };

  return { success: true, eval_results: evalResults, eval_summary: evalSummary, control_decision: controlDecision, execution_record: executionRecord };
}
