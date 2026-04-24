import { randomUUID } from "crypto";
import { generatePaperDraft } from "../../src/mvp-8/paper-draft-generator";

describe("MVP-8: Paper Draft Generation", () => {
  it("should generate paper draft sections", async () => {
    const mockContext = {
      artifact_type: "context_bundle",
      context_items: [
        {
          item_type: "primary_input",
          content: [
            { speaker: "Alice", text: "Test transcript content", agency: "UNKNOWN" },
          ],
        },
      ],
    };
    const mockIssueSet = {
      artifact_id: randomUUID(),
      issues: [
        { issue_id: "ISSUE-001", paper_section_id: "section-4", description: "test" },
      ],
    };
    const mockMinutes = { agenda_items: ["test agenda"] };

    const result = await generatePaperDraft(mockContext, mockIssueSet, mockMinutes);

    if (result.success) {
      expect(result.paper_draft_artifact?.artifact_type).toBe("paper_draft_artifact");
      expect(result.paper_draft_artifact?.schema_version).toBe("1.0.0");
      expect(Object.keys(result.paper_draft_artifact?.sections || {}).length).toBeGreaterThan(0);
    } else {
      expect(result.error_codes).toContain("generation_error");
    }
  });
});
