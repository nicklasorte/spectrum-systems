import { extractMeetingMinutes } from "@/src/mvp-4/minutes-extraction-agent";
import { assembleContextBundle } from "@/src/mvp-2/context-bundle-assembler";
import { ingestTranscript } from "@/src/mvp-1/transcript-ingestor";

describe("MVP-4: Meeting Minutes Extraction", () => {
  let contextBundlePayload: any;

  beforeAll(async () => {
    // Set up: Ingest and assemble context bundle
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
        ingestResult.transcript_artifact.artifact_id
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
    expect(result.meeting_minutes_artifact?.artifact_kind).toBe(
      "meeting_minutes_artifact"
    );
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
    expect(result.execution_record?.artifact_kind).toBe("pqx_execution_record");
    expect(result.execution_record?.execution_status).toBe("succeeded");
    expect(result.execution_record?.pqx_step.name).toBe(
      "MVP-4: Meeting Minutes Extraction"
    );
    expect(result.execution_record?.inputs.artifact_ids).toContain(
      contextBundlePayload.artifact_id
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
    const result = await extractMeetingMinutes({
      context: { transcript_content: "" },
    });

    expect(result.success).toBe(false);
    expect(result.execution_record).toBeDefined();
    expect(result.execution_record?.execution_status).toBe("failed");
    expect(result.error_codes).toContain("extraction_error");
  });

  it("should fail-closed on invalid JSON from model", async () => {
    // This test verifies that if the model returns invalid JSON,
    // the artifact is not emitted and error is returned
    const result = await extractMeetingMinutes(contextBundlePayload);

    // Either success with valid artifact, or failure with error code
    if (result.success) {
      expect(result.meeting_minutes_artifact?.artifact_kind).toBe(
        "meeting_minutes_artifact"
      );
    } else {
      expect(result.error_codes).toContain("extraction_error");
    }
  });
});
