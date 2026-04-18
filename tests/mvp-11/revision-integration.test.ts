import { integrateRevisions } from "@/src/mvp-11/revision-integrator";

describe("MVP-11: Revision Integration", () => {
  it("should pass through unchanged on approve", async () => {
    const mockDraft = {
      artifact_id: "draft-id",
      sections: { abstract: "Original abstract" },
    };
    const mockReview = {
      decision: "approve",
      findings: [],
    };

    const result = await integrateRevisions(mockDraft, mockReview);
    expect(result.success).toBe(true);
    expect(result.revised_draft_artifact?.revision_diff.length).toBe(0);
  });

  it("should apply revisions on revise decision", async () => {
    const mockDraft = {
      artifact_id: "draft-id",
      sections: { findings: "Original findings" },
    };
    const mockReview = {
      decision: "revise",
      findings: [
        {
          section: "findings",
          comment: "Add more detail",
          severity: "S2",
        },
      ],
    };

    const result = await integrateRevisions(mockDraft, mockReview);
    expect(result.success).toBe(true);
  });
});
