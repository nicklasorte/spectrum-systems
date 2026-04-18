import { extractMeetingMinutes } from "@/src/mvp-4/minutes-extraction-agent";
import { assembleContextBundle } from "@/src/mvp-2/context-bundle-assembler";
import { ingestTranscript } from "@/src/mvp-1/transcript-ingestor";

describe("MVP-4: Meeting Minutes Extraction", () => {
  let contextBundlePayload: any;

  beforeAll(async () => {
    const ingestResult = await ingestTranscript({
      raw_text: `Alice: Good morning. Let's discuss the new product launch.
Bob: I think Q2 release. Carol: Agreed. Alice: Bob, lead the product team?
Bob: Yes. Carol: Marketing by March 31st.`,
      source_file: "product-launch.txt",
    });
    if (ingestResult.success && ingestResult.transcript_artifact) {
      const assembleResult = await assembleContextBundle(ingestResult.transcript_artifact.artifact_id);
      if (assembleResult.success && assembleResult.context_bundle) {
        contextBundlePayload = assembleResult.context_bundle;
      }
    }
  });

  it("should extract minutes successfully", async () => {
    const result = await extractMeetingMinutes(contextBundlePayload);
    expect(result.success).toBe(true);
    expect(result.meeting_minutes_artifact?.artifact_kind).toBe("meeting_minutes_artifact");
  });

  it("should extract agenda items", async () => {
    const result = await extractMeetingMinutes(contextBundlePayload);
    expect(result.success).toBe(true);
    expect(Array.isArray(result.meeting_minutes_artifact?.agenda_items)).toBe(true);
  });

  it("should extract decisions", async () => {
    const result = await extractMeetingMinutes(contextBundlePayload);
    expect(result.success).toBe(true);
    expect(Array.isArray(result.meeting_minutes_artifact?.decisions)).toBe(true);
  });

  it("should extract action items", async () => {
    const result = await extractMeetingMinutes(contextBundlePayload);
    expect(result.success).toBe(true);
    expect(Array.isArray(result.meeting_minutes_artifact?.action_items)).toBe(true);
  });

  it("should extract attendees", async () => {
    const result = await extractMeetingMinutes(contextBundlePayload);
    expect(result.success).toBe(true);
    expect(Array.isArray(result.meeting_minutes_artifact?.attendees)).toBe(true);
  });

  it("should emit execution record", async () => {
    const result = await extractMeetingMinutes(contextBundlePayload);
    expect(result.execution_record?.artifact_kind).toBe("pqx_execution_record");
    expect(result.execution_record?.execution_status).toBe("succeeded");
  });
});
