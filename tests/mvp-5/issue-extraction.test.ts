import { extractIssues } from "../../src/mvp-5/issue-extraction-agent";
import { extractMeetingMinutes } from "../../src/mvp-4/minutes-extraction-agent";
import { assembleContextBundle } from "../../src/mvp-2/context-bundle-assembler";
import { ingestTranscript } from "../../src/mvp-1/transcript-ingestor";

const describeWithApiKey = process.env.ANTHROPIC_API_KEY ? describe : describe.skip;

describeWithApiKey("MVP-5: Issue Extraction", () => {
  let contextBundlePayload: any;
  let minutesPayload: any;
  let transcriptRawText: string;

  beforeAll(async () => {
    transcriptRawText = `Alice: We have critical performance issues in the backend.
Bob: What kind of issues?
Alice: High latency on database queries. We need to optimize the indexes.
Bob: I can work on that. When do we need it?
Carol: By end of month ideally.
Alice: Also, we should review our security policies.
Bob: Good point. That's a risk if we don't address it soon.
Carol: I'll take that action item.
Alice: Great, let's make sure we track these.`;

    const ingestResult = await ingestTranscript({
      raw_text: transcriptRawText,
      source_file: "tech-meeting.txt",
      duration_minutes: 45,
      language: "en",
    });

    if (ingestResult.success && ingestResult.transcript_artifact) {
      const assembleResult = await assembleContextBundle(
        ingestResult.transcript_artifact
      );
      if (assembleResult.success && assembleResult.context_bundle) {
        contextBundlePayload = assembleResult.context_bundle;

        const minutesResult = await extractMeetingMinutes(contextBundlePayload);
        if (minutesResult.success && minutesResult.meeting_minutes_artifact) {
          minutesPayload = minutesResult.meeting_minutes_artifact;
        }
      }
    }
  });

  it("should extract issues successfully", async () => {
    const result = await extractIssues(contextBundlePayload, minutesPayload);

    expect(result.success).toBe(true);
    expect(result.issue_registry_artifact).toBeDefined();
    expect(result.issue_registry_artifact?.artifact_type).toBe(
      "issue_registry_artifact"
    );
    expect(result.issue_registry_artifact?.schema_version).toBe("1.0.0");
  });

  it("should include issues array", async () => {
    const result = await extractIssues(contextBundlePayload, minutesPayload);

    expect(result.success).toBe(true);
    expect(Array.isArray(result.issue_registry_artifact?.issues)).toBe(true);
  });

  it("should have source_turn_ref for all issues (CRITICAL)", async () => {
    const result = await extractIssues(contextBundlePayload, minutesPayload);

    expect(result.success).toBe(true);
    const issues = result.issue_registry_artifact?.issues || [];
    expect(issues.length).toBeGreaterThan(0);

    for (const issue of issues) {
      expect(issue.source_turn_ref).toBeDefined();
      expect(issue.source_turn_ref.length).toBeGreaterThan(0);
    }
  });

  it("should have required fields for each issue", async () => {
    const result = await extractIssues(contextBundlePayload, minutesPayload);

    expect(result.success).toBe(true);
    const issues = result.issue_registry_artifact?.issues || [];

    for (const issue of issues) {
      expect(issue.issue_id).toBeDefined();
      expect(["finding", "action_item", "risk"]).toContain(issue.type);
      expect(issue.description).toBeDefined();
      expect(issue.description.length).toBeGreaterThan(0);
      expect(["high", "medium", "low"]).toContain(issue.priority);
      expect(["open", "closed"]).toContain(issue.status);
    }
  });

  it("should extract issues with diverse types", async () => {
    const result = await extractIssues(contextBundlePayload, minutesPayload);

    expect(result.success).toBe(true);
    const issues = result.issue_registry_artifact?.issues || [];
    const types = new Set(issues.map((i: any) => i.type));

    expect(types.size).toBeGreaterThan(0);
  });

  it("should emit execution record on success", async () => {
    const result = await extractIssues(contextBundlePayload, minutesPayload);

    expect(result.success).toBe(true);
    expect(result.execution_record).toBeDefined();
    expect(result.execution_record?.artifact_type).toBe("pqx_execution_record");
    expect(result.execution_record?.execution_status).toBe("succeeded");
    expect(result.execution_record?.pqx_step.name).toContain("Issue");
    expect(result.execution_record?.inputs.artifact_ids.length).toBeGreaterThan(0);
    expect(result.execution_record?.outputs.artifact_ids).toContain(
      result.issue_registry_artifact?.artifact_id
    );
  });

  it("should link trace context", async () => {
    const result = await extractIssues(contextBundlePayload, minutesPayload);

    expect(result.success).toBe(true);
    expect(result.issue_registry_artifact?.trace.trace_id).toBeDefined();
    expect(result.execution_record?.trace.trace_id).toBe(
      result.issue_registry_artifact?.trace.trace_id
    );
  });

  it("should emit execution record on failure", async () => {
    const result = await extractIssues(null, null);

    expect(result.success).toBe(false);
    expect(result.execution_record).toBeDefined();
    expect(result.execution_record?.execution_status).toBe("failed");
    expect(result.error_codes).toContain("extraction_error");
  });

  it("should require source_turn_ref on every issue", async () => {
    const result = await extractIssues(contextBundlePayload, minutesPayload);

    if (result.success) {
      const issues = result.issue_registry_artifact?.issues || [];
      for (const issue of issues) {
        expect(issue.source_turn_ref).toBeTruthy();
        expect(issue.source_turn_ref.length).toBeGreaterThan(0);
      }
    }
  });
});
