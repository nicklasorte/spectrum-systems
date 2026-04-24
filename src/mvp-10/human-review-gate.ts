import { randomUUID } from "crypto";
import type { ReviewArtifact, ReviewGatewayResult } from "./types";

/**
 * MVP-10: Human Review Gate
 * Human-in-the-loop. Emits require_human_review enforcement_action.
 * Pipeline pauses until review_artifact is submitted.
 */

const VALID_SEVERITIES = ["S0", "S1", "S2", "S3", "S4"];
const VALID_DECISIONS = ["approve", "reject", "revise"];

export async function emitHumanReviewRequest(
  draftArtifactId: string,
  _evalSummary: any
): Promise<ReviewGatewayResult> {
  const traceContext = {
    trace_id: randomUUID(),
    created_at: new Date().toISOString(),
  };

  const enforcementAction = {
    artifact_type: "enforcement_action",
    artifact_id: randomUUID(),
    created_at: new Date().toISOString(),
    trace: traceContext,
    action_type: "require_human_review",
    draft_artifact_id: draftArtifactId,
    status: "pending",
  };

  return { success: true, execution_record: enforcementAction };
}

export async function submitReview(
  reviewerId: string,
  _draftArtifactId: string,
  decision: "approve" | "reject" | "revise",
  findings: any[]
): Promise<ReviewGatewayResult> {
  const traceContext = {
    trace_id: randomUUID(),
    created_at: new Date().toISOString(),
  };

  // TPA reviewer identity enforcement
  if (!reviewerId || typeof reviewerId !== "string" || reviewerId.length < 3) {
    return failClosed(
      traceContext,
      ["missing_reviewer_identity"],
      `Reviewer identity is required and must be at least 3 characters (got: ${JSON.stringify(reviewerId)})`
    );
  }

  if (!VALID_DECISIONS.includes(decision)) {
    return failClosed(
      traceContext,
      ["invalid_decision"],
      `Invalid decision: ${decision}`
    );
  }

  if (!Array.isArray(findings)) {
    return failClosed(
      traceContext,
      ["invalid_findings"],
      "findings must be an array"
    );
  }

  for (const finding of findings) {
    if (!VALID_SEVERITIES.includes(finding.severity)) {
      return failClosed(
        traceContext,
        ["invalid_severity"],
        `Invalid severity: ${finding.severity}`
      );
    }
  }

  const reviewArtifact: ReviewArtifact = {
    artifact_type: "review_artifact",
    schema_version: "1.0.0",
    artifact_id: randomUUID(),
    reviewer_id: reviewerId,
    decision,
    findings: findings.map((f) => ({
      finding_id: f.finding_id || randomUUID(),
      section: f.section,
      comment: f.comment,
      severity: f.severity,
    })),
    timestamp: new Date().toISOString(),
  };

  const executionRecord = {
    artifact_type: "pqx_execution_record",
    artifact_id: randomUUID(),
    created_at: new Date().toISOString(),
    trace: traceContext,
    pqx_step: { name: "MVP-10: Human Review Gate", version: "1.0" },
    execution_status: "succeeded",
    outputs: { artifact_ids: [reviewArtifact.artifact_id] },
  };

  return { success: true, review_artifact: reviewArtifact, execution_record: executionRecord };
}

function failClosed(
  traceContext: { trace_id: string; created_at: string },
  errorCodes: string[],
  message: string
): ReviewGatewayResult {
  return {
    success: false,
    error: message,
    error_codes: errorCodes,
    execution_record: {
      artifact_type: "pqx_execution_record",
      artifact_id: randomUUID(),
      created_at: new Date().toISOString(),
      trace: traceContext,
      execution_status: "failed",
      failure: { reason_codes: errorCodes, error_message: message },
    },
  };
}
