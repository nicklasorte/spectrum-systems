import { randomUUID } from "crypto";
import type { ReviewArtifact, ReviewGatewayResult } from "./types";

/**
 * MVP-10: Human Review Gate
 * HUMAN-IN-THE-LOOP: Emits require_human_review enforcement_action
 * Pipeline pauses until review_artifact submitted
 */

export async function emitHumanReviewRequest(
  draftArtifactId: string,
  evalSummary: any
): Promise<ReviewGatewayResult> {
  const traceContext = { trace_id: randomUUID(), created_at: new Date().toISOString() };

  const executionRecord = {
    artifact_kind: "enforcement_action",
    artifact_id: randomUUID(),
    action_type: "require_human_review",
    draft_artifact_id: draftArtifactId,
    status: "pending",
    created_at: new Date().toISOString(),
  };

  return { success: true, execution_record: executionRecord };
}

export async function submitReview(
  reviewerId: string,
  draftArtifactId: string,
  decision: "approve" | "reject" | "revise",
  findings: any[]
): Promise<ReviewGatewayResult> {
  if (!["approve", "reject", "revise"].includes(decision)) {
    return { success: false, error: "Invalid decision" };
  }

  for (const finding of findings) {
    if (!["S0", "S1", "S2", "S3", "S4"].includes(finding.severity)) {
      return { success: false, error: `Invalid severity: ${finding.severity}` };
    }
  }

  const reviewArtifact: ReviewArtifact = {
    artifact_kind: "review_artifact",
    artifact_id: randomUUID(),
    reviewer_id: reviewerId,
    decision,
    findings,
    timestamp: new Date().toISOString(),
  };

  const executionRecord = {
    artifact_kind: "pqx_execution_record",
    artifact_id: randomUUID(),
    pqx_step: { name: "MVP-10: Human Review Gate", version: "1.0" },
    execution_status: "succeeded",
    outputs: { artifact_ids: [reviewArtifact.artifact_id] },
  };

  return { success: true, review_artifact: reviewArtifact, execution_record: executionRecord };
}
