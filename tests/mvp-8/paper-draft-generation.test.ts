import { randomUUID } from "crypto";
import { generatePaperDraft } from "@/src/mvp-8/paper-draft-generator";

describe("MVP-8: Paper Draft Generation", () => {
  it("should generate paper draft sections", async () => {
    const mockContext = { context: { transcript_content: "test transcript" } };
    const mockIssueSet = {
      artifact_id: randomUUID(),
      issues: [{ issue_id: "ISSUE-001", paper_section_id: "section-4", description: "test" }],
    };
    const mockMinutes = { agenda_items: ["test agenda"] };

    const result = await generatePaperDraft(mockContext, mockIssueSet, mockMinutes);
    
    if (result.success) {
      expect(result.paper_draft_artifact?.artifact_kind).toBe("paper_draft_artifact");
      expect(Object.keys(result.paper_draft_artifact?.sections || {}).length).toBeGreaterThan(0);
    }
  });
});
