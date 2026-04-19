# Lineage Graph + Artifact Intelligence

## Lineage Graph

Queryable dependency graph of artifacts:
- artifact A `caused_by` artifact B
- artifact A `depends_on` artifact C
- artifact A `evaluated_by` eval case X
- artifact A `input_to` artifact D
- artifact A `triggered_by` drift signal Y

Use cases:
- Root cause analysis: trace failure back to originating artifact
- Impact analysis: what broke as a result of this change?
- Dependency resolution: what inputs are required for this artifact?

## Artifact Intelligence Layer

Read-only searchable index:
- Search by artifact_kind, trace_id, created_at, dimensions
- Retrieve all artifacts matching query
- Expose control signals (SLI status, drift, exceptions)
- Link to playbooks for remediation

Operations workflow:
1. Dashboard shows SLI warning
2. Operator searches artifacts created in last hour
3. Finds drift_signal artifact
4. Queries intelligence layer for control signals
5. Gets linked playbook "drift_metric_distribution"
6. Follows runbook to investigate

## Performance Optimizations

- Materialized views for common queries (optional)
- Recursive query limit (maxDepth) to prevent runaway queries
- Index on source/target/relationship for fast traversal
- Smart root cause algorithm weights direct causes higher than transitive

## Maintenance

- Signal expiry: Control signals older than 30 days auto-deleted
- Index cleanup: Stale search index entries older than 7 days removed
- Graph analysis: Can be run offline on materialized snapshots
