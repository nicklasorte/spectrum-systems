# Spectrum Systems Dashboard SLOs

## Dashboard Uptime SLO (99.95%)
- **Target**: 99.95% availability (21.6 minutes downtime/month)
- **Measured**: Synthetic health checks every 5 minutes
- **Alert Threshold**: Downtime > 5 minutes
- **Escalation**: Page on-call engineer if > 15 minutes

## Query Timeout SLO (5s max)
- **Target**: 99% of queries complete in < 5 seconds
- **Measured**: API response time tracking
- **Alert Threshold**: p99 latency > 5s
- **Escalation**: Investigate slow queries, optimize if needed

## Metric Freshness SLO (60s max age)
- **Target**: Entropy snapshot refreshed within 60 seconds
- **Measured**: Timestamp difference between now and latest snapshot
- **Alert Threshold**: Metric age > 120s
- **Escalation**: Check artifact API, restart if needed

## Error Rate SLO (< 1%)
- **Target**: < 1% of API requests return errors
- **Measured**: 5xx / total requests (1-hour rolling window)
- **Alert Threshold**: Error rate > 1%
- **Escalation**: Page on-call, investigate error logs

## MTTR SLO (30 minutes)
- **Target**: Mean Time To Recovery = 30 minutes max
- **Measured**: Time from alert to system operational again
- **Alert Threshold**: Any page alert
- **Escalation**: Follow incident response runbook
