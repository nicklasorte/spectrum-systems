import * as crypto from "crypto";
import { v4 as uuidv4 } from "uuid";

/**
 * Replay Bundle: captures all inputs needed to re-execute a run deterministically
 * Enables "given the same inputs and seeds, produce identical results"
 */

export interface ReplayBundle {
  artifact_kind: "replay_bundle";
  artifact_id: string;
  created_at: string;
  original_run_id: string;
  original_execution_record_id: string;
  seeds: Record<string, number>;
  model_versions: Record<string, string>;
  prompt_versions: Record<string, string>;
  input_hashes: Record<string, string>;
  execution_manifest: {
    step_name: string;
    step_version: string;
    start_time: string;
    end_time: string;
    duration_ms: number;
  };
  trace_context: {
    trace_id: string;
    span_id?: string;
  };
}

export function createReplayBundle(
  originalRunId: string,
  executionRecordId: string,
  stepName: string,
  stepVersion: string,
  startTime: Date,
  endTime: Date
): ReplayBundle {
  return {
    artifact_kind: "replay_bundle",
    artifact_id: uuidv4(),
    created_at: new Date().toISOString(),
    original_run_id: originalRunId,
    original_execution_record_id: executionRecordId,
    seeds: {},
    model_versions: {},
    prompt_versions: {},
    input_hashes: {},
    execution_manifest: {
      step_name: stepName,
      step_version: stepVersion,
      start_time: startTime.toISOString(),
      end_time: endTime.toISOString(),
      duration_ms: endTime.getTime() - startTime.getTime(),
    },
    trace_context: {
      trace_id: uuidv4(),
      span_id: uuidv4(),
    },
  };
}

export function recordSeed(
  bundle: ReplayBundle,
  componentName: string,
  seed: number
): void {
  bundle.seeds[componentName] = seed;
}

export function recordModelVersion(
  bundle: ReplayBundle,
  stepName: string,
  modelId: string
): void {
  bundle.model_versions[stepName] = modelId;
}

export function recordPromptVersion(
  bundle: ReplayBundle,
  stepName: string,
  promptHash: string
): void {
  bundle.prompt_versions[stepName] = promptHash;
}

export function recordInputHash(
  bundle: ReplayBundle,
  inputName: string,
  input: any
): void {
  const hash = crypto
    .createHash("sha256")
    .update(JSON.stringify(input))
    .digest("hex");
  bundle.input_hashes[inputName] = `sha256:${hash}`;
}

export interface ReplayRecord {
  artifact_kind: "replay_record";
  artifact_id: string;
  created_at: string;
  original_bundle_id: string;
  replay_run_id: string;
  match: boolean;
  differences?: string[];
  match_rate: number; // percentage of outputs that match
  trace_context: {
    trace_id: string;
  };
}

export function createReplayRecord(
  bundleId: string,
  replayRunId: string,
  match: boolean,
  matchRate: number,
  differences?: string[]
): ReplayRecord {
  return {
    artifact_kind: "replay_record",
    artifact_id: uuidv4(),
    created_at: new Date().toISOString(),
    original_bundle_id: bundleId,
    replay_run_id: replayRunId,
    match,
    differences,
    match_rate: matchRate,
    trace_context: {
      trace_id: uuidv4(),
    },
  };
}
