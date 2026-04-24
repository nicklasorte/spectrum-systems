import { v4 as uuidv4 } from "uuid";
import { Anthropic } from "@anthropic-ai/sdk";
import type { MeetingMinutesOutput, MinutesExtractionResult } from "./types";

const client = new Anthropic();

/**
 * MVP-4: Meeting Minutes Extraction
 *
 * Input: context_bundle (schema v2.3.0)
 * Output: meeting_minutes_artifact
 *
 * Uses Claude Haiku to extract structured meeting minutes.
 * Output must conform to schema — no free-form text escapes.
 * Fails-closed on schema mismatch.
 */

export async function extractMeetingMinutes(
  contextBundle: any
): Promise<MinutesExtractionResult> {
  const traceId = uuidv4();
  const traceContext = {
    trace_id: traceId,
    created_at: new Date().toISOString(),
  };

  // Fail-closed on missing/invalid context bundle
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

  if (!transcriptContent || transcriptContent.length === 0) {
    return failClosed(traceContext, "context_bundle has no primary_input segments");
  }

  const prompt = `Extract structured meeting minutes from this transcript.
Return ONLY valid JSON matching this exact structure:

{
  "agenda_items": ["item1", "item2"],
  "decisions": [
    {
      "decision": "decision text",
      "rationale": "why this decision was made"
    }
  ],
  "action_items": [
    {
      "item": "action description",
      "owner": "person responsible",
      "due_date": "YYYY-MM-DD"
    }
  ],
  "attendees": ["name1", "name2"]
}

Transcript:
${transcriptContent}

Rules:
1. Be strict: only include items explicitly mentioned
2. Return ONLY valid JSON, nothing else
3. No markdown, no preamble, no explanation
4. agenda_items: list of discussion topics
5. decisions: each decision with its rationale
6. action_items: tasks assigned with owner (optional) and due date (optional)
7. attendees: people mentioned in transcript

JSON response:`;

  try {
    const response = await client.messages.create({
      model: "claude-haiku-4-5-20251001",
      max_tokens: 2000,
      messages: [{ role: "user", content: prompt }],
    });

    const textContent = response.content.find((c) => c.type === "text");
    if (!textContent || textContent.type !== "text") {
      throw new Error("No text response from model");
    }

    const jsonMatch = textContent.text.match(/\{[\s\S]*\}/);
    if (!jsonMatch) {
      throw new Error("Could not parse JSON from response");
    }

    let minutesData: Omit<MeetingMinutesOutput, "artifact_type" | "schema_version">;
    try {
      minutesData = JSON.parse(jsonMatch[0]);
    } catch (parseError) {
      throw new Error(`Invalid JSON from model: ${parseError}`);
    }

    // Validate structure (fail-closed)
    if (
      !Array.isArray(minutesData.agenda_items) ||
      !Array.isArray(minutesData.decisions) ||
      !Array.isArray(minutesData.action_items) ||
      !Array.isArray(minutesData.attendees)
    ) {
      throw new Error("Invalid minutes structure: missing required arrays");
    }

    const sourceTranscriptId =
      contextBundle.metadata?.input_artifact_ids?.[0] ||
      primaryItem?.provenance_ref ||
      "unknown";

    const minutesArtifact = {
      artifact_type: "meeting_minutes_artifact",
      schema_version: "1.0.0",
      artifact_id: uuidv4(),
      created_at: new Date().toISOString(),
      schema_ref: "artifacts/meeting_minutes_artifact.schema.json",
      trace: traceContext,
      source_transcript_id: sourceTranscriptId,
      source_context_bundle_id: contextBundle.context_bundle_id,
      ...minutesData,
      extraction_model: "claude-haiku-4-5-20251001",
      content_hash: computeHash(JSON.stringify(minutesData)),
    };

    const executionRecord = {
      artifact_type: "pqx_execution_record",
      artifact_id: uuidv4(),
      created_at: new Date().toISOString(),
      trace: traceContext,
      pqx_step: {
        name: "MVP-4: Meeting Minutes Extraction",
        version: "1.0",
      },
      execution_status: "succeeded",
      inputs: { artifact_ids: [contextBundle.context_bundle_id] },
      outputs: { artifact_ids: [minutesArtifact.artifact_id] },
      timing: {
        started_at: traceContext.created_at,
        ended_at: new Date().toISOString(),
      },
    };

    return {
      success: true,
      meeting_minutes_artifact: minutesArtifact,
      execution_record: executionRecord,
    };
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
): MinutesExtractionResult {
  return {
    success: false,
    error: message,
    error_codes: ["extraction_error"],
    execution_record: {
      artifact_type: "pqx_execution_record",
      artifact_id: uuidv4(),
      created_at: new Date().toISOString(),
      trace: traceContext,
      execution_status: "failed",
      failure: {
        reason_codes: ["extraction_error"],
        error_message: message,
      },
    },
  };
}

function computeHash(content: string): string {
  const crypto = require("crypto");
  const hash = crypto.createHash("sha256").update(content).digest("hex");
  return `sha256:${hash}`;
}
