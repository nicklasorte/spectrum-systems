import {
  createReplayBundle,
  recordSeed,
  recordModelVersion,
  recordPromptVersion,
  recordInputHash,
} from "@/src/replay/replay-bundle";
import { replayExecution } from "@/src/replay/replay-executor";

describe("Replay Infrastructure", () => {
  it("should create replay bundle", () => {
    const bundle = createReplayBundle(
      "run-123",
      "exec-456",
      "MVP-4",
      "1.0",
      new Date(),
      new Date()
    );

    expect(bundle.artifact_kind).toBe("replay_bundle");
    expect(bundle.original_run_id).toBe("run-123");
  });

  it("should record seeds", () => {
    const bundle = createReplayBundle(
      "run-123",
      "exec-456",
      "MVP-4",
      "1.0",
      new Date(),
      new Date()
    );
    recordSeed(bundle, "haiku_extraction", 42);

    expect(bundle.seeds.haiku_extraction).toBe(42);
  });

  it("should record model versions", () => {
    const bundle = createReplayBundle(
      "run-123",
      "exec-456",
      "MVP-4",
      "1.0",
      new Date(),
      new Date()
    );
    recordModelVersion(bundle, "MVP-4", "claude-3-5-haiku-20241022");

    expect(bundle.model_versions["MVP-4"]).toBe("claude-3-5-haiku-20241022");
  });

  it("should record input hashes", () => {
    const bundle = createReplayBundle(
      "run-123",
      "exec-456",
      "MVP-4",
      "1.0",
      new Date(),
      new Date()
    );
    recordInputHash(bundle, "context_bundle", { test: "data" });

    expect(bundle.input_hashes.context_bundle).toContain("sha256:");
  });

  it("should replay execution with same seeds", async () => {
    const bundle = createReplayBundle(
      "run-123",
      "exec-456",
      "MVP-4",
      "1.0",
      new Date(),
      new Date()
    );
    recordSeed(bundle, "test", 42);

    const originalOutput = { result: "test" };
    const executeStepFn = async () => ({ result: "test" });

    const record = await replayExecution(bundle, executeStepFn, originalOutput);

    expect(record.artifact_kind).toBe("replay_record");
    expect(record.match).toBe(true);
    expect(record.match_rate).toBe(100);
  });

  it("should detect non-deterministic output", async () => {
    const bundle = createReplayBundle(
      "run-123",
      "exec-456",
      "MVP-4",
      "1.0",
      new Date(),
      new Date()
    );

    const originalOutput = { result: "original" };
    const executeStepFn = async () => ({ result: "different" });

    const record = await replayExecution(bundle, executeStepFn, originalOutput);

    expect(record.match).toBe(false);
    expect(record.match_rate).toBeLessThan(100);
    expect(record.differences?.length).toBeGreaterThan(0);
  });
});
