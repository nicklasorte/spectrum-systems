import { PipelineConnector } from "@/src/mvp-integration/pipeline-connector";
import { ControlLoopEngine } from "@/src/mvp-integration/control-loop-engine";

describe("E2E MVP Pipeline", () => {
  let connector: PipelineConnector;
  let controlLoop: ControlLoopEngine;

  beforeAll(async () => {
    // Initialize all components
  });

  it("should process transcript through MVP-1", async () => {
    const output = await connector.mvp1_transcript_ingestion("test_transcript.txt");
    expect(output.mvp_name).toBe("MVP-1");
    expect(output.sli_measurements.transcription_latency).toBeGreaterThan(0);
  });

  it("should evaluate transcript in MVP-3 and make gate decision", async () => {
    const transcript = { artifact_id: "test-123" };
    const output = await connector.mvp3_eval_gate(transcript);
    expect(["allow", "warn", "freeze", "block"]).toContain(output.decision_gate);
  });

  it("should certify and sign in MVP-13", async () => {
    const allArtifacts = [{ artifact_id: "a1" }, { artifact_id: "a2" }];
    const output = await connector.mvp13_certification(allArtifacts);
    expect(output.artifact.decision).toBeDefined();
    expect(output.artifact.signature).toBeDefined();
  });

  it("should respect control loop decisions", async () => {
    const decision = await controlLoop.decidePromotion("artifact-123", {
      eval_pass_rate: 95.0,
    });
    expect(typeof decision.allowed).toBe("boolean");
    expect(Array.isArray(decision.signals)).toBe(true);
  });
});
