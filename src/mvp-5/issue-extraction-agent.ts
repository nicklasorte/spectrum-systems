import { v4 as uuidv4 } from "uuid";
import { Anthropic } from "@anthropic-ai/sdk";
import type { Issue, IssueExtractionResult } from "./types";

const client = new Anthropic();

/**
 * MVP-5: Issue & Action Item Extraction
 *
 * Input: context_bundle, meeting_minutes_artifact
 * Output: issue_registry_artifact with source traceability
 *
 * Uses Claude Haiku to extract spectrum-relevant issues.
 * CRITICAL: Each issue must have source_turn_ref (traceable to transcript).
 *
 * LLM: Claude Haiku
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
${JSON.stringify(minutesArtifact, null, 2)}

Transcript (for context):
${contextBundle.context.transcript_content}

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
      model: "claude-3-5-haiku-20241022",
      max_tokens: 2000,
      messages: [{ role: "user", content: prompt }],
    });

    const textContent = response.content.find((c) => c.type === "text");
    if (!textContent || textContent.type !== "text") {
      throw new Error("No text response from model");
    }

    // Extract JSON
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

    // Validate structure
    if (!Array.isArray(issueData.issues)) {
      throw new Error("Invalid issue structure: missing issues array");
    }

    // Validate all issues have source_turn_ref (critical requirement)
    for (const issue of issueData.issues) {
      if (!issue.source_turn_ref) {
        throw new Error(
          `Issue ${issue.issue_id} missing source_turn_ref (critical requirement)`
        );
      }
    }

    // Build issue_registry_artifact
    const issueRegistry = {
      artifact_kind: "issue_registry_artifact",
      artifact_id: uuidv4(),
      created_at: new Date().toISOString(),
      schema_ref: "artifacts/issue_registry_artifact.schema.json",
      trace: traceContext,
      source_transcript_id: contextBundle.input_artifacts[0],
      source_context_bundle_id: contextBundle.artifact_id,
      source_minutes_id: minutesArtifact.artifact_id,
      issues: issueData.issues,
      extraction_model: "claude-3-5-haiku-20241022",
      content_hash: computeHash(JSON.stringify(issueData.issues)),
    };

    // Emit execution record
    const executionRecord = {
      artifact_kind: "pqx_execution_record",
      artifact_id: uuidv4(),
      created_at: new Date().toISOString(),
      trace: traceContext,
      pqx_step: {
        name: "MVP-5: Issue & Action Item Extraction",
        version: "1.0",
      },
      execution_status: "succeeded",
      inputs: { artifact_ids: [contextBundle.artifact_id, minutesArtifact.artifact_id] },
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
