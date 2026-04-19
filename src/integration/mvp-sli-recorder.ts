import { SLIBackend } from "@/src/governance/sli-backend";

/**
 * SLI Recording for Each MVP
 * Each step measures and records its quality metrics
 */

export async function recordMVP3TranscriptEval(
  sliBackend: SLIBackend,
  runId: string,
  evalPassRate: number,
  traceId: string
): Promise<void> {
  await sliBackend.recordMeasurement(
    "transcript_eval_baseline",
    evalPassRate,
    runId,
    { mvp: "MVP-3" },
    traceId
  );
}

export async function recordMVP6ExtractionQuality(
  sliBackend: SLIBackend,
  runId: string,
  minutesAccuracy: number,
  issuesAccuracy: number,
  traceId: string
): Promise<void> {
  await sliBackend.recordMeasurement(
    "extraction_quality_minutes",
    minutesAccuracy,
    runId,
    { mvp: "MVP-6", metric: "minutes" },
    traceId
  );

  await sliBackend.recordMeasurement(
    "extraction_quality_issues",
    issuesAccuracy,
    runId,
    { mvp: "MVP-6", metric: "issues" },
    traceId
  );
}

export async function recordMVP9DraftQuality(
  sliBackend: SLIBackend,
  runId: string,
  draftScore: number,
  traceId: string
): Promise<void> {
  await sliBackend.recordMeasurement(
    "draft_quality_score",
    draftScore,
    runId,
    { mvp: "MVP-9" },
    traceId
  );
}

export async function recordMVP13Certification(
  sliBackend: SLIBackend,
  runId: string,
  costCents: number,
  traceCoverage: number,
  traceId: string
): Promise<void> {
  await sliBackend.recordMeasurement(
    "cost_per_run",
    costCents,
    runId,
    { mvp: "MVP-13" },
    traceId
  );

  await sliBackend.recordMeasurement(
    "trace_coverage",
    traceCoverage,
    runId,
    { mvp: "MVP-13" },
    traceId
  );
}
