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
    expect(result.transcript_artifact!.artifact_type).toBe("transcript_artifact");
    expect(result.transcript_artifact!.schema_version).toBe("1.0.0");
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

  it("should produce schema-conformant metadata", async () => {
    const result = await ingestTranscript({
      raw_text: FIXTURE_VALID_TRANSCRIPT,
      source_file: "test.txt",
    });

    expect(result.success).toBe(true);
    const metadata = result.transcript_artifact!.outputs.metadata;
    expect(metadata.segment_count).toBeGreaterThanOrEqual(5);
    expect(metadata.has_timestamps).toBe(true);
    expect(metadata.meeting_id).toBe("test");
  });

  it("should produce schema-conformant segments", async () => {
    const result = await ingestTranscript({
      raw_text: FIXTURE_VALID_TRANSCRIPT,
      source_file: "test.txt",
    });

    expect(result.success).toBe(true);
    const segments = result.transcript_artifact!.outputs.segments;
    expect(segments.length).toBeGreaterThanOrEqual(1);
    expect(segments[0].speaker).toBeDefined();
    expect(segments[0].speaker.length).toBeGreaterThan(0);
    expect(segments[0].agency).toBeDefined();
    expect(segments[0].segment_id).toBeDefined();
  });

  it("should compute content hash", async () => {
    const result = await ingestTranscript({
      raw_text: FIXTURE_VALID_TRANSCRIPT,
      source_file: "test.txt",
    });

    expect(result.success).toBe(true);
    expect(result.transcript_artifact!.outputs.provenance.content_hash).toMatch(
      /^sha256:[a-f0-9]{64}$/
    );
  });

  it("should emit execution record with trace linkage", async () => {
    const result = await ingestTranscript({
      raw_text: FIXTURE_VALID_TRANSCRIPT,
      source_file: "test.txt",
    });

    const execRecord = result.execution_record;
    expect(execRecord.trace_id).toBeDefined();
    expect(execRecord.pqx_step.name).toBe("MVP-1: Transcript Ingestion & Normalization");
    expect(execRecord.outputs.artifact_ids).toContain(
      result.transcript_artifact!.outputs.artifact_id
    );
  });

  it("should produce deterministic content hash for same input", async () => {
    const result1 = await ingestTranscript({
      raw_text: FIXTURE_VALID_TRANSCRIPT,
      source_file: "test.txt",
    });
    const result2 = await ingestTranscript({
      raw_text: FIXTURE_VALID_TRANSCRIPT,
      source_file: "test.txt",
    });

    expect(result1.success).toBe(true);
    expect(result2.success).toBe(true);
    expect(result1.transcript_artifact!.outputs.provenance.content_hash).toBe(
      result2.transcript_artifact!.outputs.provenance.content_hash
    );
  });
});
