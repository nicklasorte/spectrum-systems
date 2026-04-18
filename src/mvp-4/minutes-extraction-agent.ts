import { v4 as uuidv4 } from "uuid";
import { Anthropic } from "@anthropic-ai/sdk";
import type { MeetingMinutesOutput, MinutesExtractionResult } from "./types";

const client = new Anthropic();

/**
 * MVP-4: Meeting Minutes Extraction
 *
 * Input: context_bundle
 * Output: meeting_minutes_artifact
 *
 * Uses Claude Haiku to extract structured meeting minutes.
 * Output must conform to schema — no free-form text escapes.
 * Fails-closed on schema mismatch.
 *
 * LLM: Claude Haiku (structured extraction, low complexity)
 */

export async function extractMeetingMinutes(
  contextBundle: any
): Promise<MinutesExtractionResult> {
  const traceId = uuidv4();
  const traceContext = {
    trace_id: traceId,
    created_at: new Date().toISOString(),
  };

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
${contextBundle.context.transcript_content}

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
      model: "claude-3-5-haiku-20241022",
      max_tokens: 2000,
      messages: [{ role: "user", content: prompt }],
    });

    const textContent = response.content.find((c) => c.type === "text");
    if (!textContent || textContent.type !== "text") {
      throw new Error("No text response from model");
    }

    // Extract JSON from response
    const jsonMatch = textContent.text.match(/\{[\s\S]*\}/);
    if (!jsonMatch) {
      throw new Error("Could not parse JSON from response");
    }

    let minutesData: MeetingMinutesOutput;
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

    // Build meeting_minutes_artifact
    const minutesArtifact = {
      artifact_kind: "meeting_minutes_artifact",
      artifact_id: uuidv4(),
      created_at: new Date().toISOString(),
      schema_ref: "artifacts/meeting_minutes_artifact.schema.json",
      trace: traceContext,
      source_transcript_id: contextBundle.input_artifacts[0],
      source_context_bundle_id: contextBundle.artifact_id,
      ...minutesData,
      extraction_model: "claude-3-5-haiku-20241022",
      content_hash: computeHash(JSON.stringify(minutesData)),
    };

    // Emit execution record
    const executionRecord = {
      artifact_kind: "pqx_execution_record",
      artifact_id: uuidv4(),
      created_at: new Date().toISOString(),
      trace: traceContext,
      pqx_step: {
        name: "MVP-4: Meeting Minutes Extraction",
        version: "1.0",
      },
      execution_status: "succeeded",
      inputs: { artifact_ids: [contextBundle.artifact_id] },
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
    return {
      success: false,
      error: error instanceof Error ? error.message : String(error),
      error_codes: ["extraction_error"],
      execution_record: {
        artifact_kind: "pqx_execution_record",
        artifact_id: uuidv4(),
        created_at: new Date().toISOString(),
        execution_status: "failed",
        failure: {
          reason_codes: ["extraction_error"],
          error_message: error instanceof Error ? error.message : String(error),
        },
      },
    };
  }
}

function computeHash(content: string): string {
  const crypto = require("crypto");
  const hash = crypto.createHash("sha256").update(content).digest("hex");
  return `sha256:${hash}`;
}
