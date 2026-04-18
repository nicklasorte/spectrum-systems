import { v4 as uuidv4 } from "uuid";
import type { FormattedPaperArtifact, PublicationFormattingResult } from "./types";

/**
 * MVP-12: Publication Formatting
 * Converts prose draft to publication-ready format
 * Applies formatting rules, generates metadata
 */

export async function formatPaperForPublication(
  draftArtifact: any,
  metadata?: { title?: string; authors?: string[] }
): Promise<PublicationFormattingResult> {
  const traceId = uuidv4();
  const traceContext = { trace_id: traceId, created_at: new Date().toISOString() };

  try {
    const sections = draftArtifact.sections || {};

    // Apply formatting rules (deterministic)
    const formattedSections: Record<string, string> = {};
    for (const [key, content] of Object.entries(sections)) {
      formattedSections[key] = applyFormatting(key, content as string);
    }

    const formattedPaper: FormattedPaperArtifact = {
      artifact_kind: "formatted_paper_artifact",
      artifact_id: uuidv4(),
      title: metadata?.title || "Spectrum Study Paper",
      sections: formattedSections,
      publication_metadata: {
        doi_placeholder: `10.5555/${uuidv4().substring(0, 8)}`,
        version: "1.0",
        authors: metadata?.authors || ["Spectrum Systems"],
        date: new Date().toISOString().split("T")[0],
      },
      content_hash: computeHash(JSON.stringify(formattedSections)),
    };

    const executionRecord = {
      artifact_kind: "pqx_execution_record",
      artifact_id: uuidv4(),
      pqx_step: { name: "MVP-12: Publication Formatting", version: "1.0" },
      execution_status: "succeeded",
      outputs: { artifact_ids: [formattedPaper.artifact_id] },
    };

    return { success: true, formatted_paper_artifact: formattedPaper, execution_record: executionRecord };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

function applyFormatting(sectionType: string, content: string): string {
  // Deterministic formatting rules
  const formatted = content
    .trim()
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .join("\n\n");

  return formatted;
}

function computeHash(content: string): string {
  const crypto = require("crypto");
  return `sha256:${crypto.createHash("sha256").update(JSON.stringify(content)).digest("hex")}`;
}
