import { runIngestionEvalGate } from "@/src/mvp-3/ingestion-eval-gate";
import { ingestTranscript } from "@/src/mvp-1/transcript-ingestor";
import { assembleContextBundle } from "@/src/mvp-2/context-bundle-assembler";

describe("MVP-3: Transcript Eval Baseline", () => {
  let transcriptArtifactId: string;
  let contextBundleArtifactId: string;

  beforeAll(async () => {
    const ingestResult = await ingestTranscript({
      raw_text: `Alice: Good morning.\nBob: Hi Alice.\nCarol: Ready.\nAlice: Let's begin.`,
      source_file: "test.txt",
      duration_minutes: 30,
    });
    if (ingestResult.success && ingestResult.transcript_artifact) {
      transcriptArtifactId = ingestResult.transcript_artifact.artifact_id;
      const assembleResult = await assembleContextBundle(transcriptArtifactId);
      if (assembleResult.success && assembleResult.context_bundle) {
        contextBundleArtifactId = assembleResult.context_bundle.artifact_id;
      }
    }
  });

  it("should run all 3 eval cases", async () => {
    const result = await runIngestionEvalGate(transcriptArtifactId, contextBundleArtifactId);
    expect(result.success).toBe(true);
    expect(result.eval_results?.length).toBe(3);
  });

  it("should pass all evals for valid artifacts", async () => {
    const result = await runIngestionEvalGate(transcriptArtifactId, contextBundleArtifactId);
    expect(result.eval_summary?.overall_status).toBe("pass");
    expect(result.eval_summary?.pass_rate).toBe(100);
  });

  it("should emit allow control decision", async () => {
    const result = await runIngestionEvalGate(transcriptArtifactId, contextBundleArtifactId);
    expect(result.control_decision?.decision).toBe("allow");
  });

  it("should emit execution record", async () => {
    const result = await runIngestionEvalGate(transcriptArtifactId, contextBundleArtifactId);
    expect(result.execution_record?.artifact_kind).toBe("pqx_execution_record");
    expect(result.execution_record?.execution_status).toBe("succeeded");
  });

  it("should fail on missing artifacts", async () => {
    const result = await runIngestionEvalGate("nonexistent", "nonexistent");
    expect(result.success).toBe(false);
  });
});
