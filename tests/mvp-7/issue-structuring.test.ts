import { structureIssuesForPaper } from "@/src/mvp-7/issue-structuring";

describe("MVP-7: Structured Issue Set", () => {
  it("should structure issues for paper", async () => {
    const mockRegistry = {
      artifact_id: "reg-123",
      issues: [
        {
          issue_id: "ISSUE-001",
          type: "finding",
          priority: "high",
          source_turn_ref: "quote",
          description: "test finding",
          status: "open",
        },
      ],
    };

    const result = await structureIssuesForPaper(mockRegistry);
    expect(result.success).toBe(true);
    expect(result.structured_issue_set?.issues[0].paper_section_id).toBe("section-4");
  });

  it("should assign all issues to paper section", async () => {
    const mockRegistry = {
      artifact_id: "reg-123",
      issues: [
        {
          issue_id: "ISSUE-001",
          type: "finding",
          priority: "high",
          source_turn_ref: "q",
          description: "finding",
          status: "open",
        },
        {
          issue_id: "ISSUE-002",
          type: "risk",
          priority: "medium",
          source_turn_ref: "q",
          description: "risk",
          status: "open",
        },
        {
          issue_id: "ISSUE-003",
          type: "action_item",
          priority: "low",
          source_turn_ref: "q",
          description: "action",
          status: "open",
        },
      ],
    };

    const result = await structureIssuesForPaper(mockRegistry);
    expect(result.success).toBe(true);
    expect(result.structured_issue_set?.issues.length).toBe(3);
    expect(result.structured_issue_set?.issues.every((i) => i.paper_section_id)).toBe(true);
  });

  it("should map findings to section-4, risks to section-5, actions to section-6", async () => {
    const mockRegistry = {
      artifact_id: "reg-123",
      issues: [
        { issue_id: "F1", type: "finding", priority: "high", source_turn_ref: "q", description: "f", status: "open" },
        { issue_id: "R1", type: "risk", priority: "medium", source_turn_ref: "q", description: "r", status: "open" },
        { issue_id: "A1", type: "action_item", priority: "low", source_turn_ref: "q", description: "a", status: "open" },
      ],
    };

    const result = await structureIssuesForPaper(mockRegistry);
    expect(result.success).toBe(true);
    expect(result.structured_issue_set?.issues.find((i) => i.issue_id === "F1")?.paper_section_id).toBe("section-4");
    expect(result.structured_issue_set?.issues.find((i) => i.issue_id === "R1")?.paper_section_id).toBe("section-5");
    expect(result.structured_issue_set?.issues.find((i) => i.issue_id === "A1")?.paper_section_id).toBe("section-6");
  });
});
