import { v4 as uuidv4 } from "uuid";
import type { StructuredIssueSet, StructuredIssue, IssueStructuringResult } from "./types";

/**
 * MVP-7: Structured Issue Set
 * Reorganizes issues into structure required for paper generation
 * Maps each issue to target paper section
 */

export async function structureIssuesForPaper(
  issueRegistry: any
): Promise<IssueStructuringResult> {
  const traceId = uuidv4();
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

    // Verify all issues assigned to exactly one section
    if (structuredIssues.some((i) => !i.paper_section_id)) {
      throw new Error("Some issues could not be assigned to paper section");
    }

    const structuredSet: StructuredIssueSet = {
      artifact_kind: "structured_issue_set",
      artifact_id: uuidv4(),
      issues: structuredIssues,
      content_hash: computeHash(JSON.stringify(structuredIssues)),
    };

    const executionRecord = {
      artifact_kind: "pqx_execution_record",
      artifact_id: uuidv4(),
      pqx_step: { name: "MVP-7: Structured Issue Set", version: "1.0" },
      execution_status: "succeeded",
      outputs: { artifact_ids: [structuredSet.artifact_id] },
    };

    return { success: true, structured_issue_set: structuredSet, execution_record: executionRecord };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : String(error),
      execution_record: {
        artifact_kind: "pqx_execution_record",
        artifact_id: uuidv4(),
        execution_status: "failed",
      },
    };
  }
}

function determineSpectrumBand(issue: any): string {
  // Placeholder logic: would be more sophisticated in production
  if (issue.priority === "high") return "C"; // Critical
  if (issue.priority === "medium") return "L"; // Licensed
  return "S"; // Secondary
}

function determinePolicySection(issue: any): string {
  // Placeholder logic
  if (issue.type === "risk") return "risks";
  if (issue.type === "action_item") return "actions";
  return "findings";
}

function mapToSection(issue: any, section: string): string {
  // Map to paper section ID
  const sectionMap: Record<string, string> = {
    risks: "section-5",
    actions: "section-6",
    findings: "section-4",
  };
  return sectionMap[section] || "section-4";
}

function computeHash(content: string): string {
  const crypto = require("crypto");
  return `sha256:${crypto.createHash("sha256").update(content).digest("hex")}`;
}
