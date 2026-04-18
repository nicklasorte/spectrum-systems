import { runGOV10Certification } from "@/src/mvp-13/gov10-certification";

describe("MVP-13: GOV-10 Certification", () => {
  it("should pass certification with valid artifacts", async () => {
    const mockEvals = [
      { artifact_id: "eval-1", overall_status: "pass" },
      { artifact_id: "eval-2", decision: "allow" },
    ];
    const mockRecords = [
      { artifact_id: "rec-1", artifact_kind: "pqx_execution_record", schema_ref: "ref", execution_status: "succeeded" },
    ];

    const result = await runGOV10Certification("paper-id", mockEvals, mockRecords);
    expect(result.done_certification_record?.status).toBe("PASSED");
    expect(result.release_artifact).toBeDefined();
  });

  it("should fail certification on broken lineage", async () => {
    const mockEvals = [];
    const mockRecords = [];

    const result = await runGOV10Certification("paper-id", mockEvals, mockRecords);
    expect(result.done_certification_record?.status).toBe("FAILED");
  });
});
