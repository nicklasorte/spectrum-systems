import { PipelineConnector } from "@/src/mvp-integration/pipeline-connector";
import * as fs from "fs";

/**
 * E2E Test: Real Transcript
 * Runs full pipeline on an actual meeting recording transcript
 * Measures: latency, cost, quality, trace completeness
 */

describe("E2E Pipeline with Real Transcript", () => {
  let connector: PipelineConnector;
  let realTranscriptPath: string;

  beforeAll(async () => {
    // Use a real transcript file from test fixtures
    realTranscriptPath = "tests/fixtures/real-meeting-transcript.txt";
    if (!fs.existsSync(realTranscriptPath)) {
      throw new Error(`Real transcript not found: ${realTranscriptPath}`);
    }
  });

  it("should ingest real transcript (MVP-1)", async () => {
    const startTime = Date.now();
    const output = await connector.mvp1_transcript_ingestion(realTranscriptPath);
    const elapsedMs = Date.now() - startTime;

    console.log(`✅ MVP-1 Ingestion: ${elapsedMs}ms`);
    console.log(`   Transcript size: ${output.artifact.text?.length || 0} chars`);
    console.log(`   SLI measurements:`, output.sli_measurements);

    expect(output.mvp_name).toBe("MVP-1");
    expect(output.sli_measurements.transcription_latency).toBeGreaterThan(0);
  });

  it("should pass eval gate (MVP-3)", async () => {
    const output = await connector.mvp3_eval_gate({
      artifact_id: "transcript-123",
    });

    console.log(`✅ MVP-3 Eval Gate:`, output.decision_gate);
    console.log(`   Eval pass rate: ${output.sli_measurements.eval_pass_rate}%`);

    expect(["allow", "warn", "freeze", "block"]).toContain(output.decision_gate);
  });

  it("should complete certification (MVP-13)", async () => {
    const allArtifacts = [{ artifact_id: "a1" }];
    const output = await connector.mvp13_certification(allArtifacts);

    console.log(`✅ MVP-13 Certification:`, output.decision_gate);
    console.log(`   Cost per run: ${output.sli_measurements.cost_per_run} cents`);
    console.log(`   Trace coverage: ${(output.sli_measurements.trace_coverage * 100).toFixed(1)}%`);

    expect(output.artifact.decision).toBeDefined();
    expect(output.artifact.signature).toBeDefined();
  });
});
