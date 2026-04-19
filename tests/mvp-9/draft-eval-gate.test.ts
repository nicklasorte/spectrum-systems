import { runDraftEvalGate } from "@/src/mvp-9/draft-eval-gate";

describe("MVP-9: Draft Quality Eval Gate", () => {
  it("should validate draft quality", async () => {
    const result = await runDraftEvalGate("draft-id", "issue-set-id", 
      {
        artifact_kind: "paper_draft_artifact",
        sections: {
          abstract: "test",
          introduction: "test",
          findings: "test",
          recommendations: "test",
          conclusion: "test",
        },
        content_hash: "sha256:test"
      },
      { artifact_id: "issue-set-id" }
    );
    expect(result.success).toBe(true);
    expect(result.eval_summary?.overall_status).toBe("pass");
  });
});
