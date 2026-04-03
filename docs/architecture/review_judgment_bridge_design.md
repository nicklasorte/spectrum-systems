# Review → Judgment Bridge Design (Design Only)

## Purpose
Define how governed review and eval signals can be synthesized into future `judgment_record` and `judgment_policy` artifacts **without introducing a second authority path**.

## Inputs
- `review_control_signal`
- review-derived `eval_result`
- `review_failure_summary`
- `review_hotspot_report`
- `review_eval_generation_report`
- existing `evaluation_control_decision`

## Outputs (future)
- `judgment_record` candidates (advisory + evidence linkage)
- `judgment_policy` calibration proposals (governed lifecycle only)

## Decision conditions (future)
- Recurrent review failure keys above threshold may propose stricter policy calibration.
- Hard-gate review failures with corroborating eval failures may produce escalation candidates.
- Strategic review findings may propose roadmap-level policy experiments (never direct execution authority).

## Authority boundary
- Control authority remains `evaluation_control_decision`.
- Bridge artifacts are **advisory synthesis only** until governed policy-lifecycle adoption.
- No direct allow/block is emitted by review bridge outputs.

## Determinism requirements
- Canonical JSON hashing for bridge payload IDs.
- Stable ordering of contributing findings/evals.
- Explicit mapping tables only; no inferred taxonomy expansion.
