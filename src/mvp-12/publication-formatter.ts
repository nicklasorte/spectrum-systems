import { randomUUID, createHash } from "crypto";
import type { FormattedPaperArtifact, PublicationFormattingResult } from "./types";

/**
 * MVP-12: Publication Formatting
 * Converts prose draft to publication-ready format.
 * Deterministic: same input produces same output.
 */

export async function formatPaperForPublication(
  draftArtifact: any,
  metadata?: { title?: string; authors?: string[] }
): Promise<PublicationFormattingResult> {
  const traceId = randomUUID();
  const traceContext = { trace_id: traceId, created_at: new Date().toISOString() };

  try {
    // Accept either draft.sections or draft.outputs.sections
    const rawSections: Record<string, any> =
      draftArtifact?.sections ??
      draftArtifact?.outputs?.sections ??
      {};

    const formattedSections: Record<string, string> = {};
    for (const [key, value] of Object.entries(rawSections)) {
      const content =
        typeof value === "string"
          ? value
          : value && typeof value === "object" && "content" in value
            ? String((value as any).content ?? "")
            : String(value ?? "");
      formattedSections[key] = applyFormatting(key, content);
    }

    const title = metadata?.title || "Spectrum Study Paper";
    const titleHashPrefix = createHash("sha256").update(title).digest("hex").substring(0, 8);

    const formattedPaper: FormattedPaperArtifact = {
      artifact_type: "formatted_paper_artifact",
      schema_version: "1.0.0",
      artifact_id: randomUUID(),
      created_at: new Date().toISOString(),
      schema_ref: "artifacts/formatted_paper_artifact.schema.json",
      trace: traceContext,
      title,
      sections: formattedSections,
      publication_metadata: {
        doi_placeholder: `10.5555/${titleHashPrefix}`,
        version: "1.0",
        authors: metadata?.authors || ["Spectrum Systems"],
        date: new Date().toISOString().split("T")[0],
      },
      content_hash: computeHash(JSON.stringify(formattedSections)),
    };

    const executionRecord = {
      artifact_type: "pqx_execution_record",
      artifact_id: randomUUID(),
      created_at: new Date().toISOString(),
      trace: traceContext,
      pqx_step: { name: "MVP-12: Publication Formatting", version: "1.0" },
      execution_status: "succeeded",
      inputs: { artifact_ids: [draftArtifact?.artifact_id ?? "unknown"] },
      outputs: { artifact_ids: [formattedPaper.artifact_id] },
      timing: { started_at: traceContext.created_at, ended_at: new Date().toISOString() },
    };

    return { success: true, formatted_paper_artifact: formattedPaper, execution_record: executionRecord };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return {
      success: false,
      error: message,
      error_codes: ["formatting_error"],
      execution_record: {
        artifact_type: "pqx_execution_record",
        artifact_id: randomUUID(),
        created_at: new Date().toISOString(),
        trace: traceContext,
        execution_status: "failed",
        failure: { reason_codes: ["formatting_error"], error_message: message },
      },
    };
  }
}

function applyFormatting(_sectionType: string, content: string): string {
  return content
    .trim()
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .join("\n\n");
}

function computeHash(content: string): string {
  return `sha256:${createHash("sha256").update(content).digest("hex")}`;
}
