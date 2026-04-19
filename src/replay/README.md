# Replay Infrastructure

Captures all inputs needed to re-run a pipeline step.

## ReplayBundle

Captures per-run:
- Seeds: Random number generator seeds
- Model versions: Exact model IDs
- Prompt versions: Hash of prompt text
- Input hashes: SHA256 of all inputs
- Execution manifest: Timing, step version, trace

## ReplayRecord

Result of re-run:
- `outputs_match`: true if identical
- `match_rate`: percentage of matching fields
- `differences`: which fields diverged

## Usage

```typescript
import { 
  createReplayBundle, 
  recordSeed, 
  recordModelVersion, 
  recordInputHash 
} from './replay-bundle';
import { verifyReplay } from './replay-verifier';

const bundle = createReplayBundle(...);
recordSeed(bundle, "step-1", seed);
recordModelVersion(bundle, "MVP-4", "claude-3-5-haiku...");
recordInputHash(bundle, "input", inputData);

// Later, verify:
const record = await verifyReplay(bundle, runStepFn, originalOutput);
if (!record.outputs_match) {
  console.warn("Output diverged:", record.differences);
}
```

## Integration

- Every step run emits ReplayBundle on execution
- Replay can be triggered for debugging or audit
- Deterministic re-execution enables verification of consistency
