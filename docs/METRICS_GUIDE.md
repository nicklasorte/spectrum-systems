# Entropy Metrics Interpretation Guide

## Decision Divergence
**What it means**: % of decisions that contradict previous decisions on similar contexts
**Good range**: 0-10%
**Action if high**: Review policy consistency, merge conflicting rules
**Example**: Same user input → different allow/deny decisions = divergence spike

## Exception Rate
**What it means**: % of decisions that required manual override (vs auto-allow)
**Good range**: 0-2%
**Action if high**: Policies may be too strict, review blocks + escalations
**Example**: "Policy blocked this, but human said OK" = exception

## Trace Coverage
**What it means**: % of decisions with end-to-end trace (for replay/audit)
**Good range**: 99.9%+
**Action if below SLO**: Check trace propagation, add W3C headers
**Example**: Can replay this decision → audit + debugging possible

## Calibration Drift
**What it means**: Judge confidence vs actual correctness (should match)
**Good range**: 0-5%
**Action if high**: Judge may be overconfident or underconfident
**Example**: Judge says "90% confident" but only right 60% of time

## Override Hotspots
**What it means**: Gates with unusually high manual exception rates
**Good range**: 0
**Action if > 0**: These gates may need policy updates or removal
**Example**: "Auto-deny user logins" overridden 100x = hot spot

## Failure-to-Eval Rate
**What it means**: % of incidents NOT caught by any eval before they happened
**Good range**: < 1%
**Action if high**: Add evals for this failure class
**Example**: Incident happened but no eval existed to catch it = eval gap

## Dashboard Navigation

### Entropy Snapshot
- **Location**: Dashboard home page
- **Refresh rate**: Every 30 seconds
- **Cache**: Local cache for 5 seconds
- **Fallback**: Cached data if API unavailable

### Query Results
- **Location**: Various dashboard tabs
- **Refresh rate**: Manual (click "Refresh") or auto every 60 seconds
- **Cache**: 30-second cache for performance
- **Queries available**:
  - Reason codes (top blocks)
  - Rising overrides
  - Cost increases
  - Context contradictions
  - Judge disagreement
  - Failure patterns
  - Incident drills
  - Reviewer bias

### Health Status
- **Location**: Top right corner of dashboard
- **Checks**: Artifact API, Database, Trace collection
- **Endpoint**: `/api/metrics/health`
- **Frequency**: Checked every 5 minutes

### SLO Dashboard
- **Location**: Settings → SLOs
- **Metrics tracked**:
  - Uptime (99.95% target)
  - Query latency (5s p99 target)
  - Metric freshness (60s target)
  - Error rate (< 1% target)
  - MTTR (30m target)
