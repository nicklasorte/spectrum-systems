import { structureIssuesForPaper } from "@/src/mvp-7/issue-structuring";

describe("MVP-7: Structured Issue Set", () => {
  it("should structure issues for paper", async () => {
    const mockRegistry = {
      issues: [
        {
          issue_id: "ISSUE-001",
          type: "finding",
          priority: "high",
          source_turn_ref: "quote",
        },
      ],
    };

    const result = await structureIssuesForPaper(mockRegistry);
    expect(result.success).toBe(true);
    expect(result.structured_issue_set?.issues[0].paper_section_id).toBeDefined();
  });

  it("should assign all issues to paper section", async () => {
    const mockRegistry = {
      issues: [
        { issue_id: "ISSUE-001", type: "finding", priority: "high", source_turn_ref: "q" },
        { issue_id: "ISSUE-002", type: "risk", priority: "medium", source_turn_ref: "q" },
      ],
    };

    const result = await structureIssuesForPaper(mockRegistry);
    expect(result.success).toBe(true);
    expect(result.structured_issue_set?.issues.length).toBe(2);
    expect(result.structured_issue_set?.issues.every((i) => i.paper_section_id)).toBe(true);
  });
});
