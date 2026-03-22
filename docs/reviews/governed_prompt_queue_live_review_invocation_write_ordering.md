# Governed Prompt Queue Live Review Invocation — Mandatory Write Ordering

This document is the binding implementation ordering contract for LI-CR-3.

## Mandatory ordering

1. assert no prior invocation (idempotency guard)
2. validate trigger lineage
3. transition work item to `review_invoking`
4. invoke provider
5. write schema-valid invocation result artifact
6. persist `review_invocation_result_artifact_path`
7. transition to terminal state

## Enforcement note

Implementations must follow this sequence exactly unless superseded by an explicit ADR.
