# FRE Recovery System Action Tracker — 2026-04-05

- Source Review: docs/reviews/2026-04-05-fre-recovery-system-review.md
- Owner: Spectrum Systems maintainers
- Last Updated: 2026-04-05

## Critical Items

### [FRE-REV-01] Repair retry-budget-exhausted terminal artifact path
- **Priority:** Critical
- **Why:** FRE-03 currently cannot emit a schema-valid `blocked` artifact when `recovery_attempt_number > max_attempts` because required evidence arrays are emitted empty.
- **Required change:** Align implementation and schema so budget exhaustion deterministically emits a valid terminal recovery artifact (not an exception-only path).
- **Acceptance evidence:**
  - Add/extend tests that assert retry-budget exhaustion returns valid `recovery_result_artifact` with `recovery_status=blocked`.
  - Confirm artifact validates against `contracts/schemas/recovery_result_artifact.schema.json`.
- **Status:** Open

### [FRE-REV-02] Close FRE-02 mapping gap for FRE-01 root causes
- **Priority:** Critical
- **Why:** Several legal FRE-01 primary root causes currently have no FRE-02 template mapping, causing deterministic hard-stop of the recovery loop.
- **Required change:** Provide deterministic supported handling for every FRE-01 class (template coverage or explicit structured manual-triage artifact path).
- **Acceptance evidence:**
  - Test matrix proving each FRE-01 `primary_root_cause` has a deterministic FRE-02 outcome.
  - No unsupported-root-cause generation failures for schema-valid diagnosis artifacts.
- **Status:** Open

## High-Priority Items

### [FRE-REV-03] Require governance gate evidence in FRE-03 execution handoff
- **Priority:** High
- **Why:** FRE-03 currently depends on caller discipline for preflight/control/certification subordination and does not require explicit gate evidence in execution results.
- **Required change:** Extend execution runner contract and/or orchestration validation to require explicit governance evidence refs when execution is attempted.
- **Acceptance evidence:**
  - Tests showing execution attempt without gate evidence fails closed.
  - Tests showing execution attempt with complete gate evidence passes and is preserved in artifact lineage.
- **Status:** Open

## Medium-Priority Items

### [FRE-REV-04] Improve replay determinism defaults
- **Priority:** Medium
- **Why:** Dynamic timestamp defaults can cause output drift when `emitted_at` is not pinned.
- **Required change:** Enforce explicit emitted timestamp input for governed runs or record deterministic replay-time policy for timestamp normalization.
- **Acceptance evidence:**
  - Tests proving stable output policy under repeated runs.
- **Status:** Open

### [FRE-REV-05] Increase unresolved-state evidence granularity
- **Priority:** Medium
- **Why:** `remaining_failure_classes` currently only preserves primary class, reducing triage precision for partial recovery.
- **Required change:** Preserve deterministic secondary unresolved classification when validation evidence indicates multi-symptom residual failure.
- **Acceptance evidence:**
  - Tests covering mixed validation outcomes with structured residual class outputs.
- **Status:** Open
