import { v4 as uuidv4 } from "uuid";
import { Anthropic } from "@anthropic-ai/sdk";
import type { PaperDraftArtifact, PaperGenerationResult, PaperSection } from "./types";

const client = new Anthropic();

/**
 * MVP-8: Paper Draft Generation
 * HARDEST STEP: Section-by-section generation with validation
 * Strategy: Generate, validate immediately, retry up to 3 times, fail-closed on all failures
 * Model: Sonnet (high-quality prose)
 */

export async function generatePaperDraft(
  contextBundle: any,
  structuredIssueSet: any,
  minutesArtifact: any
): Promise<PaperGenerationResult> {
  const traceId = uuidv4();
  const traceContext = { trace_id: traceId, created_at: new Date().toISOString() };

  const sections = ["abstract", "introduction", "findings", "recommendations", "conclusion"];
  const generatedSections: Record<string, PaperSection> = {};

  try {
    for (const sectionType of sections) {
      let sectionContent: string | null = null;
      let retries = 0;
      const maxRetries = 3;

      while (!sectionContent && retries < maxRetries) {
        try {
          const prompt = buildSectionPrompt(
            sectionType,
            structuredIssueSet,
            minutesArtifact,
            contextBundle
          );

          const response = await client.messages.create({
            model: "claude-opus-4-20250514",
            max_tokens: 2000,
            messages: [{ role: "user", content: prompt }],
          });

          const textContent = response.content.find((c) => c.type === "text");
          if (!textContent || textContent.type !== "text") {
            throw new Error("No text response");
          }

          sectionContent = textContent.text;

          // Validate section immediately
          if (!validateSection(sectionType, sectionContent)) {
            sectionContent = null; // Force retry
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
        .filter((i: any) => i.paper_section_id === `section-${sections.indexOf(sectionType)}`)
        .map((i: any) => i.issue_id);

      generatedSections[sectionType] = {
        section_type: sectionType,
        content: sectionContent,
        source_issue_ids: sourceIssueIds,
      };
    }

    const paperDraft: PaperDraftArtifact = {
      artifact_kind: "paper_draft_artifact",
      artifact_id: uuidv4(),
      sections: generatedSections,
      source_issue_set_id: structuredIssueSet.artifact_id,
      generation_model: "claude-opus-4-20250514",
      content_hash: computeHash(JSON.stringify(generatedSections)),
    };

    const executionRecord = {
      artifact_kind: "pqx_execution_record",
      artifact_id: uuidv4(),
      pqx_step: { name: "MVP-8: Paper Draft Generation", version: "1.0" },
      execution_status: "succeeded",
      outputs: { artifact_ids: [paperDraft.artifact_id] },
    };

    return { success: true, paper_draft_artifact: paperDraft, execution_record: executionRecord };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : String(error),
      error_codes: ["generation_error"],
      execution_record: {
        artifact_kind: "pqx_execution_record",
        artifact_id: uuidv4(),
        execution_status: "failed",
        failure: { reason_codes: ["generation_error"] },
      },
    };
  }
}

function buildSectionPrompt(
  sectionType: string,
  issueSet: any,
  minutes: any,
  context: any
): string {
  const basePrompt = `You are writing a section of a spectrum study paper.

Section type: ${sectionType}
Context: ${JSON.stringify(context, null, 2)}
Issues: ${JSON.stringify(issueSet.issues, null, 2)}
Minutes: ${JSON.stringify(minutes, null, 2)}

Write the ${sectionType} section. Be professional, concise, and reference relevant issues.`;

  return basePrompt;
}

function validateSection(sectionType: string, content: string): boolean {
  // Basic validation: non-empty, some minimum length
  return content && content.length > 100;
}

function computeHash(content: string): string {
  const crypto = require("crypto");
  return `sha256:${crypto.createHash("sha256").update(content).digest("hex")}`;
}
