import { ingestTranscript } from "../../src/mvp-1/transcript-ingestor";
import {
  FIXTURE_VALID_TRANSCRIPT,
  FIXTURE_EMPTY_TRANSCRIPT,
  FIXTURE_MALFORMED_TRANSCRIPT,
} from "../../src/mvp-1/test-fixtures";

describe("Transcript Ingestor (MVP-1)", () => {
  it("should ingest valid transcript successfully", async () => {
    const result = await ingestTranscript({
      raw_text: FIXTURE_VALID_TRANSCRIPT,
      source_file: "meeting.txt",
      duration_minutes: 30,
      language: "en",
    });

    expect(result.success).toBe(true);
    expect(result.transcript_artifact).toBeDefined();
    expect(result.transcript_artifact.artifact_kind).toBe("transcript_artifact");
    expect(result.transcript_artifact.metadata.speaker_labels).toContain("Alice");
    expect(result.execution_record.execution_status).toBe("succeeded");
  });

  it("should fail-closed on empty transcript", async () => {
    const result = await ingestTranscript({
      raw_text: FIXTURE_EMPTY_TRANSCRIPT,
      source_file: "empty.txt",
    });

    expect(result.success).toBe(false);
    expect(result.error_codes).toContain("transcript_validation_failed");
    expect(result.execution_record.execution_status).toBe("failed");
  });

  it("should handle malformed transcript gracefully", async () => {
    const result = await ingestTranscript({
      raw_text: FIXTURE_MALFORMED_TRANSCRIPT,
      source_file: "malformed.txt",
    });

    expect(result.success).toBe(false);
    expect(result.execution_record.execution_status).toBe("failed");
  });

  it("should extract correct speaker count", async () => {
    const result = await ingestTranscript({
      raw_text: FIXTURE_VALID_TRANSCRIPT,
      source_file: "test.txt",
    });

    expect(result.success).toBe(true);
    expect(result.transcript_artifact.metadata.speaker_labels).toHaveLength(3); // Alice, Bob, Carol
  });

  it("should compute content hash", async () => {
    const result = await ingestTranscript({
      raw_text: FIXTURE_VALID_TRANSCRIPT,
      source_file: "test.txt",
    });

    expect(result.success).toBe(true);
    expect(result.transcript_artifact.content_hash).toMatch(/^sha256:[a-f0-9]{64}$/);
  });

  it("should set correct metadata", async () => {
    const result = await ingestTranscript({
      raw_text: FIXTURE_VALID_TRANSCRIPT,
      source_file: "meeting.txt",
      duration_minutes: 45,
      language: "en",
    });

    expect(result.success).toBe(true);
    const metadata = result.transcript_artifact.metadata;
    expect(metadata.source_file).toBe("meeting.txt");
    expect(metadata.duration_minutes).toBe(45);
    expect(metadata.language).toBe("en");
    expect(metadata.turn_count).toBeGreaterThan(0);
  });

  it("should emit execution record with trace linkage", async () => {
    const result = await ingestTranscript({
      raw_text: FIXTURE_VALID_TRANSCRIPT,
      source_file: "test.txt",
    });

    const execRecord = result.execution_record;
    expect(execRecord.trace.trace_id).toBeDefined();
    expect(execRecord.pqx_step.name).toBe("MVP-1: Transcript Ingestion & Normalization");
    expect(execRecord.outputs.artifact_ids).toContain(result.transcript_artifact.artifact_id);
  });
});
