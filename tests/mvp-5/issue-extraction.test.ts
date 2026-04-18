import { extractIssues } from "@/src/mvp-5/issue-extraction-agent";
import { extractMeetingMinutes } from "@/src/mvp-4/minutes-extraction-agent";
import { assembleContextBundle } from "@/src/mvp-2/context-bundle-assembler";
import { ingestTranscript } from "@/src/mvp-1/transcript-ingestor";

describe("MVP-5: Issue Extraction", () => {
  let contextBundlePayload: any;
  let minutesPayload: any;

  beforeAll(async () => {
    const ingestResult = await ingestTranscript({
      raw_text: `Alice: We have critical backend performance issues.
Bob: What issues?
Alice: High latency on database queries. Need to optimize indexes.
Bob: I can do that by month end.
Carol: Also review security policies.
Alice: That's a risk.`,
      source_file: "tech-meeting.txt",
    });
    if (ingestResult.success && ingestResult.transcript_artifact) {
      const assembleResult = await assembleContextBundle(ingestResult.transcript_artifact.artifact_id);
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
    expect(result.issue_registry_artifact?.artifact_kind).toBe("issue_registry_artifact");
  });

  it("should have issues array", async () => {
    const result = await extractIssues(contextBundlePayload, minutesPayload);
    expect(Array.isArray(result.issue_registry_artifact?.issues)).toBe(true);
  });

  it("all issues should have source_turn_ref", async () => {
    const result = await extractIssues(contextBundlePayload, minutesPayload);
    const issues = result.issue_registry_artifact?.issues || [];
    for (const issue of issues) {
      expect(issue.source_turn_ref).toBeDefined();
      expect(issue.source_turn_ref.length).toBeGreaterThan(0);
    }
  });

  it("should have required fields", async () => {
    const result = await extractIssues(contextBundlePayload, minutesPayload);
    const issues = result.issue_registry_artifact?.issues || [];
    for (const issue of issues) {
      expect(issue.issue_id).toBeDefined();
      expect(["finding", "action_item", "risk"]).toContain(issue.type);
      expect(issue.description).toBeDefined();
    }
  });

  it("should emit execution record", async () => {
    const result = await extractIssues(contextBundlePayload, minutesPayload);
    expect(result.execution_record?.execution_status).toBe("succeeded");
  });
});
