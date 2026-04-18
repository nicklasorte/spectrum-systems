import { v4 as uuidv4 } from "uuid";
import { Anthropic } from "@anthropic-ai/sdk";
import type { RevisionFinding, RevisedDraftArtifact, RevisionIntegrationResult } from "./types";

const client = new Anthropic();

/**
 * MVP-11: Revision Integration
 * Applies reviewer findings to draft
 * Tracks provenance: finding_id → change
 * Model: Sonnet (targeted prose revision)
 */

export async function integrateRevisions(
  draftArtifact: any,
  reviewArtifact: any
): Promise<RevisionIntegrationResult> {
  const traceId = uuidv4();
  const traceContext = { trace_id: traceId, created_at: new Date().toISOString() };

  // If decision is "approve", pass through unchanged
  if (reviewArtifact.decision === "approve") {
    const revisedDraft: RevisedDraftArtifact = {
      artifact_kind: "revised_draft_artifact",
      artifact_id: uuidv4(),
      sections: draftArtifact.sections,
      revision_diff: [],
      source_draft_id: draftArtifact.artifact_id,
      content_hash: computeHash(JSON.stringify(draftArtifact.sections)),
    };

    return { success: true, revised_draft_artifact: revisedDraft };
  }

  // For "revise" decision, apply findings
  const revisedSections = { ...draftArtifact.sections };
  const revisionDiff: RevisionFinding[] = [];

  try {
    for (const finding of reviewArtifact.findings) {
      if (["S2", "S3", "S4"].includes(finding.severity)) {
        // Apply revision for S2+ findings
        const sectionType = finding.section;
        const sectionContent = revisedSections[sectionType];

        if (sectionContent) {
          const prompt = `Revise this section based on the reviewer finding.

Original: ${sectionContent}

Finding: ${finding.comment}

Provide ONLY the revised section text, no explanation.`;

          const response = await client.messages.create({
            model: "claude-opus-4-20250514",
            max_tokens: 2000,
            messages: [{ role: "user", content: prompt }],
          });

          const textContent = response.content.find((c) => c.type === "text");
          if (textContent && textContent.type === "text") {
            revisedSections[sectionType] = textContent.text;

            revisionDiff.push({
              finding_id: uuidv4(),
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
      artifact_kind: "revised_draft_artifact",
      artifact_id: uuidv4(),
      sections: revisedSections,
      revision_diff: revisionDiff,
      source_draft_id: draftArtifact.artifact_id,
      content_hash: computeHash(JSON.stringify(revisedSections)),
    };

    const executionRecord = {
      artifact_kind: "pqx_execution_record",
      artifact_id: uuidv4(),
      pqx_step: { name: "MVP-11: Revision Integration", version: "1.0" },
      execution_status: "succeeded",
      outputs: { artifact_ids: [revisedDraft.artifact_id] },
    };

    return { success: true, revised_draft_artifact: revisedDraft, execution_record: executionRecord };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

function computeHash(content: string): string {
  const crypto = require("crypto");
  return `sha256:${crypto.createHash("sha256").update(JSON.stringify(content)).digest("hex")}`;
}
