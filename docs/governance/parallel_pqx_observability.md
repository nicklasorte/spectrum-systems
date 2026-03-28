# PQX-CLT-022 — Parallel PQX Observability Policy (2-Slice Governed Mode)

- **Date Activated:** 2026-03-28
- **Status:** **ACTIVE**
- **Scope:** Repository-native governance observability for **2-slice parallel PQX** runs only

## 1) Purpose

Define how parallel PQX behavior is measured, tracked, and analyzed over time to detect:

1. cross-slice interference,
2. behavior drift from expected governed outcomes,
3. reliability degradation in repeated parallel operation.

This policy is documentation/governance only and introduces **no runtime instrumentation**, **no test changes**, **no certification logic changes**, and **no CLI/CI behavior changes**.

## 2) Required Metrics (Canonical Set)

All parallel observability records and rollups must include the following metrics.

1. **parallel_run_count**
   - Total count of completed 2-slice parallel runs within the reporting window.
2. **pass_fail_rate**
   - Ratio and percentage of `pass` vs `fail` outcomes for completed runs.
3. **slice_local_failure_rate**
   - Percentage of runs classified with `slice_local_failure`.
4. **cross_slice_interference_rate**
   - Percentage of runs classified with `cross_slice_interference`.
5. **ambiguous_failure_rate**
   - Percentage of runs classified with `ambiguous_failure`.
6. **rollback_frequency**
   - Percentage of runs requiring rollback actions.
7. **recovery_success_rate**
   - Percentage of rollback/containment events that conclude `recovered`.
8. **certification_path_stability**
   - Percentage of runs where promotion/certification path is explicitly `unchanged`.

## 3) Classification Inputs and Normalization

To keep trend analysis deterministic, each completed run must be normalized into bounded fields:

- **Outcome:** `pass | fail`
- **Failure Type (if fail):** `slice_local_failure | cross_slice_interference | ambiguous_failure`
- **Rollback Required:** `YES | NO`
- **Recovery Status:** `recovered | unrecovered | not_applicable`
- **Certification Path Status:** `unchanged | requires-review | blocked`

If a run cannot be unambiguously normalized into these fields, it is treated as `ambiguous_failure`.

## 4) Signal Categories (Bounded)

Operational signal for the current window must be one of:

1. **stable**
2. **degraded**
3. **unstable**

No additional category values are allowed.

## 5) Alert Thresholds and Category Rules

Threshold evaluation is fail-closed and evaluated per reporting window.

### 5.1 Stable

Classify as `stable` only when all are true:

- `cross_slice_interference_rate` ≤ **2%**
- `ambiguous_failure_rate` = **0%**
- `rollback_frequency` ≤ **5%**
- `recovery_success_rate` ≥ **95%**
- `certification_path_stability` ≥ **98%**

### 5.2 Degraded

Classify as `degraded` when any of the below are true and `unstable` conditions are not met:

- `cross_slice_interference_rate` > **2%** and ≤ **5%**
- `slice_local_failure_rate` > **5%** and ≤ **10%**
- `rollback_frequency` > **5%** and ≤ **10%**
- `recovery_success_rate` < **95%** and ≥ **85%**
- `certification_path_stability` < **98%** and ≥ **90%**
- Any required signal is unclear or partially evidenced
- Any required metric is missing

### 5.3 Unstable

Classify as `unstable` when any of the below are true:

- `cross_slice_interference_rate` > **5%**
- `ambiguous_failure_rate` > **1%**
- `slice_local_failure_rate` > **10%**
- `rollback_frequency` > **10%**
- `recovery_success_rate` < **85%**
- `certification_path_stability` < **90%**
- Two consecutive degraded windows with no documented remediation closure

## 6) Alert and Control Actions

The following minimum actions are mandatory:

1. **Cross-slice interference threshold breach**
   - If `cross_slice_interference_rate` exceeds the degraded threshold (>2%), flag the window as at least `degraded`.
2. **Ambiguous failure threshold breach**
   - If `ambiguous_failure_rate` exceeds 1%, classify as `unstable` and **block further parallel runs** until remediation and explicit review sign-off.
3. **Certification instability threshold breach**
   - If `certification_path_stability` falls below 90%, classify as `unstable` and revert execution mode to serial PQX pending investigation.

## 7) Fail-Closed Observability Rule (Mandatory)

Observability is fail-closed:

1. If any required signal is unclear, classify as **degraded** at minimum.
2. If any required metric is missing, classify as **degraded** at minimum.
3. If ambiguity cannot be resolved within the reporting window, escalate to `unstable` via `ambiguous_failure` accounting.

Soft conclusions such as “likely stable” are not permitted.

## 8) Required Artifacts and Tracking Surface

For every completed 2-slice run, operators must produce:

- `docs/review-actions/parallel_pqx_observability_template.md` (filled record)

Trend review may aggregate those records into periodic governance summaries, but the per-run record is authoritative.

## 9) Governance Boundaries

This policy intentionally stays at the documentation and governance layer.

It does **not**:

- add runtime instrumentation,
- modify tests,
- modify certification logic,
- modify CLI/CI behavior.
