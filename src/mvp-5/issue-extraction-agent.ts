import { v4 as uuidv4 } from "uuid";
import { Anthropic } from "@anthropic-ai/sdk";
import type { Issue, IssueExtractionResult } from "./types";

const client = new Anthropic();

/**
 * MVP-5: Issue Extraction
 * CRITICAL: Each issue must have source_turn_ref (traceable to transcript)
 */

export async function extractIssues(
  contextBundle: any,
  minutesArtifact: any
): Promise<IssueExtractionResult> {
  const traceId = uuidv4();
  const traceContext = { trace_id: traceId, created_at: new Date().toISOString() };

  const prompt = `Extract spectrum-relevant issues from meeting minutes and transcript.
Return ONLY valid JSON:

{
  "issues": [
    {
      "issue_id": "ISSUE-001",
      "type": "finding",
      "description": "Description",
      "priority": "high",
      "assignee": "name",
      "status": "open",
      "source_turn_ref": "Quote from transcript"
    }
  ]
}

Minutes: ${JSON.stringify(minutesArtifact, null, 2)}

Transcript: ${contextBundle.context.transcript_content}

Rules:
1. Extract ALL spectrum-relevant issues
2. CRITICAL: Include source_turn_ref for EVERY issue
3. source_turn_ref must be a direct quote from transcript
4. Type: "finding", "action_item", or "risk"
5. Priority: "high", "medium", or "low"
6. Status: "open" or "closed"
7. assignee optional
8. If no issues, return empty array
9. Return ONLY valid JSON

JSON response:`;

  try {
    const response = await client.messages.create({
      model: "claude-3-5-haiku-20241022",
      max_tokens: 2000,
      messages: [{ role: "user", content: prompt }],
    });

    const textContent = response.content.find((c) => c.type === "text");
    if (!textContent || textContent.type !== "text") throw new Error("No text response");

    const jsonMatch = textContent.text.match(/\{[\s\S]*\}/);
    if (!jsonMatch) throw new Error("Could not parse JSON");

    const issueData: { issues: Issue[] } = JSON.parse(jsonMatch[0]);
    if (!Array.isArray(issueData.issues)) throw new Error("Missing issues array");

    for (const issue of issueData.issues) {
      if (!issue.source_turn_ref) throw new Error(`Issue ${issue.issue_id} missing source_turn_ref`);
    }

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

    const executionRecord = {
      artifact_kind: "pqx_execution_record",
      artifact_id: uuidv4(),
      created_at: new Date().toISOString(),
      trace: traceContext,
      pqx_step: { name: "MVP-5: Issue Extraction", version: "1.0" },
      execution_status: "succeeded",
      inputs: { artifact_ids: [contextBundle.artifact_id, minutesArtifact.artifact_id] },
      outputs: { artifact_ids: [issueRegistry.artifact_id] },
      timing: { started_at: traceContext.created_at, ended_at: new Date().toISOString() },
    };

    return { success: true, issue_registry_artifact: issueRegistry, execution_record: executionRecord };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : String(error),
      error_codes: ["extraction_error"],
      execution_record: {
        artifact_kind: "pqx_execution_record",
        artifact_id: uuidv4(),
        execution_status: "failed",
        failure: { reason_codes: ["extraction_error"] },
      },
    };
  }
}

function computeHash(content: string): string {
  const crypto = require("crypto");
  return `sha256:${crypto.createHash("sha256").update(content).digest("hex")}`;
}
