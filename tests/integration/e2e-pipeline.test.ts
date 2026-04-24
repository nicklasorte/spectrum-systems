import { ingestTranscript } from "../../src/mvp-1/transcript-ingestor";
import { assembleContextBundle } from "../../src/mvp-2/context-bundle-assembler";
import { runIngestionEvalGate } from "../../src/mvp-3/ingestion-eval-gate";
import { runGOV10Certification } from "../../src/mvp-13/gov10-certification";

describe("E2E MVP Pipeline Integration", () => {
  const RAW_TEXT = `Alice: Good morning, let's discuss the spectrum study findings.
Bob: We identified three key interference patterns in the 2.4GHz band.
Carol: I'll take the action item to document those findings.
Alice: Great. Bob, can you prepare the technical analysis by Friday?
Bob: Yes, confirmed.`;

  it("should chain MVP-1 → MVP-2 → MVP-3 successfully", async () => {
    const ingestResult = await ingestTranscript({
      raw_text: RAW_TEXT,
      source_file: "integration-test.txt",
    });
    expect(ingestResult.success).toBe(true);
    expect(ingestResult.transcript_artifact?.artifact_type).toBe("transcript_artifact");
    const transcriptArtifact = ingestResult.transcript_artifact!;

    const bundleResult = await assembleContextBundle(transcriptArtifact);
    expect(bundleResult.success).toBe(true);
    expect(bundleResult.context_bundle?.artifact_type).toBe("context_bundle");
    const contextBundle = bundleResult.context_bundle!;

    const evalResult = await runIngestionEvalGate(transcriptArtifact, contextBundle);
    expect(evalResult.success).toBe(true);
    expect(evalResult.control_decision?.decision).toBe("allow");
    expect(evalResult.control_decision?.artifact_type).toBe("evaluation_control_decision");
  });

  it("should GOV-10 certify a valid pipeline run", async () => {
    const mockEvals = [
      { artifact_id: "eval-1", overall_status: "pass" },
      { artifact_id: "eval-2", overall_status: "pass" },
    ];
    const mockRecords = [
      { artifact_id: "r1", artifact_type: "pqx_execution_record", execution_status: "succeeded", created_at: new Date().toISOString() },
      { artifact_id: "r2", artifact_type: "pqx_execution_record", execution_status: "succeeded", created_at: new Date().toISOString() },
      { artifact_id: "r3", artifact_type: "pqx_execution_record", execution_status: "succeeded", created_at: new Date().toISOString() },
      { artifact_id: "enf-1", artifact_type: "enforcement_action", action_type: "require_human_review", execution_status: "succeeded", created_at: new Date().toISOString() },
    ];

    const certResult = await runGOV10Certification("formatted-paper-id", mockEvals, mockRecords);
    expect(certResult.done_certification_record?.status).toBe("PASSED");
    expect(certResult.done_certification_record?.artifact_type).toBe("done_certification_record");
    expect(certResult.release_artifact?.artifact_type).toBe("release_artifact");
    expect(certResult.release_artifact?.status).toBe("RELEASED");
  });

  it("should fail GOV-10 when human review is absent", async () => {
    const mockEvals = [{ artifact_id: "eval-1" }, { artifact_id: "eval-2" }];
    const mockRecords = [
      { artifact_id: "r1", artifact_type: "pqx_execution_record", execution_status: "succeeded", created_at: new Date().toISOString() },
      { artifact_id: "r2", artifact_type: "pqx_execution_record", execution_status: "succeeded", created_at: new Date().toISOString() },
      { artifact_id: "r3", artifact_type: "pqx_execution_record", execution_status: "succeeded", created_at: new Date().toISOString() },
      // no enforcement_action with action_type: "require_human_review"
    ];

    const certResult = await runGOV10Certification("formatted-paper-id", mockEvals, mockRecords);
    expect(certResult.done_certification_record?.status).toBe("FAILED");
    expect(certResult.done_certification_record?.checks?.human_review_present).toBe(false);
  });
});
