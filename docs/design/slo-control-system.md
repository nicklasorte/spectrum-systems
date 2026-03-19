# SLO Control System — Design Document (Prompt BR)

## Purpose

Decision-grade systems must not proceed when their outputs are untrustworthy.
The SLO Control Layer exists to enforce that constraint mechanically, without
relying on human review to catch every quality failure.

In spectrum engineering workflows the artifacts produced by BE (Run Output
Evaluation), BF (Cross-Run Intelligence), and BG (Working Paper Evidence Pack
Synthesis) form a chain of trust.  Each layer depends on the integrity of the
one before it.  If BG produces an evidence pack with incomplete sections,
missing traceability, or stale data, any downstream working paper or agency
submission built from that pack inherits those defects.

The SLO Control Layer (Prompt BR) evaluates three Service Level Indicators
(SLIs) against governed thresholds and emits a deterministic
`slo_evaluation` artifact.  The key field is `allowed_to_proceed`: when it is
`false` the downstream pipeline must stop.

This is a **control system**, not a reporting feature.  The distinction
matters:

- A reporting system records what happened.
- A control system changes what is allowed to happen next.

---

## SLI Definitions

### completeness

**What it measures:** Whether the BG evidence pack contains all required
working-paper sections populated with evidence, and whether the number of
ranked findings falls within the expected healthy range (3–7).

**Inputs:**
- `section_evidence` array from the BG artifact — sections with
  `synthesis_status` of `populated` or `partial` are counted as present.
- `ranked_findings` array — a count outside [3, 7] incurs a score penalty.
- When no BG artifact is present, BE-only inputs yield a partial score (0.5).
- When neither BE nor BG is present, the score is 0.0.

**Why it matters:** An evidence pack missing sections cannot support a
complete working paper.  A pack with zero findings provides no decision
support.

---

### timeliness

**What it measures:** How current the BG artifact is, based on its
`generated_at` timestamp relative to the current wall-clock time.

**Scoring:**
| Age        | Score |
|------------|-------|
| ≤ 24 h     | 1.0   |
| 25–72 h    | 0.95  |
| 73 h–1 wk  | 0.90  |
| > 1 wk     | 0.80  |

**Fallback:** If `generated_at` is absent, malformed, or in the future, the
score is `1.0` (assume fresh).  This ensures the layer never crashes on
missing timestamp data.

**Why it matters:** Spectrum studies are time-sensitive.  Decisions made on
stale evidence carry unquantified risk.  However, the fallback prevents the
control layer from blocking pipelines when timestamps are legitimately absent.

---

### traceability

**What it measures:** Whether the evidence items in the BG pack can be traced
back to specific BE and/or BF source artifacts.

**Scoring:**
- Base score = fraction of `source_artifacts` entries that carry a valid
  `artifact_id` or `source_bundle_id`.
- Citation rate = fraction of individual `evidence_items` across all sections
  that carry `source_artifact_id` or `source_bundle_id`.
- Final score = `0.6 × base_score + 0.4 × citation_rate` when evidence items
  are present.
- BE-only path (no BG) yields 0.7 — partial traceability since BE artifacts
  are present but cannot be linked through a synthesis layer.
- No inputs at all yields 0.0.

**Why it matters:** Untraceable evidence cannot be reviewed, defended, or
corrected.  The FCC and NTIA require defensible provenance for all technical
claims submitted to regulatory proceedings.

---

## Threshold Classification

| SLI value  | Classification | Severity |
|------------|----------------|----------|
| ≥ 0.95     | healthy        | none     |
| 0.85–0.95  | degraded       | low      |
| 0.70–0.85  | violated       | medium   |
| 0.50–0.70  | violated       | high     |
| < 0.50     | violated       | critical |

---

## Error Budget Philosophy

**The system is allowed to fail — within limits.**

No system achieves perfect SLIs on every run.  Data may be stale by hours,
a section may be partially populated, or a finding may lack a citation.
These are acceptable within the error budget.

**Error budget model:**
```
remaining  = mean(completeness, timeliness, traceability)
burn_rate  = 1 − remaining
```

**When the budget is exhausted, change must stop.**

`allowed_to_proceed` is set to `false` when either of these conditions holds:

1. `slo_status == "violated"` — any SLI is critically, highly, or medium-
   severity violated.
2. `burn_rate > 0.2` — more than 20% of the aggregate quality budget has
   been consumed, even if no single SLI is individually violated.

The 0.2 burn-rate threshold reflects a deliberate design choice: the system
can tolerate small imperfections across all three dimensions, but not a
consistent 20%+ degradation in aggregate quality.

---

## Relationship to the BC → BD → BE → BF → BG → BR Pipeline

```
BC  Runtime Compatibility Check
 │
BD  Run Bundle Contract Hardening
 │
BE  Run Output Normalization and Evaluation
 │                         ┐
BF  Cross-Run Intelligence └─── both feed ──→ BG
 │                                              │
BG  Working Paper Evidence Pack Synthesis       │
 │                                              │
BR  SLO Control ◄───────────────────────────────┘
     │
     └── allowed_to_proceed=true  → proceed to working paper generation
     └── allowed_to_proceed=false → pipeline halts; operator review required
```

BR is the final governed gate in the evidence assembly pipeline.  It consumes
the outputs of BE, BF, and BG and decides whether the system has met its
quality commitments before a working paper is produced.

---

## Example Outputs

### Healthy

```json
{
  "slo_status": "healthy",
  "allowed_to_proceed": true,
  "slis": {
    "completeness": 1.0,
    "timeliness": 1.0,
    "traceability": 0.96
  },
  "violations": [],
  "error_budget": {
    "remaining": 0.9867,
    "burn_rate": 0.0133
  }
}
```

All SLIs are ≥ 0.95.  No violations.  Burn rate is well under 0.2.
The pipeline proceeds.

---

### Degraded

```json
{
  "slo_status": "degraded",
  "allowed_to_proceed": true,
  "slis": {
    "completeness": 0.875,
    "timeliness": 1.0,
    "traceability": 0.95
  },
  "violations": [
    {
      "sli": "completeness",
      "severity": "low",
      "description": "completeness SLI is degraded (value=0.8750). Expected >=0.95 for healthy operation."
    }
  ],
  "error_budget": {
    "remaining": 0.9417,
    "burn_rate": 0.0583
  }
}
```

One SLI is in the degraded band.  Burn rate is below 0.2.  The pipeline is
allowed to continue, but the operator should investigate missing sections.

---

### Violated

```json
{
  "slo_status": "violated",
  "allowed_to_proceed": false,
  "slis": {
    "completeness": 0.375,
    "timeliness": 1.0,
    "traceability": 0.5
  },
  "violations": [
    {
      "sli": "completeness",
      "severity": "critical",
      "description": "completeness SLI is violated (value=0.3750). Expected >=0.95 for healthy operation."
    },
    {
      "sli": "traceability",
      "severity": "high",
      "description": "traceability SLI is violated (value=0.5000). Expected >=0.95 for healthy operation."
    }
  ],
  "error_budget": {
    "remaining": 0.625,
    "burn_rate": 0.375
  }
}
```

Two SLIs are critically/highly violated.  Burn rate is 37.5%, well above the
0.2 threshold.  `allowed_to_proceed` is `false`.  The pipeline must halt and
the operator must rerun BG with corrected inputs before proceeding.

---

## Design Constraints

- **Fail-safe, not fail-open.** Any ambiguity in SLI computation defaults to
  a conservative (lower) score rather than an optimistic one.
- **No hallucinated metrics.** SLI scores are derived only from measurable
  artifact properties.  If a property is absent, the scoring logic applies a
  defined fallback rather than inventing a value.
- **Partial-input support.** The layer accepts BE-only inputs (no BF or BG)
  and produces a valid, schema-compliant evaluation artifact.
- **No crashes on missing optional data.** Every scoring function handles
  missing keys, null values, and malformed timestamps without raising
  exceptions.
- **Deterministic outputs.** Given the same inputs and the same `created_at`
  timestamp, the layer always produces the same `evaluation_id`.

---

## Governed Schema

The `slo_evaluation` artifact is validated against:

```
contracts/schemas/slo_evaluation.schema.json
```

The schema uses JSON Schema 2020-12 with `additionalProperties: false`
throughout to prevent undeclared fields from passing validation.

---

## CLI Usage

```bash
# BE-only evaluation
python scripts/slo_control.py \
    --be-input outputs/be/normalized_run_result.json \
    --output-dir outputs/slo/

# Full BE + BF + BG evaluation
python scripts/slo_control.py \
    --be-input outputs/be/nrr_run1.json \
    --be-input outputs/be/nrr_run2.json \
    --bf-input outputs/bf/cross_run_intelligence_decision.json \
    --bg-input outputs/bg/working_paper_evidence_pack.json \
    --output-dir outputs/slo/
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0    | healthy — all SLIs ≥ 0.95 and burn\_rate ≤ 0.2 |
| 1    | degraded — at least one SLI in the 0.85–0.95 band |
| 2    | violated — at least one SLI < 0.85 or burn\_rate > 0.2 |
