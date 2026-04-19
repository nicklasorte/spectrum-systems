# Replay Infrastructure

Capture and deterministically re-execute pipeline steps.

## ReplayBundle

Captures per-run:
- Seeds (random number generator seeds)
- Model versions (exact model IDs)
- Prompt versions (hash of prompt text)
- Input hashes (SHA256 of all inputs)
- Execution manifest (timing, step version)

## ReplayRecord

Result of re-execution:
- match: true if outputs identical
- match_rate: percentage of fields that match
- differences: which fields diverged (for debugging)

## Usage

```typescript
const bundle = createReplayBundle(...);
recordSeed(bundle, "step-1", seed);
recordModelVersion(bundle, "MVP-4", "claude-3-5-haiku...");

// Later, replay:
const record = await replayExecution(bundle, executeStepFn, originalOutput);
if (!record.match) {
  console.warn("Replay diverged:", record.differences);
}
```

## Integration

- Every MVP emits ReplayBundle on execution
- Every control decision stores ReplayBundle ID
- Replay can be triggered for debugging or audit
