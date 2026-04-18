import { generatePaperDraft } from "@/src/mvp-8/paper-draft-generator";
import { v4 as uuidv4 } from "uuid";

describe("MVP-8: Paper Draft Generation", () => {
  it("should generate paper draft", async () => {
    const mockContext = { context: { transcript_content: "test" } };
    const mockIssueSet = {
      artifact_id: uuidv4(),
      issues: [{ issue_id: "ISSUE-001", paper_section_id: "section-4" }],
    };
    const mockMinutes = { agenda_items: ["test"] };

    const result = await generatePaperDraft(mockContext, mockIssueSet, mockMinutes);
    expect(result.success).toBe(true);
    expect(result.paper_draft_artifact?.artifact_kind).toBe("paper_draft_artifact");
  });
});
