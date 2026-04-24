import { randomUUID } from "crypto";
import type { StructuredIssueSet, StructuredIssue, IssueStructuringResult } from "./types";

/**
 * MVP-7: Structured Issue Set
 * Reorganizes issues into structure required for paper generation
 * Maps each issue to target paper section
 */

export async function structureIssuesForPaper(
  issueRegistry: any
): Promise<IssueStructuringResult> {
  const traceId = randomUUID();
  const traceContext = { trace_id: traceId, created_at: new Date().toISOString() };

  try {
    const structuredIssues: StructuredIssue[] = (issueRegistry.issues || []).map((issue: any) => {
      const spectrum_band = determineSpectrumBand(issue);
      const policy_section = determinePolicySection(issue);
      const paper_section_id = mapToSection(issue, policy_section);

      return {
        ...issue,
        spectrum_band,
        policy_section,
        paper_section_id,
      };
    });

    if (structuredIssues.some((i) => !i.paper_section_id)) {
      throw new Error("Some issues could not be assigned to paper section");
    }

    const structuredSet: StructuredIssueSet = {
      artifact_type: "structured_issue_set",
      schema_version: "1.0.0",
      artifact_id: randomUUID(),
      created_at: new Date().toISOString(),
      schema_ref: "artifacts/structured_issue_set.schema.json",
      trace: traceContext,
      issues: structuredIssues,
      content_hash: computeHash(JSON.stringify(structuredIssues)),
    };

    const executionRecord = {
      artifact_type: "pqx_execution_record",
      artifact_id: randomUUID(),
      created_at: new Date().toISOString(),
      trace: traceContext,
      pqx_step: { name: "MVP-7: Structured Issue Set", version: "1.0" },
      execution_status: "succeeded",
      inputs: { artifact_ids: [issueRegistry.artifact_id] },
      outputs: { artifact_ids: [structuredSet.artifact_id] },
      timing: { started_at: traceContext.created_at, ended_at: new Date().toISOString() },
    };

    return { success: true, structured_issue_set: structuredSet, execution_record: executionRecord };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : String(error),
      execution_record: {
        artifact_type: "pqx_execution_record",
        artifact_id: randomUUID(),
        created_at: new Date().toISOString(),
        trace: traceContext,
        execution_status: "failed",
        failure: { reason_codes: ["structuring_error"] },
      },
    };
  }
}

function determineSpectrumBand(issue: any): string {
  if (issue.priority === "high") return "C";
  if (issue.priority === "medium") return "L";
  return "S";
}

function determinePolicySection(issue: any): string {
  if (issue.type === "risk") return "risks";
  if (issue.type === "action_item") return "actions";
  return "findings";
}

function mapToSection(_issue: any, section: string): string {
  const sectionMap: Record<string, string> = {
    risks: "section-5",
    actions: "section-6",
    findings: "section-4",
  };
  return sectionMap[section] || "section-4";
}

function computeHash(content: string): string {
  const { createHash } = require("crypto");
  return `sha256:${createHash("sha256").update(content).digest("hex")}`;
}
