# MVP Pipeline → Governance Integration

## Architecture

```
MVP-1 (Transcript) → transcript_artifact
↓
MVP-2 (Context) → context_bundle_artifact (depends_on MVP-1)
↓
MVP-3 (Eval) → eval_result (evaluated_by transcript)
↓ (GATE: eval_pass_rate > 85% to proceed)
…
↓
MVP-13 (Certification) → promotion_decision (signed, verified)
↓
RELEASE: release_artifact emitted if promotion_decision.decision == "allow_release"
```

## SLI Recording Points

Each MVP records measurements that feed into SLI burn-rate tracking:

- **MVP-1**: transcription_latency, transcript_schema_validity
- **MVP-3**: eval_pass_rate, eval_cases_covered
- **MVP-6**: extraction_eval_pass_rate
- **MVP-9**: draft_quality_score
- **MVP-13**: cost_per_run, trace_coverage, total_pipeline_latency

## Control Decision Gates

After certain MVPs, control loop queries governance signals:

- **After MVP-3**: if eval_pass_rate < 85% → BLOCK (postmortem required)
- **After MVP-6**: if extraction_quality < threshold → FREEZE
- **After MVP-9**: if draft_quality < threshold → require human review
- **After MVP-13**: if cost > budget OR trace < 95% → block release

## Lineage Recording

Every edge is recorded in the lineage graph:
- MVP-2 depends_on MVP-1
- MVP-3 evaluated_by eval_case_suite
- MVP-4 caused_by MVP-2
- ... etc

Full DAG reconstructable post-run.

## Component Modules

### PipelineConnector
Orchestrates all 13 MVPs with artifact recording, SLI measurement, and lineage tracking.

- `mvp1_transcript_ingestion(transcriptPath)` - Ingest and record transcript
- `mvp3_eval_gate(transcriptArtifact)` - Evaluate with governance gate
- `mvp13_certification(allArtifacts)` - Sign and certify for release

### ControlLoopEngine
Queries governance signals and makes promotion decisions.

- `checkControlSignals(sliName)` - Get active alerts and drift signals
- `decidePromotion(artifactId, sliMeasurements)` - Make allow/warn/freeze/block decision

## Usage

```typescript
const connector = new PipelineConnector(hub, controlLoop, signer);

// Run MVP-1
const transcript = await connector.mvp1_transcript_ingestion("meeting.txt");

// Run MVP-3 with eval gate
const evalResult = await connector.mvp3_eval_gate(transcript.artifact);
if (evalResult.decision_gate === "block") {
  throw new Error("Eval gate blocked pipeline");
}

// Run MVP-13 for certification
const certified = await connector.mvp13_certification([transcript.artifact]);
if (certified.artifact.decision !== "allow_release") {
  throw new Error("Certification failed");
}
```
