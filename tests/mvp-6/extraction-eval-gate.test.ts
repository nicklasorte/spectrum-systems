import { runExtractionEvalGate } from "@/src/mvp-6/extraction-eval-gate";
import { extractIssues } from "@/src/mvp-5/issue-extraction-agent";
import { extractMeetingMinutes } from "@/src/mvp-4/minutes-extraction-agent";
import { assembleContextBundle } from "@/src/mvp-2/context-bundle-assembler";
import { ingestTranscript } from "@/src/mvp-1/transcript-ingestor";

describe("MVP-6: Extraction Eval Gate", () => {
  let minutesArtifactId: string;
  let issueArtifactId: string;

  beforeAll(async () => {
    // Set up: Ingest → assemble → extract minutes → extract issues
    const ingestResult = await ingestTranscript({
      raw_text: `Alice: We need to fix backend performance issues.
Bob: I'll optimize the database queries.
Carol: And we should review security policies.
Alice: Good point.`,
      source_file: "test.txt",
      duration_minutes: 30,
    });

    if (ingestResult.success && ingestResult.transcript_artifact) {
      const assembleResult = await assembleContextBundle(
        ingestResult.transcript_artifact.artifact_id
      );
      if (assembleResult.success && assembleResult.context_bundle) {
        const minutesResult = await extractMeetingMinutes(
          assembleResult.context_bundle
        );
        if (minutesResult.success && minutesResult.meeting_minutes_artifact) {
          minutesArtifactId = minutesResult.meeting_minutes_artifact.artifact_id;

          const issuesResult = await extractIssues(
            assembleResult.context_bundle,
            minutesResult.meeting_minutes_artifact
          );
          if (issuesResult.success && issuesResult.issue_registry_artifact) {
            issueArtifactId = issuesResult.issue_registry_artifact.artifact_id;
          }
        }
      }
    }
  });

  it("should run all 5 eval cases", async () => {
    const result = await runExtractionEvalGate(minutesArtifactId, issueArtifactId);

    expect(result.success).toBe(true);
    expect(result.eval_results?.length).toBe(5);
  });

  it("should pass schema conformance eval", async () => {
    const result = await runExtractionEvalGate(minutesArtifactId, issueArtifactId);

    const schemaEval = result.eval_results?.find(
      (r) => r.details?.case_name === "schema_conformance"
    );
    expect(schemaEval?.status).toBe("pass");
  });

  it("should pass issue source traceability eval", async () => {
    const result = await runExtractionEvalGate(minutesArtifactId, issueArtifactId);

    const tracEval = result.eval_results?.find(
      (r) => r.details?.case_name === "issue_source_traceability"
    );
    expect(tracEval?.status).toBe("pass");
  });

  it("should pass agenda coverage eval", async () => {
    const result = await runExtractionEvalGate(minutesArtifactId, issueArtifactId);

    const agendaEval = result.eval_results?.find(
      (r) => r.details?.case_name === "agenda_coverage"
    );
    expect(agendaEval?.status).toBe("pass");
  });

  it("should pass action item completeness eval", async () => {
    const result = await runExtractionEvalGate(minutesArtifactId, issueArtifactId);

    const actionEval = result.eval_results?.find(
      (r) => r.details?.case_name === "action_item_completeness"
    );
    expect(actionEval?.status).toBe("pass");
  });

  it("should pass replay consistency eval", async () => {
    const result = await runExtractionEvalGate(minutesArtifactId, issueArtifactId);

    const replayEval = result.eval_results?.find(
      (r) => r.details?.case_name === "replay_consistency"
    );
    expect(replayEval?.status).toBe("pass");
  });

  it("should produce eval summary with pass_rate", async () => {
    const result = await runExtractionEvalGate(minutesArtifactId, issueArtifactId);

    expect(result.eval_summary).toBeDefined();
    expect(result.eval_summary?.overall_status).toBe("pass");
    expect(result.eval_summary?.pass_rate).toBe(100);
    expect(result.eval_summary?.metrics.total_cases).toBe(5);
    expect(result.eval_summary?.metrics.passed).toBe(5);
  });

  it("should emit allow control decision when all evals pass", async () => {
    const result = await runExtractionEvalGate(minutesArtifactId, issueArtifactId);

    expect(result.control_decision?.decision).toBe("allow");
    expect(result.control_decision?.rationale).toContain("All extraction eval cases passed");
  });

  it("should emit execution record with all artifacts", async () => {
    const result = await runExtractionEvalGate(minutesArtifactId, issueArtifactId);

    expect(result.execution_record?.artifact_kind).toBe("pqx_execution_record");
    expect(result.execution_record?.execution_status).toBe("succeeded");
    expect(result.execution_record?.outputs.artifact_ids.length).toBeGreaterThan(0);
  });

  it("should fail on missing artifacts", async () => {
    const result = await runExtractionEvalGate("nonexistent", "nonexistent");

    expect(result.success).toBe(false);
    expect(result.error).toContain("Missing artifacts");
  });
});
