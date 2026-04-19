import { emitHumanReviewRequest, submitReview } from "@/src/mvp-10/human-review-gate";

describe("MVP-10: Human Review Gate", () => {
  it("should emit human review request", async () => {
    const result = await emitHumanReviewRequest("draft-id", { artifact_id: "summary-id" });
    expect(result.success).toBe(true);
  });

  it("should accept valid review submission", async () => {
    const result = await submitReview("reviewer-123", "draft-id", "revise", [
      { section: "findings", comment: "Needs detail", severity: "S2" },
    ]);
    expect(result.success).toBe(true);
    expect(result.review_artifact?.decision).toBe("revise");
  });
});
