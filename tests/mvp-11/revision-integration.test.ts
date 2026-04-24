import { integrateRevisions } from "../../src/mvp-11/revision-integrator";

describe("MVP-11: Revision Integration", () => {
  it("should pass through unchanged on approve", async () => {
    const mockDraft = { artifact_id: "draft-id", sections: { abstract: "Original" } };
    const mockReview = { decision: "approve", findings: [] };

    const result = await integrateRevisions(mockDraft, mockReview);
    expect(result.success).toBe(true);
    expect(result.revised_draft_artifact?.artifact_type).toBe("revised_draft_artifact");
    expect(result.revised_draft_artifact?.schema_version).toBe("1.0.0");
    expect(result.revised_draft_artifact?.revision_diff.length).toBe(0);
    expect(result.revised_draft_artifact?.source_draft_id).toBe("draft-id");
    expect(result.revised_draft_artifact?.content_hash.startsWith("sha256:")).toBe(true);
  });

  it("should fail-closed on reject decision", async () => {
    const mockDraft = { artifact_id: "draft-id", sections: { abstract: "Original" } };
    const mockReview = { decision: "reject", findings: [] };

    const result = await integrateRevisions(mockDraft, mockReview);
    expect(result.success).toBe(false);
    expect(result.error_codes).toContain("draft_rejected");
    expect(result.execution_record?.execution_status).toBe("failed");
  });

  it("should produce sha256-prefixed content_hash on approve", async () => {
    const mockDraft = { artifact_id: "draft-id", sections: { abstract: "Original" } };
    const mockReview = { decision: "approve", findings: [] };

    const result = await integrateRevisions(mockDraft, mockReview);
    expect(result.success).toBe(true);
    expect(result.revised_draft_artifact?.content_hash.startsWith("sha256:")).toBe(true);
  });
});
