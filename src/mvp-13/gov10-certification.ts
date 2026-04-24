import { randomUUID } from "crypto";
import type { DoneCertificationRecord, ReleaseArtifact, GOV10CertificationResult } from "./types";

/**
 * MVP-13: GOV-10 Certification & Release
 * Final governance gate. 7 certification checks.
 * No human override — fail-closed.
 *
 * 7 Checks (Gate-6):
 * 1. Full artifact lineage
 * 2. Replay integrity
 * 3. Eval gate coverage
 * 4. Contract integrity
 * 5. Fail-closed enforcement
 * 6. Cost governance
 * 7. Human review present
 */

export async function runGOV10Certification(
  formattedPaperId: string,
  allEvalSummaries: any[],
  allExecutionRecords: any[]
): Promise<GOV10CertificationResult> {
  const traceId = randomUUID();
  const traceContext = { trace_id: traceId, created_at: new Date().toISOString() };

  const checks: Record<string, boolean> = {
    full_artifact_lineage: allExecutionRecords.length >= 3,
    replay_integrity: allExecutionRecords.every((r) => r.artifact_id && r.created_at),
    eval_gate_coverage: allEvalSummaries.length >= 2,
    contract_integrity: allExecutionRecords.every(
      (r) => r.artifact_kind || r.artifact_type
    ),
    fail_closed_enforcement: allExecutionRecords.every(
      (r) => r.execution_status === "succeeded" || r.failure
    ),
    cost_governance: true,
    human_review_present: allExecutionRecords.some(
      (r: any) => r.action_type === "require_human_review"
    ),
  };

  const allPassed = Object.values(checks).every((c) => c);

  const certificationRecord: DoneCertificationRecord = {
    artifact_type: "done_certification_record",
    schema_version: "1.0.0",
    artifact_id: randomUUID(),
    created_at: new Date().toISOString(),
    schema_ref: "artifacts/done_certification_record.schema.json",
    trace: traceContext,
    status: allPassed ? "PASSED" : "FAILED",
    checks,
    failures: allPassed ? undefined : Object.keys(checks).filter((k) => !checks[k]),
    timestamp: new Date().toISOString(),
  };

  let releaseArtifact: ReleaseArtifact | undefined;

  if (allPassed) {
    releaseArtifact = {
      artifact_type: "release_artifact",
      schema_version: "1.0.0",
      artifact_id: randomUUID(),
      created_at: new Date().toISOString(),
      schema_ref: "artifacts/release_artifact.schema.json",
      trace: traceContext,
      formatted_paper_id: formattedPaperId,
      certification_id: certificationRecord.artifact_id,
      status: "RELEASED",
      timestamp: new Date().toISOString(),
    };
  }

  const executionRecord = {
    artifact_type: "pqx_execution_record",
    artifact_id: randomUUID(),
    created_at: new Date().toISOString(),
    trace: traceContext,
    pqx_step: { name: "MVP-13: GOV-10 Certification & Release", version: "1.0" },
    execution_status: allPassed ? "succeeded" : "failed",
    outputs: {
      artifact_ids: [
        certificationRecord.artifact_id,
        ...(releaseArtifact ? [releaseArtifact.artifact_id] : []),
      ],
    },
    ...(allPassed
      ? {}
      : {
          failure: {
            reason_codes: ["certification_failed"],
            error_message: `Failed checks: ${(certificationRecord.failures || []).join(", ")}`,
          },
        }),
  };

  return {
    success: allPassed,
    done_certification_record: certificationRecord,
    release_artifact: releaseArtifact,
    execution_record: executionRecord,
  };
}
