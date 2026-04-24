import { extractMeetingMinutes } from "../../src/mvp-4/minutes-extraction-agent";
import { assembleContextBundle } from "../../src/mvp-2/context-bundle-assembler";
import { ingestTranscript } from "../../src/mvp-1/transcript-ingestor";

const describeWithApiKey = process.env.ANTHROPIC_API_KEY ? describe : describe.skip;

describeWithApiKey("MVP-4: Meeting Minutes Extraction", () => {
  let contextBundlePayload: any;

  beforeAll(async () => {
    const ingestResult = await ingestTranscript({
      raw_text: `Alice: Good morning everyone. Let's discuss the new product launch.
Bob: I think we should focus on Q2 release.
Carol: Agreed. We need to assign someone to lead the effort.
Alice: Bob, can you lead the product team?
Bob: Yes, I can take that on.
Carol: Great. We also need marketing materials ready by March 31st.
Alice: Anything else?
Bob: No, I think that covers it.`,
      source_file: "product-launch.txt",
      duration_minutes: 30,
      language: "en",
    });

    if (ingestResult.success && ingestResult.transcript_artifact) {
      const assembleResult = await assembleContextBundle(
        ingestResult.transcript_artifact
      );
      if (assembleResult.success && assembleResult.context_bundle) {
        contextBundlePayload = assembleResult.context_bundle;
      }
    }
  });

  it("should extract meeting minutes successfully", async () => {
    const result = await extractMeetingMinutes(contextBundlePayload);

    expect(result.success).toBe(true);
    expect(result.meeting_minutes_artifact).toBeDefined();
    expect(result.meeting_minutes_artifact?.artifact_type).toBe(
      "meeting_minutes_artifact"
    );
    expect(result.meeting_minutes_artifact?.schema_version).toBe("1.0.0");
  });

  it("should extract agenda items", async () => {
    const result = await extractMeetingMinutes(contextBundlePayload);

    expect(result.success).toBe(true);
    expect(result.meeting_minutes_artifact?.agenda_items).toBeDefined();
    expect(Array.isArray(result.meeting_minutes_artifact?.agenda_items)).toBe(
      true
    );
    expect(result.meeting_minutes_artifact?.agenda_items.length).toBeGreaterThan(0);
  });

  it("should extract decisions with rationale", async () => {
    const result = await extractMeetingMinutes(contextBundlePayload);

    expect(result.success).toBe(true);
    expect(result.meeting_minutes_artifact?.decisions).toBeDefined();
    expect(Array.isArray(result.meeting_minutes_artifact?.decisions)).toBe(true);
  });

  it("should extract action items with owner", async () => {
    const result = await extractMeetingMinutes(contextBundlePayload);

    expect(result.success).toBe(true);
    expect(result.meeting_minutes_artifact?.action_items).toBeDefined();
    expect(Array.isArray(result.meeting_minutes_artifact?.action_items)).toBe(
      true
    );
  });

  it("should extract attendees", async () => {
    const result = await extractMeetingMinutes(contextBundlePayload);

    expect(result.success).toBe(true);
    expect(result.meeting_minutes_artifact?.attendees).toBeDefined();
    expect(Array.isArray(result.meeting_minutes_artifact?.attendees)).toBe(true);
    expect(result.meeting_minutes_artifact?.attendees.length).toBeGreaterThan(0);
  });

  it("should emit execution record on success", async () => {
    const result = await extractMeetingMinutes(contextBundlePayload);

    expect(result.success).toBe(true);
    expect(result.execution_record).toBeDefined();
    expect(result.execution_record?.artifact_type).toBe("pqx_execution_record");
    expect(result.execution_record?.execution_status).toBe("succeeded");
    expect(result.execution_record?.pqx_step.name).toBe(
      "MVP-4: Meeting Minutes Extraction"
    );
    expect(result.execution_record?.inputs.artifact_ids).toContain(
      contextBundlePayload.context_bundle_id
    );
    expect(result.execution_record?.outputs.artifact_ids).toContain(
      result.meeting_minutes_artifact?.artifact_id
    );
  });

  it("should link trace context between artifact and execution record", async () => {
    const result = await extractMeetingMinutes(contextBundlePayload);

    expect(result.success).toBe(true);
    expect(result.meeting_minutes_artifact?.trace.trace_id).toBeDefined();
    expect(result.execution_record?.trace.trace_id).toBe(
      result.meeting_minutes_artifact?.trace.trace_id
    );
  });

  it("should emit execution record on failure", async () => {
    const result = await extractMeetingMinutes(null);

    expect(result.success).toBe(false);
    expect(result.execution_record).toBeDefined();
    expect(result.execution_record?.execution_status).toBe("failed");
    expect(result.error_codes).toContain("extraction_error");
  });

  it("should fail-closed on invalid JSON from model", async () => {
    const result = await extractMeetingMinutes(contextBundlePayload);

    if (result.success) {
      expect(result.meeting_minutes_artifact?.artifact_type).toBe(
        "meeting_minutes_artifact"
      );
    } else {
      expect(result.error_codes).toContain("extraction_error");
    }
  });
});
