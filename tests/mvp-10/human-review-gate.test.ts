import { emitHumanReviewRequest, submitReview } from "../../src/mvp-10/human-review-gate";

describe("MVP-10: Human Review Gate", () => {
  it("should emit human review request", async () => {
    const result = await emitHumanReviewRequest("draft-id", { artifact_id: "summary-id" });
    expect(result.success).toBe(true);
    expect(result.execution_record?.action_type).toBe("require_human_review");
    expect(result.execution_record?.status).toBe("pending");
    expect(result.execution_record?.draft_artifact_id).toBe("draft-id");
  });

  it("should accept valid review submission", async () => {
    const result = await submitReview("reviewer-123", "draft-id", "revise", [
      { section: "findings", comment: "Needs detail", severity: "S2" },
    ]);
    expect(result.success).toBe(true);
    expect(result.review_artifact?.decision).toBe("revise");
    expect(result.review_artifact?.artifact_type).toBe("review_artifact");
    expect(result.review_artifact?.schema_version).toBe("1.0.0");
  });

  it("should fail-closed on empty reviewer identity", async () => {
    const result = await submitReview("", "draft-id", "revise", [
      { section: "findings", comment: "Needs detail", severity: "S2" },
    ]);
    expect(result.success).toBe(false);
    expect(result.error_codes).toContain("missing_reviewer_identity");
  });

  it("should fail-closed on short reviewer identity", async () => {
    const result = await submitReview("ab", "draft-id", "revise", [
      { section: "findings", comment: "Needs detail", severity: "S2" },
    ]);
    expect(result.success).toBe(false);
    expect(result.error_codes).toContain("missing_reviewer_identity");
  });

  it("should fail-closed on invalid severity", async () => {
    const result = await submitReview("reviewer-123", "draft-id", "revise", [
      { section: "findings", comment: "Needs detail", severity: "S5" as any },
    ]);
    expect(result.success).toBe(false);
    expect(result.error_codes).toContain("invalid_severity");
  });
});
