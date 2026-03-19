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

The SLO Control Layer (Prompt BR) evaluates four Service Level Indicators
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
back to **known** BE and/or BF source artifact IDs.

**Scoring:**
- Base score = fraction of `source_artifacts` entries whose `artifact_id` or
  `source_bundle_id` matches a known BE/BF artifact ID.  When no known IDs
  are available (BE-only path without a BG), degraded mode falls back to
  presence-only checking.
- Citation rate = fraction of individual `evidence_items` across all sections
  that carry `source_artifact_id` or `source_bundle_id` (presence check).
- Final score = `0.6 × base_score + 0.4 × citation_rate` when evidence items
  are present.
- BE-only path (no BG) yields 0.7 — partial traceability since BE artifacts
  are present but cannot be linked through a synthesis layer.
- No inputs at all yields 0.0.

**Linkage correctness:** When BE or BF artifacts are loaded, the base-score
check validates that `source_artifacts` IDs actually match known artifact IDs
from the loaded inputs — not merely that the field is non-empty.  An evidence
pack that invents artifact IDs absent from BE/BF will not score full
traceability.

**Why it matters:** Untraceable evidence cannot be reviewed, defended, or
corrected.  The FCC and NTIA require defensible provenance for all technical
claims submitted to regulatory proceedings.

---

### traceability_integrity

**What it measures:** Whether the artifact lineage chain for this SLO
evaluation is structurally valid, as determined by the BS Artifact Lineage
System.

**Scoring:**
- 1.0 when all lineage checks pass (or when no registry is provided, which
  is a not-assessed state, not a confirmed-healthy state).
- 0.0 when the lineage registry contains any validation error.

**When a registry is provided:** The full `validate_full_registry` check is
applied.  Any orphan artifact, missing parent type, or broken chain sets the
SLI to 0.0, which drives `slo_status` to `violated` and blocks
`allowed_to_proceed`.

**When no registry is provided:** The SLI defaults to 1.0 (lineage not
assessed).  This is a degraded validation state — operators who care about
lineage must supply a registry via `--lineage-dir`.

---

## Lineage Provenance Requirements

Every `slo_evaluation` artifact is **contract-required** to carry lineage
provenance.  The following fields are required at the schema level:

| Field               | Type    | Constraint       |
|---------------------|---------|------------------|
| `lineage_valid`     | boolean | always required  |
| `parent_artifact_ids` | array of string | required, minItems: 1 |

An SLO artifact without both fields is schema-invalid and must be rejected.

The `parent_artifact_ids` field records the upstream decision and/or synthesis
artifacts that drove this evaluation.  Operators must supply these via the CLI
`--parent-id` flag.

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
remaining  = mean(completeness, timeliness, traceability, traceability_integrity)
burn_rate  = 1 − remaining
```

**When the budget is exhausted, change must stop.**

`allowed_to_proceed` is set to `false` when either of these conditions holds:

1. `slo_status == "violated"` — any SLI is critically, highly, or medium-
   severity violated.
2. `burn_rate > 0.2` — more than 20% of the aggregate quality budget has
   been consumed, even if no single SLI is individually violated.

The 0.2 burn-rate threshold reflects a deliberate design choice: the system
can tolerate small imperfections across all four dimensions, but not a
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
  "lineage_valid": true,
  "parent_artifact_ids": ["DEC-001", "SYN-001"],
  "slis": {
    "completeness": 1.0,
    "timeliness": 1.0,
    "traceability": 0.96,
    "traceability_integrity": 1.0
  },
  "violations": [],
  "error_budget": {
    "remaining": 0.99,
    "burn_rate": 0.01
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
  "lineage_valid": true,
  "parent_artifact_ids": ["DEC-001"],
  "slis": {
    "completeness": 0.875,
    "timeliness": 1.0,
    "traceability": 0.95,
    "traceability_integrity": 1.0
  },
  "violations": [
    {
      "sli": "completeness",
      "severity": "low",
      "description": "completeness SLI is degraded (value=0.8750). Expected >=0.95 for healthy operation."
    }
  ],
  "error_budget": {
    "remaining": 0.9563,
    "burn_rate": 0.0437
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
  "lineage_valid": false,
  "parent_artifact_ids": ["DEC-001"],
  "slis": {
    "completeness": 0.375,
    "timeliness": 1.0,
    "traceability": 0.5,
    "traceability_integrity": 0.0
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
    },
    {
      "sli": "traceability_integrity",
      "severity": "critical",
      "description": "traceability_integrity SLI is violated (value=0.0000). Expected >=0.95 for healthy operation."
    }
  ],
  "error_budget": {
    "remaining": 0.469,
    "burn_rate": 0.531
  }
}
```

Multiple SLIs are critically/highly violated.  Broken lineage drives
`traceability_integrity` to 0.0.  `allowed_to_proceed` is `false`.  The
pipeline must halt and the operator must correct both the lineage chain and
the evidence pack before proceeding.

---

## Design Constraints

- **Fail-safe, not fail-open.** Any ambiguity in SLI computation defaults to
  a conservative (lower) score rather than an optimistic one.
- **No hallucinated metrics.** SLI scores are derived only from measurable
  artifact properties.  If a property is absent, the scoring logic applies a
  defined fallback rather than inventing a value.
- **Partial-input support.** The layer accepts BE-only inputs (no BF or BG)
  and produces a valid, schema-compliant evaluation artifact — provided the
  operator supplies `--parent-id`.
- **No crashes on missing optional data.** Every scoring function handles
  missing keys, null values, and malformed timestamps without raising
  exceptions.
- **Deterministic outputs.** Given the same inputs and the same `created_at`
  timestamp, the layer always produces the same `evaluation_id`.
- **Lineage is enforced, not assumed.** The CLI does not default
  `traceability_integrity` to a fake-healthy state.  When `--lineage-dir` is
  provided, the registry is loaded and validated.  When it is not provided,
  the SLI is 1.0 (not-assessed), and the operator must acknowledge that
  lineage has not been verified.

---

## Governed Schema

The `slo_evaluation` artifact is validated against:

```
contracts/schemas/slo_evaluation.schema.json
```

The schema uses JSON Schema 2020-12 with `additionalProperties: false`
throughout to prevent undeclared fields from passing validation.

**Canonical schema `$id`:**

```
https://spectrum-systems.org/contracts/slo_evaluation.schema.json
```

All governed schemas in this repository use the `https://spectrum-systems.org/contracts/`
base domain.  The `$id` was normalized to this domain (previously
`https://spectrum.systems/contracts/slo_evaluation.schema.json`) so that
future cross-schema `$ref` resolution is unambiguous.

**Required top-level fields** (additions since initial design):
- `lineage_valid` (boolean) — always required; fail-safe defaults to `false`
  when not explicitly set.
- `parent_artifact_ids` (array of string, minItems: 1) — always required;
  operators must supply at least one parent artifact ID.

**Required slis fields**:
- `completeness`, `timeliness`, `traceability`, `traceability_integrity` —
  all four are required in every artifact.

---

## CLI Usage

```bash
# BE-only evaluation (must supply --parent-id for schema-valid artifact)
python scripts/slo_control.py \
    --be-input outputs/be/normalized_run_result.json \
    --parent-id DEC-001 \
    --output-dir outputs/slo/

# Full BE + BF + BG evaluation with lineage registry
python scripts/slo_control.py \
    --be-input outputs/be/nrr_run1.json \
    --be-input outputs/be/nrr_run2.json \
    --bf-input outputs/bf/cross_run_intelligence_decision.json \
    --bg-input outputs/bg/working_paper_evidence_pack.json \
    --lineage-dir outputs/lineage/ \
    --parent-id DEC-001 \
    --parent-id SYN-001 \
    --output-dir outputs/slo/
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `--be-input PATH` | BE normalized_run_result artifact (repeatable) |
| `--bf-input PATH` | BF cross_run_intelligence_decision artifact (optional) |
| `--bg-input PATH` | BG working_paper_evidence_pack artifact (optional) |
| `--lineage-dir PATH` | Directory of lineage JSON artifacts to validate integrity against |
| `--parent-id VALUE` | Parent artifact ID for lineage provenance (repeatable, required for schema-valid output) |
| `--output-dir PATH` | Output directory (default: current working directory) |

**`--lineage-dir` behaviour:**
- All `*.json` files in the directory are loaded into the lineage registry.
- If the directory does not exist, is empty, or any file fails to parse, the
  command exits with code 2.  This is intentional: a missing or broken
  registry must never silently pretend lineage is healthy.

**CLI summary output:**

The operator summary printed to stdout always includes lineage health fields
so that a single log line is sufficient to determine whether a run is safe to
trust:

```
slo_status:                  healthy
allowed_to_proceed:          True
completeness_sli:            1.0
timeliness_sli:              1.0
traceability_sli:            0.9166666666666666
traceability_integrity_sli:  1.0
error_budget:                remaining=0.9791666666666666  burn_rate=0.020833333333333426
lineage_valid:               True
parent_artifact_ids:         ['DEC-001', 'SYN-001']
lineage_errors:              []
violations:                  []
```

- `lineage_valid` and `parent_artifact_ids` are always emitted; if absent from
  the artifact, the summary prints an explicit `[absent]` notice rather than
  silently skipping the field.
- `traceability_integrity_sli` is always emitted (not conditional).

**stderr vs stdout:**

- Normal summary fields go to **stdout**.
- `Schema validation errors` (with count and details) go to **stderr**.
- `lineage_errors` (when non-empty, with count and details) go to **stderr**.
- This separation allows CI logs and operators to distinguish normal status
  output from validation failures without parsing mixed streams.

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0    | healthy — all SLIs ≥ 0.95 and burn\_rate ≤ 0.2 |
| 1    | degraded — at least one SLI in the 0.85–0.95 band |
| 2    | violated — at least one SLI < 0.85 or burn\_rate > 0.2 |

---

## SLO Classification Thresholds

The following thresholds are authoritative and enforced as named constants
(`HEALTHY_THRESHOLD`, `DEGRADED_THRESHOLD`) in
`spectrum_systems/modules/runtime/slo_control.py`:

| Condition                                     | Classification |
|-----------------------------------------------|----------------|
| SLI value ≥ 0.95 (`HEALTHY_THRESHOLD`)        | healthy        |
| SLI value ≥ 0.85 (`DEGRADED_THRESHOLD`) and < 0.95 | degraded  |
| SLI value < 0.85 (`DEGRADED_THRESHOLD`)       | violated       |

**Overall status rule:** the overall SLO status is the worst individual SLI
state.

- If **any** SLI is violated → overall status is `violated`
- Else if **any** SLI is degraded → overall status is `degraded`
- Else → overall status is `healthy`

Exit codes map directly from the overall status: healthy → 0, degraded → 1,
violated → 2.  There are no fallback or default paths that mask
classification errors.
