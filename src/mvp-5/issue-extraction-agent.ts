import { v4 as uuidv4 } from "uuid";
import { Anthropic } from "@anthropic-ai/sdk";
import type { Issue, IssueExtractionResult } from "./types";

const client = new Anthropic();

/**
 * MVP-5: Issue & Action Item Extraction
 *
 * Input: context_bundle (schema v2.3.0), meeting_minutes_artifact
 * Output: issue_registry_artifact with source traceability
 *
 * CRITICAL: Each issue must have source_turn_ref (traceable to transcript).
 */

export async function extractIssues(
  contextBundle: any,
  minutesArtifact: any
): Promise<IssueExtractionResult> {
  const traceId = uuidv4();
  const traceContext = {
    trace_id: traceId,
    created_at: new Date().toISOString(),
  };

  if (!contextBundle || typeof contextBundle !== "object") {
    return failClosed(traceContext, "context_bundle is required");
  }
  if (!minutesArtifact || typeof minutesArtifact !== "object") {
    return failClosed(traceContext, "meeting_minutes_artifact is required");
  }

  // Derive transcript text from context_items (new schema)
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

  // Read minutes payload from either new wrapped shape or flat shape
  const minutesPayload = {
    agenda_items:
      minutesArtifact.outputs?.agenda_items || minutesArtifact.agenda_items,
    decisions:
      minutesArtifact.outputs?.decisions || minutesArtifact.decisions,
    action_items:
      minutesArtifact.outputs?.action_items || minutesArtifact.action_items,
    attendees:
      minutesArtifact.outputs?.attendees || minutesArtifact.attendees,
  };

  const prompt = `Extract spectrum-relevant issues from meeting minutes and transcript.
Return ONLY valid JSON:

{
  "issues": [
    {
      "issue_id": "ISSUE-001",
      "type": "finding",
      "description": "Description of the issue",
      "priority": "high",
      "assignee": "name",
      "status": "open",
      "source_turn_ref": "Quote from transcript that identifies this issue"
    }
  ]
}

Meeting Minutes:
${JSON.stringify(minutesPayload, null, 2)}

Transcript (for context):
${transcriptContent}

Rules:
1. Extract ALL spectrum-relevant issues mentioned
2. CRITICAL: Include source_turn_ref for EVERY issue
3. source_turn_ref must be a direct quote from the transcript
4. Type can be: "finding", "action_item", or "risk"
5. Priority: "high", "medium", or "low"
6. Status: "open" or "closed"
7. assignee is optional
8. If no issues found, return empty issues array
9. Return ONLY valid JSON, nothing else
10. No markdown, no preamble, no explanation

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

    let issueData: { issues: Issue[] };
    try {
      issueData = JSON.parse(jsonMatch[0]);
    } catch (parseError) {
      throw new Error(`Invalid JSON from model: ${parseError}`);
    }

    if (!Array.isArray(issueData.issues)) {
      throw new Error("Invalid issue structure: missing issues array");
    }

    // Fail-closed if any issue is missing source_turn_ref (schema violation)
    for (const issue of issueData.issues) {
      if (!issue.source_turn_ref || issue.source_turn_ref.length === 0) {
        throw new Error(
          `Issue ${issue.issue_id} missing source_turn_ref (critical requirement)`
        );
      }
    }

    const sourceTranscriptId =
      contextBundle.metadata?.input_artifact_ids?.[0] ||
      primaryItem?.provenance_ref ||
      "unknown";

    const issueRegistry = {
      artifact_type: "issue_registry_artifact",
      schema_version: "1.0.0",
      artifact_id: uuidv4(),
      created_at: new Date().toISOString(),
      schema_ref: "artifacts/issue_registry_artifact.schema.json",
      trace: traceContext,
      source_transcript_id: sourceTranscriptId,
      source_context_bundle_id: contextBundle.context_bundle_id,
      source_minutes_id: minutesArtifact.artifact_id,
      issues: issueData.issues,
      extraction_model: "claude-haiku-4-5-20251001",
      content_hash: computeHash(JSON.stringify(issueData.issues)),
    };

    const executionRecord = {
      artifact_type: "pqx_execution_record",
      artifact_id: uuidv4(),
      created_at: new Date().toISOString(),
      trace: traceContext,
      pqx_step: {
        name: "MVP-5: Issue & Action Item Extraction",
        version: "1.0",
      },
      execution_status: "succeeded",
      inputs: {
        artifact_ids: [
          contextBundle.context_bundle_id,
          minutesArtifact.artifact_id,
        ],
      },
      outputs: { artifact_ids: [issueRegistry.artifact_id] },
      timing: {
        started_at: traceContext.created_at,
        ended_at: new Date().toISOString(),
      },
    };

    return {
      success: true,
      issue_registry_artifact: issueRegistry,
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
): IssueExtractionResult {
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
