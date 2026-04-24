import { randomUUID } from "crypto";
import { Anthropic } from "@anthropic-ai/sdk";
import type { PaperDraftArtifact, PaperGenerationResult, PaperSection } from "./types";

const client = new Anthropic();

/**
 * MVP-8: Paper Draft Generation
 * Section-by-section generation with validation.
 * Strategy: Generate, validate immediately, retry up to 3 times, fail-closed.
 */

export async function generatePaperDraft(
  contextBundle: any,
  structuredIssueSet: any,
  minutesArtifact: any
): Promise<PaperGenerationResult> {
  const traceId = randomUUID();
  const traceContext = { trace_id: traceId, created_at: new Date().toISOString() };

  if (!contextBundle || typeof contextBundle !== "object") {
    return failClosed(traceContext, "context_bundle is required");
  }

  // Derive transcript text from context_items (new schema, not contextBundle.context.*)
  const primaryItem = contextBundle.context_items?.find(
    (item: any) => item.item_type === "primary_input"
  );
  const segments: any[] = primaryItem?.content || [];
  const transcriptContent = segments
    .map((s: any) => `${s.speaker}: ${s.text}`)
    .join("\n");

  const sectionNames = ["abstract", "introduction", "findings", "recommendations", "conclusion"];
  const generatedSections: Record<string, PaperSection> = {};

  try {
    for (const sectionType of sectionNames) {
      let sectionContent: string | null = null;
      let retries = 0;
      const maxRetries = 3;

      while (!sectionContent && retries < maxRetries) {
        try {
          const prompt = buildSectionPrompt(
            sectionType,
            structuredIssueSet,
            minutesArtifact,
            transcriptContent
          );

          const response = await client.messages.create({
            model: "claude-sonnet-4-20250514",
            max_tokens: 2000,
            messages: [{ role: "user", content: prompt }],
          });

          const textContent = response.content.find((c) => c.type === "text");
          if (!textContent || textContent.type !== "text") {
            throw new Error("No text response");
          }

          sectionContent = textContent.text;

          if (!validateSection(sectionType, sectionContent)) {
            sectionContent = null;
          }
        } catch (error) {
          retries++;
          if (retries >= maxRetries) {
            throw new Error(`Section ${sectionType} failed after ${maxRetries} retries`);
          }
        }
      }

      if (!sectionContent) {
        throw new Error(`Could not generate valid ${sectionType} section`);
      }

      const sourceIssueIds = (structuredIssueSet.issues || [])
        .filter((i: any) => i.paper_section_id === `section-${sectionNames.indexOf(sectionType) + 3}`)
        .map((i: any) => i.issue_id);

      generatedSections[sectionType] = {
        section_type: sectionType,
        content: sectionContent,
        source_issue_ids: sourceIssueIds,
      };
    }

    const paperDraft: PaperDraftArtifact = {
      artifact_type: "paper_draft_artifact",
      schema_version: "1.0.0",
      artifact_id: randomUUID(),
      created_at: new Date().toISOString(),
      schema_ref: "artifacts/paper_draft_artifact.schema.json",
      trace: traceContext,
      sections: generatedSections,
      source_issue_set_id: structuredIssueSet?.artifact_id ?? "unknown",
      generation_model: "claude-sonnet-4-20250514",
      content_hash: computeHash(JSON.stringify(generatedSections)),
    };

    const executionRecord = {
      artifact_type: "pqx_execution_record",
      artifact_id: randomUUID(),
      created_at: new Date().toISOString(),
      trace: traceContext,
      pqx_step: { name: "MVP-8: Paper Draft Generation", version: "1.0" },
      execution_status: "succeeded",
      inputs: { artifact_ids: [structuredIssueSet?.artifact_id] },
      outputs: { artifact_ids: [paperDraft.artifact_id] },
      timing: { started_at: traceContext.created_at, ended_at: new Date().toISOString() },
    };

    return { success: true, paper_draft_artifact: paperDraft, execution_record: executionRecord };
  } catch (error) {
    return failClosed(
      traceContext,
      error instanceof Error ? error.message : String(error)
    );
  }
}

function failClosed(
  traceContext: { trace_id: string; created_at: string },
  message: string
): PaperGenerationResult {
  return {
    success: false,
    error: message,
    error_codes: ["generation_error"],
    execution_record: {
      artifact_type: "pqx_execution_record",
      artifact_id: randomUUID(),
      created_at: new Date().toISOString(),
      trace: traceContext,
      execution_status: "failed",
      failure: { reason_codes: ["generation_error"], error_message: message },
    },
  };
}

function buildSectionPrompt(
  sectionType: string,
  issueSet: any,
  minutes: any,
  transcriptContent: string
): string {
  const issues = issueSet?.issues || [];
  return `Write a ${sectionType} section for a spectrum study paper.

Transcript excerpt:
${transcriptContent.slice(0, 500)}

Issues: ${JSON.stringify(issues.slice(0, 3))}
Minutes: ${JSON.stringify(minutes || {}, null, 2).slice(0, 500)}

Write ${sectionType} professionally and concisely.`;
}

function validateSection(_sectionType: string, content: string): boolean {
  return !!(content && content.length > 100);
}

function computeHash(content: string): string {
  const { createHash } = require("crypto");
  return `sha256:${createHash("sha256").update(content).digest("hex")}`;
}
