# Governed Prompt Queue Live Review Invocation — Failure to State Mapping

This document is the binding failure mapping contract for LI-CR-4.

## Required mapping

- provider invocation fails before output received -> `review_invocation_failed`
- artifact write fails -> `blocked`
- queue state update fails after artifact write -> retry update once, then `blocked` if unresolved
- trigger lineage validation fails -> `blocked`
- schema validation fails -> `blocked`

## Enforcement note

Live invocation queue integration must use this mapping deterministically and fail closed.
