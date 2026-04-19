# Pipeline Observability

Real-time visibility into what's actually happening in the MVP pipeline.

## Key Metrics

| Metric | Purpose | Alert Threshold |
|--------|---------|-----------------|
| MVP Latency | Identify bottlenecks | > 2x baseline |
| Cost per Run | Budget tracking | > budget limit |
| Failure Rate | Quality signal | > 10% |
| Trace Completeness | Auditability | < 95% |
| SLI Burn-Rate | Error budget depletion | 2x, 5x, 10x thresholds |

## Dashboard

Visualizes: bottlenecks by MVP, cost trends, failure rates, incident heatmap

Query: `/api/observability/*`

## Incident Investigation

When a run fails:
1. Check lineage graph: which MVP failed first?
2. Check SLI measurements: did an SLI violate threshold?
3. Check control signals: what decision gate blocked?
4. Check trace: is execution fully reconstructible?
5. Check postmortem: was incident reason captured?

## Alerts

- **High failure rate**: > 10% of runs failing
- **Bottleneck detection**: MVP latency > 2x baseline
- **Cost overrun**: total cost > budget
- **Trace gaps**: completeness < 95%
- **SLI burn**: 2x sustainable rate

## SLI Recording

Each MVP records metrics that feed burn-rate tracking:

```
MVP-1: transcription_latency, transcript_schema_validity
MVP-3: eval_pass_rate, eval_cases_covered
MVP-6: extraction_eval_pass_rate
MVP-9: draft_quality_score
MVP-13: cost_per_run, trace_coverage, total_pipeline_latency
```

All measurements recorded durably and queryable via `PipelineMetricsCollector`.
