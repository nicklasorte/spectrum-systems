import { assembleContextBundle } from "../../src/mvp-2/context-bundle-assembler";
import { ingestTranscript } from "../../src/mvp-1/transcript-ingestor";

describe("MVP-2: Context Bundle Assembly", () => {
  let transcriptArtifact: any;

  beforeAll(async () => {
    const ingestResult = await ingestTranscript({
      raw_text: `Alice: Good morning everyone, thanks for joining.
Bob: Hi Alice, great to be here.
Carol: Looking forward to this discussion.
Alice: Let's start with the main topics.
Bob: I have three items to cover today.
Alice: Perfect, please go ahead.`,
      source_file: "test-meeting.txt",
      duration_minutes: 30,
      language: "en",
    });

    if (ingestResult.success && ingestResult.transcript_artifact) {
      transcriptArtifact = ingestResult.transcript_artifact;
    }
  });

  it("should assemble context bundle successfully", async () => {
    const result = await assembleContextBundle(transcriptArtifact);

    expect(result.success).toBe(true);
    expect(result.context_bundle).toBeDefined();
    expect(result.context_bundle?.artifact_kind).toBe("context_bundle");
    expect(result.context_bundle?.artifact_id).toBeDefined();
    expect(result.context_bundle?.assembly_manifest).toBeDefined();
  });

  it("should fail on missing transcript artifact", async () => {
    const result = await assembleContextBundle(null);

    expect(result.success).toBe(false);
    expect(result.error_codes).toContain("missing_artifact");
    expect(result.error).toBeDefined();
  });

  it("should produce reproducible manifest hash", async () => {
    const result1 = await assembleContextBundle(transcriptArtifact);
    const result2 = await assembleContextBundle(transcriptArtifact);

    expect(result1.success).toBe(true);
    expect(result2.success).toBe(true);

    expect(result1.context_bundle?.assembly_manifest.manifest_hash).toBe(
      result2.context_bundle?.assembly_manifest.manifest_hash
    );
  });

  it("should produce reproducible content hash", async () => {
    const result1 = await assembleContextBundle(transcriptArtifact);
    const result2 = await assembleContextBundle(transcriptArtifact);

    expect(result1.context_bundle?.content_hash).toBe(
      result2.context_bundle?.content_hash
    );
  });

  it("should preserve speaker data from transcript", async () => {
    const result = await assembleContextBundle(transcriptArtifact);

    expect(result.success).toBe(true);
    expect(result.context_bundle?.context.speakers).toBeDefined();
    expect(result.context_bundle?.context.speakers?.length).toBeGreaterThan(0);
    expect(result.context_bundle?.context.speakers).toContain("Alice");
    expect(result.context_bundle?.context.speakers).toContain("Bob");
  });

  it("should preserve transcript content", async () => {
    const result = await assembleContextBundle(transcriptArtifact);

    expect(result.success).toBe(true);
    expect(result.context_bundle?.context.transcript_content).toBeDefined();
    expect(
      result.context_bundle?.context.transcript_content?.length
    ).toBeGreaterThan(0);
  });

  it("should include default task description and instructions", async () => {
    const result = await assembleContextBundle(transcriptArtifact);

    expect(result.success).toBe(true);
    expect(result.context_bundle?.context.task_description).toBeDefined();
    expect(result.context_bundle?.context.instructions).toBeDefined();
  });

  it("should accept custom task description and instructions", async () => {
    const customTask = "Custom task for this meeting";
    const customInstructions = "Follow these specific instructions";

    const result = await assembleContextBundle(transcriptArtifact, {
      task_description: customTask,
      instructions: customInstructions,
    });

    expect(result.success).toBe(true);
    expect(result.context_bundle?.context.task_description).toBe(customTask);
    expect(result.context_bundle?.context.instructions).toBe(customInstructions);
  });

  it("should emit pqx execution record on success", async () => {
    const result = await assembleContextBundle(transcriptArtifact);

    expect(result.success).toBe(true);
    expect(result.execution_record).toBeDefined();
    expect(result.execution_record?.artifact_kind).toBe("pqx_execution_record");
    expect(result.execution_record?.execution_status).toBe("succeeded");
    expect(result.execution_record?.pqx_step.name).toBe(
      "MVP-2: Context Bundle Assembly"
    );
    expect(result.execution_record?.inputs.artifact_ids).toContain(
      transcriptArtifact.artifact_id
    );
    expect(result.execution_record?.outputs.artifact_ids).toBeDefined();
  });

  it("should link execution record to context bundle", async () => {
    const result = await assembleContextBundle(transcriptArtifact);

    expect(result.success).toBe(true);
    expect(result.execution_record?.outputs.artifact_ids).toContain(
      result.context_bundle?.artifact_id
    );
  });

  it("should include trace context for distributed tracing", async () => {
    const result = await assembleContextBundle(transcriptArtifact);

    expect(result.success).toBe(true);
    expect(result.context_bundle?.trace.trace_id).toBeDefined();
    expect(result.context_bundle?.trace.created_at).toBeDefined();
    expect(result.execution_record?.trace.trace_id).toBe(
      result.context_bundle?.trace.trace_id
    );
  });

  it("should emit execution record on failure", async () => {
    const result = await assembleContextBundle(null);

    expect(result.success).toBe(false);
    expect(result.execution_record).toBeDefined();
    expect(result.execution_record?.execution_status).toBe("failed");
    expect(result.execution_record?.failure).toBeDefined();
    expect(result.execution_record?.failure?.reason_codes).toContain(
      "missing_artifact"
    );
  });

  it("should reject artifact missing artifact_id", async () => {
    const result = await assembleContextBundle({ artifact_kind: "transcript_artifact" });

    expect(result.success).toBe(false);
    expect(result.error_codes).toContain("missing_artifact");
  });

  it("should include input artifact reference in context bundle", async () => {
    const result = await assembleContextBundle(transcriptArtifact);

    expect(result.success).toBe(true);
    expect(result.context_bundle?.input_artifacts).toContain(
      transcriptArtifact.artifact_id
    );
    expect(result.context_bundle?.context.transcript_id).toBe(
      transcriptArtifact.artifact_id
    );
  });
});
