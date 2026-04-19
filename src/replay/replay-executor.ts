import {
  ReplayBundle,
  createReplayRecord,
  ReplayRecord,
} from "./replay-bundle";
import { v4 as uuidv4 } from "uuid";

/**
 * Replay Executor: re-runs a step with identical seeds and model versions
 * Verifies that outputs match (deterministic within tolerance)
 */

export async function replayExecution(
  bundle: ReplayBundle,
  executeStepFn: (
    seeds: Record<string, number>,
    modelVersions: Record<string, string>
  ) => Promise<any>,
  originalOutput: any
): Promise<ReplayRecord> {
  const replayRunId = uuidv4();

  try {
    // Re-execute with same seeds and model versions
    const replayOutput = await executeStepFn(
      bundle.seeds,
      bundle.model_versions
    );

    // Compare outputs
    const match =
      JSON.stringify(originalOutput) === JSON.stringify(replayOutput);
    const matchRate = match ? 100 : computeMatchRate(originalOutput, replayOutput);

    const differences = !match
      ? identifyDifferences(originalOutput, replayOutput)
      : undefined;

    return createReplayRecord(
      bundle.artifact_id,
      replayRunId,
      match,
      matchRate,
      differences
    );
  } catch (error) {
    return createReplayRecord(
      bundle.artifact_id,
      replayRunId,
      false,
      0,
      [`Replay execution failed: ${error}`]
    );
  }
}

function computeMatchRate(original: any, replayed: any): number {
  // Simplified: for JSON, compare field-by-field
  if (typeof original !== "object" || typeof replayed !== "object") {
    return 0;
  }

  const originalKeys = Object.keys(original).length;
  let matchingKeys = 0;

  for (const key of Object.keys(original)) {
    if (
      JSON.stringify(original[key]) === JSON.stringify(replayed[key])
    ) {
      matchingKeys++;
    }
  }

  return (matchingKeys / originalKeys) * 100;
}

function identifyDifferences(original: any, replayed: any): string[] {
  const differences: string[] = [];

  if (typeof original !== "object" || typeof replayed !== "object") {
    differences.push("Output types differ");
    return differences;
  }

  for (const key of Object.keys(original)) {
    if (JSON.stringify(original[key]) !== JSON.stringify(replayed[key])) {
      differences.push(`Field '${key}' differs`);
    }
  }

  return differences;
}
