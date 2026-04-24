import { ingestTranscript } from "../../src/mvp-1/transcript-ingestor";
import { assembleContextBundle } from "../../src/mvp-2/context-bundle-assembler";
import { runIngestionEvalGate } from "../../src/mvp-3/ingestion-eval-gate";

const describeWithApiKey = process.env.ANTHROPIC_API_KEY ? describe : describe.skip;

describeWithApiKey("E2E: Real Transcript Pipeline (requires API key)", () => {
  const REAL_TRANSCRIPT = `[09:00:12] Alice: Good morning everyone. Today we're reviewing spectrum interference findings from Site 7.
[09:00:45] Bob: Thanks Alice. We've confirmed three interference sources in the 5.8GHz band affecting our primary uplink.
[09:01:15] Carol: I've documented two of those already. The third requires additional field measurements.
[09:02:00] Alice: Bob, can you schedule the additional field measurements by end of week?
[09:02:20] Bob: Yes, I'll coordinate with the field team and report back by Thursday.
[09:03:00] Carol: I'll take the action item to update the spectrum management plan once we have the measurements.
[09:03:30] Alice: Perfect. Let's reconvene Thursday afternoon to review findings and finalize the study draft.`;

  it("MVP-1: should ingest real-style transcript with timestamps", async () => {
    const start = Date.now();
    const result = await ingestTranscript({
      raw_text: REAL_TRANSCRIPT,
      source_file: "site-7-review.txt",
      duration_minutes: 5,
    });
    const elapsed = Date.now() - start;

    expect(result.success).toBe(true);
    expect(result.transcript_artifact?.artifact_type).toBe("transcript_artifact");
    expect(result.transcript_artifact?.outputs?.metadata?.has_timestamps).toBe(true);
    expect(result.transcript_artifact?.outputs?.metadata?.segment_count).toBeGreaterThanOrEqual(6);
    expect(result.transcript_artifact?.outputs?.provenance?.content_hash).toMatch(/^sha256:/);
    console.log(`MVP-1 latency: ${elapsed}ms, segments: ${result.transcript_artifact?.outputs?.metadata?.segment_count}`);
  });

  it("MVP-2: should assemble context bundle from real transcript", async () => {
    const ingestResult = await ingestTranscript({
      raw_text: REAL_TRANSCRIPT,
      source_file: "site-7-review.txt",
    });
    expect(ingestResult.success).toBe(true);
    const transcriptArtifact = ingestResult.transcript_artifact!;

    const start = Date.now();
    const result = await assembleContextBundle(transcriptArtifact);
    const elapsed = Date.now() - start;

    expect(result.success).toBe(true);
    expect(result.context_bundle?.artifact_type).toBe("context_bundle");
    expect(result.context_bundle?.context_bundle_id).toMatch(/^ctx-[a-f0-9]{16}$/);
    expect(result.context_bundle?.metadata?.assembly_manifest_hash).toMatch(/^sha256:/);
    console.log(`MVP-2 latency: ${elapsed}ms`);
  });

  it("MVP-3: should pass ingestion eval gate on real transcript", async () => {
    const ingestResult = await ingestTranscript({ raw_text: REAL_TRANSCRIPT, source_file: "site-7-review.txt" });
    const transcriptArtifact = ingestResult.transcript_artifact!;
    const bundleResult = await assembleContextBundle(transcriptArtifact);

    const result = await runIngestionEvalGate(transcriptArtifact, bundleResult.context_bundle!);

    expect(result.success).toBe(true);
    expect(result.eval_results?.length).toBe(3);
    expect(result.control_decision?.decision).toBe("allow");
    expect(result.eval_summary?.overall_status).toBe("pass");
    console.log(`MVP-3: ${result.eval_results?.length} eval cases, decision: ${result.control_decision?.decision}`);
  });
});
