import { randomUUID, createHash } from "crypto";
import { Anthropic } from "@anthropic-ai/sdk";
import type { RevisionFinding, RevisedDraftArtifact, RevisionIntegrationResult } from "./types";

const client = new Anthropic();

/**
 * MVP-11: Revision Integration
 * Applies reviewer findings to draft. Tracks provenance: finding_id → change.
 */

export async function integrateRevisions(
  draftArtifact: any,
  reviewArtifact: any
): Promise<RevisionIntegrationResult> {
  const traceId = randomUUID();
  const traceContext = { trace_id: traceId, created_at: new Date().toISOString() };

  // Fail-closed on "reject" decision
  if (reviewArtifact?.decision === "reject") {
    return {
      success: false,
      error: "Draft was rejected during review",
      error_codes: ["draft_rejected"],
      execution_record: {
        artifact_type: "pqx_execution_record",
        artifact_id: randomUUID(),
        created_at: new Date().toISOString(),
        trace: traceContext,
        pqx_step: { name: "MVP-11: Revision Integration", version: "1.0" },
        execution_status: "failed",
        failure: {
          reason_codes: ["draft_rejected"],
          error_message: "Draft was rejected during human review",
        },
      },
    };
  }

  // Approve path: pass through unchanged
  if (reviewArtifact?.decision === "approve") {
    const revisedDraft: RevisedDraftArtifact = {
      artifact_type: "revised_draft_artifact",
      schema_version: "1.0.0",
      artifact_id: randomUUID(),
      created_at: new Date().toISOString(),
      schema_ref: "artifacts/revised_draft_artifact.schema.json",
      trace: traceContext,
      sections: draftArtifact?.sections || {},
      revision_diff: [],
      source_draft_id: draftArtifact?.artifact_id ?? "unknown",
      content_hash: computeHash(JSON.stringify(draftArtifact?.sections || {})),
    };

    const executionRecord = {
      artifact_type: "pqx_execution_record",
      artifact_id: randomUUID(),
      created_at: new Date().toISOString(),
      trace: traceContext,
      pqx_step: { name: "MVP-11: Revision Integration", version: "1.0" },
      execution_status: "succeeded",
      outputs: { artifact_ids: [revisedDraft.artifact_id] },
    };

    return { success: true, revised_draft_artifact: revisedDraft, execution_record: executionRecord };
  }

  // Revise path
  const revisedSections: Record<string, any> = { ...(draftArtifact?.sections || {}) };
  const revisionDiff: RevisionFinding[] = [];

  try {
    for (const finding of reviewArtifact?.findings || []) {
      if (["S2", "S3", "S4"].includes(finding.severity)) {
        const sectionType = finding.section;
        const existing = revisedSections[sectionType];
        const sectionText =
          typeof existing === "string"
            ? existing
            : existing && typeof existing === "object" && "content" in existing
              ? existing.content
              : "";

        if (sectionText) {
          const prompt = `Revise this section based on reviewer finding.\n\nOriginal: ${sectionText.substring(0, 200)}...\n\nFinding: ${finding.comment}\n\nProvide only the revised section text.`;

          const response = await client.messages.create({
            model: "claude-sonnet-4-20250514",
            max_tokens: 2000,
            messages: [{ role: "user", content: prompt }],
          });

          const textContent = response.content.find((c) => c.type === "text");
          if (textContent && textContent.type === "text") {
            if (typeof existing === "object" && existing !== null) {
              revisedSections[sectionType] = { ...existing, content: textContent.text };
            } else {
              revisedSections[sectionType] = textContent.text;
            }

            revisionDiff.push({
              finding_id: finding.finding_id || randomUUID(),
              section: sectionType,
              comment: finding.comment,
              severity: finding.severity,
              change_applied: `Applied revision to ${sectionType}`,
            });
          }
        }
      }
    }

    const revisedDraft: RevisedDraftArtifact = {
      artifact_type: "revised_draft_artifact",
      schema_version: "1.0.0",
      artifact_id: randomUUID(),
      created_at: new Date().toISOString(),
      schema_ref: "artifacts/revised_draft_artifact.schema.json",
      trace: traceContext,
      sections: revisedSections,
      revision_diff: revisionDiff,
      source_draft_id: draftArtifact?.artifact_id ?? "unknown",
      content_hash: computeHash(JSON.stringify(revisedSections)),
    };

    const executionRecord = {
      artifact_type: "pqx_execution_record",
      artifact_id: randomUUID(),
      created_at: new Date().toISOString(),
      trace: traceContext,
      pqx_step: { name: "MVP-11: Revision Integration", version: "1.0" },
      execution_status: "succeeded",
      outputs: { artifact_ids: [revisedDraft.artifact_id] },
    };

    return { success: true, revised_draft_artifact: revisedDraft, execution_record: executionRecord };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return {
      success: false,
      error: message,
      error_codes: ["revision_error"],
      execution_record: {
        artifact_type: "pqx_execution_record",
        artifact_id: randomUUID(),
        created_at: new Date().toISOString(),
        trace: traceContext,
        execution_status: "failed",
        failure: { reason_codes: ["revision_error"], error_message: message },
      },
    };
  }
}

function computeHash(content: string): string {
  return `sha256:${createHash("sha256").update(content).digest("hex")}`;
}
