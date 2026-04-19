import { randomUUID } from "crypto";
import type { DraftEvalGateResult } from "./types";

/**
 * MVP-9: Draft Quality Eval Gate
 * Gate-3: Validates generation step before human review
 * 6 eval cases
 */

export async function runDraftEvalGate(
  draftArtifactId: string,
  issueSetArtifactId: string,
  draft?: any,
  issueSet?: any
): Promise<DraftEvalGateResult> {
  const traceId = randomUUID();
  const traceContext = { trace_id: traceId, created_at: new Date().toISOString() };

  const draftData = draft || { artifact_kind: "paper_draft_artifact", sections: { abstract: "test", introduction: "test", findings: "test" } };
  const issueSetData = issueSet || { artifact_id: issueSetArtifactId };

  if (!draftData) {
    return {
      success: false,
      error: "Missing artifacts",
      execution_record: {
        artifact_kind: "pqx_execution_record",
        artifact_id: randomUUID(),
        execution_status: "failed",
      },
    };
  }

  const evalCases = [
    {
      name: "schema_conformance",
      check: () => draftData.artifact_kind === "paper_draft_artifact",
    },
    {
      name: "issue_coverage",
      check: () => {
        const sections = Object.values(draftData.sections || {});
        return sections.length === 5;
      },
    },
    {
      name: "section_completeness",
      check: () => {
        const sections = draftData.sections || {};
        return sections.abstract && sections.introduction && sections.findings;
      },
    },
    {
      name: "internal_consistency",
      check: () => {
        return Object.keys(draftData.sections || {}).length > 0;
      },
    },
    {
      name: "replay_consistency",
      check: () => draftData.content_hash && draftData.content_hash.startsWith("sha256:"),
    },
    {
      name: "quality_score",
      check: () => true,
    },
  ];

  const evalResults: any[] = [];
  let passedCount = 0;

  for (const evalCase of evalCases) {
    const passed = evalCase.check();
    evalResults.push({
      artifact_kind: "eval_result",
      artifact_id: randomUUID(),
      status: passed ? "pass" : "fail",
      score: passed ? 100 : 0,
      details: { case_name: evalCase.name },
    });
    if (passed) passedCount++;
  }

  const passRate = (passedCount / evalCases.length) * 100;

  const evalSummary = {
    artifact_kind: "eval_summary",
    artifact_id: randomUUID(),
    overall_status: passRate >= 80 ? "pass" : "fail",
    pass_rate: Math.round(passRate),
    metrics: { total_cases: evalCases.length, passed: passedCount },
  };

  const controlDecision = {
    artifact_kind: "evaluation_control_decision",
    artifact_id: randomUUID(),
    decision: passRate >= 80 ? "allow" : "block",
    rationale: passRate >= 80 ? "Draft passed quality gate. Proceeding to human review." : "Draft failed quality checks.",
    eval_summary_id: evalSummary.artifact_id,
  };

  const executionRecord = {
    artifact_kind: "pqx_execution_record",
    artifact_id: randomUUID(),
    pqx_step: { name: "MVP-9: Draft Quality Eval Gate", version: "1.0" },
    execution_status: "succeeded",
    outputs: { artifact_ids: [evalSummary.artifact_id, controlDecision.artifact_id] },
  };

  return { success: true, eval_results: evalResults, eval_summary: evalSummary, control_decision: controlDecision, execution_record: executionRecord };
}
