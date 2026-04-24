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
    expect(result.context_bundle?.artifact_type).toBe("context_bundle");
    expect(result.context_bundle?.schema_version).toBe("2.3.0");
    expect(result.context_bundle?.context_bundle_id).toMatch(/^ctx-[a-f0-9]{16}$/);
    expect(result.context_bundle?.context_items.length).toBeGreaterThanOrEqual(1);
    expect(result.context_bundle?.metadata.assembly_manifest_hash).toMatch(/^sha256:/);
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

    expect(result1.context_bundle?.metadata.assembly_manifest_hash).toBe(
      result2.context_bundle?.metadata.assembly_manifest_hash
    );
  });

  it("should produce reproducible assembly manifest hash (replay determinism)", async () => {
    const result1 = await assembleContextBundle(transcriptArtifact);
    const result2 = await assembleContextBundle(transcriptArtifact);

    expect(result1.context_bundle?.metadata.assembly_manifest_hash).toBe(
      result2.context_bundle?.metadata.assembly_manifest_hash
    );
  });

  it("should preserve speaker data from transcript", async () => {
    const result = await assembleContextBundle(transcriptArtifact);

    expect(result.success).toBe(true);
    const content = result.context_bundle?.context_items[0].content as any[];
    expect(content).toBeDefined();
    expect(content.length).toBeGreaterThan(0);
    const speakers = Array.from(new Set(content.map((s: any) => s.speaker)));
    expect(speakers).toContain("Alice");
    expect(speakers).toContain("Bob");
  });

  it("should preserve transcript content", async () => {
    const result = await assembleContextBundle(transcriptArtifact);

    expect(result.success).toBe(true);
    expect(result.context_bundle?.context_items[0].content).toBeDefined();
    expect(result.context_bundle?.context_items[0].content.length).toBeGreaterThan(0);
  });

  it("should include default task type", async () => {
    const result = await assembleContextBundle(transcriptArtifact);

    expect(result.success).toBe(true);
    expect(result.context_bundle?.task_type).toBeDefined();
    expect(result.context_bundle?.task_type.length).toBeGreaterThan(0);
  });

  it("should accept custom task description", async () => {
    const customTask = "Custom task for this meeting";

    const result = await assembleContextBundle(transcriptArtifact, {
      task_description: customTask,
    });

    expect(result.success).toBe(true);
    expect(result.context_bundle?.task_type).toBe(customTask);
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
      transcriptArtifact.outputs.artifact_id
    );
    expect(result.execution_record?.outputs.artifact_ids).toBeDefined();
  });

  it("should link execution record to context bundle", async () => {
    const result = await assembleContextBundle(transcriptArtifact);

    expect(result.success).toBe(true);
    expect(result.execution_record?.outputs.artifact_ids).toContain(
      result.context_bundle?.context_bundle_id
    );
  });

  it("should include trace context for distributed tracing", async () => {
    const result = await assembleContextBundle(transcriptArtifact);

    expect(result.success).toBe(true);
    expect(result.context_bundle?.trace.trace_id).toBeDefined();
    expect(result.context_bundle?.trace.run_id).toBeDefined();
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
    const result = await assembleContextBundle({ artifact_type: "transcript_artifact" });

    expect(result.success).toBe(false);
    expect(result.error_codes).toContain("missing_artifact");
  });

  it("should include input artifact reference in context bundle", async () => {
    const result = await assembleContextBundle(transcriptArtifact);

    expect(result.success).toBe(true);
    expect(result.context_bundle?.metadata.input_artifact_ids).toContain(
      transcriptArtifact.outputs.artifact_id
    );
    expect(result.context_bundle?.context_items[0].provenance_ref).toBe(
      transcriptArtifact.outputs.artifact_id
    );
  });
});
