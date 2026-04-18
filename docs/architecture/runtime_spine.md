# Runtime Spine (Companion View)

This document is an explanatory companion only.

`docs/architecture/system_registry.md` remains the sole canonical ownership and enforcement source.

This file must not define or restate canonical ownership.

## Purpose

Provide a concise control-flow view of runtime progression and gate outcomes.

For canonical definitions and compatibility wording, see `docs/architecture/system_registry.md`.

## Spine summary

Reference chain:

- AEX → PQX → EVL → TPA → CDE → SEL

Overlay gates in this flow:

- REP
- LIN
- OBS

## Outcome semantics (summary)

### BLOCK (summary)

Use BLOCK when required evidence is absent or invalid.

Typical examples:

- missing required artifact
- missing required eval result
- invalid schema artifact
- incomplete lineage evidence
- missing trace completeness where required
- missing policy result
- missing replay result where required
- missing certification evidence where required

### FREEZE (summary)

Use FREEZE for unstable or unresolved states.

Typical examples:

- replay mismatch
- required eval result is indeterminate
- drift threshold exceeded
- budget threshold exhausted
- governance threshold exhausted

### ALLOW (summary)

Use ALLOW only when required evidence is complete and gating checks pass.

Typical examples:

- required artifacts present
- required eval results pass
- policy admissibility check passes
- lineage completeness passes
- observability completeness passes
- replay check passes where required
- certification evidence present where required

## Reader note

This page is a quick explanatory outline. For canonical language used by tooling and tests, rely on `docs/architecture/system_registry.md`.
