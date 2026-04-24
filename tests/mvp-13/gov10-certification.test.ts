import { runGOV10Certification } from "../../src/mvp-13/gov10-certification";

describe("MVP-13: GOV-10 Certification", () => {
  it("should pass certification with valid artifacts including human review", async () => {
    const mockEvals = [
      { artifact_id: "eval-1", overall_status: "pass" },
      { artifact_id: "eval-2", overall_status: "pass" },
    ];
    const mockRecords = [
      {
        artifact_id: "rec-1",
        artifact_type: "pqx_execution_record",
        execution_status: "succeeded",
        created_at: new Date().toISOString(),
      },
      {
        artifact_id: "rec-2",
        artifact_type: "pqx_execution_record",
        execution_status: "succeeded",
        created_at: new Date().toISOString(),
      },
      {
        artifact_id: "enf-1",
        artifact_type: "enforcement_action",
        action_type: "require_human_review",
        execution_status: "succeeded",
        created_at: new Date().toISOString(),
      },
    ];

    const result = await runGOV10Certification("paper-id", mockEvals, mockRecords);
    expect(result.done_certification_record?.artifact_type).toBe(
      "done_certification_record"
    );
    expect(result.done_certification_record?.status).toBe("PASSED");
    expect(result.release_artifact).toBeDefined();
    expect(result.release_artifact?.artifact_type).toBe("release_artifact");
  });

  it("should emit release_artifact on PASSED", async () => {
    const mockEvals = [
      { artifact_id: "eval-1" },
      { artifact_id: "eval-2" },
    ];
    const mockRecords = [
      {
        artifact_id: "rec-1",
        artifact_type: "pqx_execution_record",
        execution_status: "succeeded",
        created_at: new Date().toISOString(),
      },
      {
        artifact_id: "rec-2",
        artifact_type: "pqx_execution_record",
        execution_status: "succeeded",
        created_at: new Date().toISOString(),
      },
      {
        artifact_id: "enf-1",
        artifact_type: "enforcement_action",
        action_type: "require_human_review",
        execution_status: "succeeded",
        created_at: new Date().toISOString(),
      },
    ];

    const result = await runGOV10Certification("paper-id", mockEvals, mockRecords);
    expect(result.release_artifact?.status).toBe("RELEASED");
  });

  it("should FAIL when human_review_present check fails", async () => {
    const mockEvals = [
      { artifact_id: "eval-1" },
      { artifact_id: "eval-2" },
    ];
    const mockRecords = [
      {
        artifact_id: "rec-1",
        artifact_type: "pqx_execution_record",
        execution_status: "succeeded",
        created_at: new Date().toISOString(),
      },
      {
        artifact_id: "rec-2",
        artifact_type: "pqx_execution_record",
        execution_status: "succeeded",
        created_at: new Date().toISOString(),
      },
      {
        artifact_id: "rec-3",
        artifact_type: "pqx_execution_record",
        execution_status: "succeeded",
        created_at: new Date().toISOString(),
      },
    ];

    const result = await runGOV10Certification("paper-id", mockEvals, mockRecords);
    expect(result.done_certification_record?.status).toBe("FAILED");
    expect(result.done_certification_record?.failures).toContain("human_review_present");
    expect(result.release_artifact).toBeUndefined();
  });
});
