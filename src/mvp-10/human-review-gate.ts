import { v4 as uuidv4 } from "uuid";
import type { ReviewArtifact, ReviewGatewayResult } from "./types";

/**
 * MVP-10: Human Review Gate
 * HUMAN-IN-THE-LOOP: Emits require_human_review enforcement_action
 * Pipeline pauses until review_artifact is submitted
 */

export async function emitHumanReviewRequest(
  draftArtifactId: string,
  evalSummary: any
): Promise<ReviewGatewayResult> {
  const traceId = uuidv4();
  const traceContext = { trace_id: traceId, created_at: new Date().toISOString() };

  const executionRecord = {
    artifact_kind: "enforcement_action",
    artifact_id: uuidv4(),
    action_type: "require_human_review",
    draft_artifact_id: draftArtifactId,
    eval_summary_id: evalSummary.artifact_id,
    status: "pending",
    message: "Human review required before proceeding to publication",
    created_at: new Date().toISOString(),
  };

  return {
    success: true,
    execution_record: executionRecord,
  };
}

export async function submitReview(
  reviewerId: string,
  draftArtifactId: string,
  decision: "approve" | "reject" | "revise",
  findings: any[]
): Promise<ReviewGatewayResult> {
  // Validate decision
  if (!["approve", "reject", "revise"].includes(decision)) {
    return {
      success: false,
      error: "Invalid decision",
    };
  }

  // Validate findings severity
  for (const finding of findings) {
    if (!["S0", "S1", "S2", "S3", "S4"].includes(finding.severity)) {
      return {
        success: false,
        error: `Invalid severity: ${finding.severity}`,
      };
    }
  }

  const reviewArtifact: ReviewArtifact = {
    artifact_kind: "review_artifact",
    artifact_id: uuidv4(),
    reviewer_id: reviewerId,
    decision,
    findings,
    timestamp: new Date().toISOString(),
  };

  const executionRecord = {
    artifact_kind: "pqx_execution_record",
    artifact_id: uuidv4(),
    pqx_step: { name: "MVP-10: Human Review Gate", version: "1.0" },
    execution_status: "succeeded",
    outputs: { artifact_ids: [reviewArtifact.artifact_id] },
  };

  return { success: true, review_artifact: reviewArtifact, execution_record: executionRecord };
}
