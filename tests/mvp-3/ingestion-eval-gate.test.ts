import { runIngestionEvalGate } from "../../src/mvp-3/ingestion-eval-gate";
import { ingestTranscript } from "../../src/mvp-1/transcript-ingestor";
import { assembleContextBundle } from "../../src/mvp-2/context-bundle-assembler";

describe("MVP-3: Transcript Eval Baseline", () => {
  let transcriptArtifact: any;
  let contextBundleArtifact: any;

  beforeAll(async () => {
    const ingestResult = await ingestTranscript({
      raw_text: `Alice: Good morning.\nBob: Hi Alice.\nCarol: Ready.\nAlice: Let's begin.`,
      source_file: "test.txt",
      duration_minutes: 30,
    });
    if (ingestResult.success && ingestResult.transcript_artifact) {
      transcriptArtifact = ingestResult.transcript_artifact;
      const assembleResult = await assembleContextBundle(ingestResult.transcript_artifact);
      if (assembleResult.success && assembleResult.context_bundle) {
        contextBundleArtifact = assembleResult.context_bundle;
      }
    }
  });

  it("should run all 3 eval cases", async () => {
    const result = await runIngestionEvalGate(transcriptArtifact, contextBundleArtifact);
    expect(result.success).toBe(true);
    expect(result.eval_results?.length).toBe(3);
  });

  it("should pass all evals for valid artifacts", async () => {
    const result = await runIngestionEvalGate(transcriptArtifact, contextBundleArtifact);
    expect(result.eval_summary?.overall_status).toBe("pass");
    expect(result.eval_summary?.pass_rate).toBe(100);
  });

  it("should emit allow control decision for valid artifacts", async () => {
    const result = await runIngestionEvalGate(transcriptArtifact, contextBundleArtifact);
    expect(result.control_decision?.artifact_type).toBe("evaluation_control_decision");
    expect(result.control_decision?.decision).toBe("allow");
    expect(result.control_decision?.system_status).toBe("healthy");
  });

  it("should emit eval_result artifacts with correct schema fields", async () => {
    const result = await runIngestionEvalGate(transcriptArtifact, contextBundleArtifact);
    expect(result.success).toBe(true);
    const first = result.eval_results![0];
    expect(first.artifact_type).toBe("eval_result");
    expect(first.schema_version).toBe("1.0.0");
    expect(["pass", "fail", "indeterminate"]).toContain(first.result_status);
    expect(first.score).toBeGreaterThanOrEqual(0);
    expect(first.score).toBeLessThanOrEqual(1);
  });

  it("should emit execution record", async () => {
    const result = await runIngestionEvalGate(transcriptArtifact, contextBundleArtifact);
    expect(result.execution_record?.artifact_kind).toBe("pqx_execution_record");
    expect(result.execution_record?.execution_status).toBe("succeeded");
  });

  it("should fail on missing artifacts", async () => {
    const result = await runIngestionEvalGate("nonexistent", "nonexistent");
    expect(result.success).toBe(false);
    expect(result.control_decision?.decision).toBe("deny");
    expect(result.control_decision?.system_status).toBe("blocked");
  });
});
