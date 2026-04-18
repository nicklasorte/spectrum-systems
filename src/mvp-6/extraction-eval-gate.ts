import { v4 as uuidv4 } from "uuid";
import { createArtifactStore, MemoryStorageBackend } from "@/src/artifact-store";
import type { ExtractionEvalGateResult } from "./types";

/**
 * MVP-6: Extraction Eval Gate
 * Gate-2: Validates extraction phase (Minutes + Issues)
 * 5 eval cases: schema, traceability, coverage, completeness, replay
 */

export async function runExtractionEvalGate(
  minutesArtifactId: string,
  issueArtifactId: string
): Promise<ExtractionEvalGateResult> {
  const backend = new MemoryStorageBackend();
  const store = createArtifactStore(backend);
  const traceId = uuidv4();
  const traceContext = { trace_id: traceId, created_at: new Date().toISOString() };

  const minutes = await store.retrieve(minutesArtifactId);
  const issues = await store.retrieve(issueArtifactId);

  if (!minutes || !issues) {
    return {
      success: false,
      error: "Missing artifacts",
      execution_record: {
        artifact_kind: "pqx_execution_record",
        artifact_id: uuidv4(),
        execution_status: "failed",
        failure: { reason_codes: ["missing_artifact"] },
      },
    };
  }

  const evalCases = [
    {
      name: "schema_conformance",
      check: () =>
        minutes.payload.artifact_kind === "meeting_minutes_artifact" &&
        issues.payload.artifact_kind === "issue_registry_artifact",
    },
    {
      name: "issue_source_traceability",
      check: () => {
        const issueList = issues.payload.issues || [];
        return issueList.every((i: any) => i.source_turn_ref && i.source_turn_ref.length > 0);
      },
    },
    {
      name: "agenda_coverage",
      check: () => (minutes.payload.agenda_items || []).length > 0,
    },
    {
      name: "action_item_completeness",
      check: () => {
        const actions = minutes.payload.action_items || [];
        return actions.every((a: any) => a.item && a.item.length > 0);
      },
    },
    {
      name: "replay_consistency",
      check: () => !!issues.payload.content_hash && issues.payload.content_hash.startsWith("sha256:"),
    },
  ];

  const evalResults: any[] = [];
  let passedCount = 0;

  for (const evalCase of evalCases) {
    const passed = evalCase.check();
    evalResults.push({
      artifact_kind: "eval_result",
      artifact_id: uuidv4(),
      status: passed ? "pass" : "fail",
      score: passed ? 100 : 0,
      details: { case_name: evalCase.name },
    });
    if (passed) passedCount++;
  }

  const passRate = (passedCount / evalCases.length) * 100;

  const evalSummary = {
    artifact_kind: "eval_summary",
    artifact_id: uuidv4(),
    overall_status: passRate === 100 ? "pass" : "fail",
    pass_rate: Math.round(passRate),
    metrics: { total_cases: evalCases.length, passed: passedCount, failed: evalCases.length - passedCount },
  };

  const controlDecision = {
    artifact_kind: "evaluation_control_decision",
    artifact_id: uuidv4(),
    decision: passRate === 100 ? "allow" : "block",
    rationale:
      passRate === 100
        ? "All extraction eval cases passed. Proceeding to paper generation."
        : `${passedCount}/${evalCases.length} cases passed. Blocking pipeline.`,
    eval_summary_id: evalSummary.artifact_id,
  };

  const executionRecord = {
    artifact_kind: "pqx_execution_record",
    artifact_id: uuidv4(),
    pqx_step: { name: "MVP-6: Extraction Eval Gate", version: "1.0" },
    execution_status: "succeeded",
    outputs: { artifact_ids: [evalSummary.artifact_id, controlDecision.artifact_id] },
  };

  return { success: true, eval_results: evalResults, eval_summary: evalSummary, control_decision: controlDecision, execution_record: executionRecord };
}
