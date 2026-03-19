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

**Governed trust-policy bands:**

| Condition                  | TI value | Constant             |
|----------------------------|----------|----------------------|
| strict + valid lineage     | 1.0      | `_TI_STRICT_VALID`   |
| strict + invalid lineage   | 0.0      | `_TI_STRICT_INVALID` |
| degraded / no registry     | 0.5      | `_TI_DEGRADED`       |

The three values are intentionally distinct so any downstream consumer can
machine-distinguish all three states without inspecting
`lineage_validation_mode`.

**When a registry is provided:** The full `validate_full_registry` check is
applied.  Any orphan artifact, missing parent type, or broken chain sets the
SLI to 0.0 (`_TI_STRICT_INVALID`), which drives `slo_status` to `violated`
and blocks `allowed_to_proceed`.

**When no registry is provided:** The system operates in **degraded
validation mode**: `traceability_integrity` is set to `_TI_DEGRADED` (0.5)
— not 1.0.  This value is deliberately below `HEALTHY_THRESHOLD` (0.95) so
that the no-registry path is machine-distinguishable from confirmed-healthy
strict-mode lineage.  Operators who require lineage verification must supply
a registry via `--lineage-dir`.

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

## SLO and Lineage Integration

The SLO Control Layer uses the Artifact Lineage System (Prompt BS) as a
gating signal:

- `traceability_integrity` SLI is computed by running `validate_full_registry`
  over the lineage registry supplied via `--lineage-dir`.  A registry error
  sets the SLI to `_TI_STRICT_INVALID` (0.0), which drives `slo_status` to
  `violated` and sets `allowed_to_proceed` to `false`.
- `lineage_valid` is a schema-required field in every `slo_evaluation`
  artifact.  It reflects the outcome of lineage validation and defaults to
  `false` when lineage has not been assessed.
- When no lineage registry is provided the system operates in **degraded
  validation mode**: `traceability_integrity` is set to `_TI_DEGRADED` (0.5)
  — not 1.0 — and `lineage_valid` remains `false`.  This value is
  deliberately below `HEALTHY_THRESHOLD` so that unvalidated runs are
  machine-distinguishable from validated-healthy strict-mode runs.  Operators
  who require lineage verification must supply a registry via `--lineage-dir`.

**Degraded validation mode is a governed trust policy, not a side effect.**
The 0.5 value for the no-registry path is intentional and locked.  It
reflects the system's deliberate posture: unknown lineage is neither healthy
(1.0) nor failed (0.0); it is an unassessed, partially-trusted state.

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
  the SLI is set to `_TI_DEGRADED` (0.5) — not 1.0 — to signal that lineage
  has not been verified.  Operators who require confirmed-healthy lineage must
  supply a registry via `--lineage-dir`.

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

---

## TI Enforcement Layer (Prompt 11B)

### Why TI Needed Enforcement

The SLO Control Layer (BR) computes `traceability_integrity_sli` as one of
four SLIs and records it in the `slo_evaluation` artifact.  Before Prompt 11B,
TI was a **passive metric**: it was observed, recorded, and could trigger an
SLO violation, but downstream callers were not required to respect it at the
stage level.

The TI Enforcement Layer turns TI into an **active runtime control** via a
policy-driven decision that determines whether a pipeline step may:

- `allow` — proceed normally
- `allow_with_warning` — proceed with caution; operator attention recommended
- `fail` — stop; do not pass this artifact to the next stage

The enforcement decision is recorded as a governed machine-readable
`slo_enforcement_decision` artifact (schema:
`contracts/schemas/slo_enforcement_decision.schema.json`).

---

### Module Location

```
spectrum_systems/modules/runtime/slo_enforcement.py
```

---

### Supported Policy Profiles

| Profile          | TI 1.0 | TI 0.5            | TI 0.0 |
|------------------|--------|-------------------|--------|
| `permissive`     | allow  | allow_with_warning | fail  |
| `decision_grade` | allow  | fail              | fail   |
| `exploratory`    | allow  | allow_with_warning | fail  |

The **default policy** is `permissive`.

Per-stage defaults (applied when no explicit `--policy` is provided):

| Stage       | Default policy   |
|-------------|-----------------|
| `observe`   | `permissive`    |
| `interpret` | `permissive`    |
| `recommend` | `decision_grade`|
| `synthesis` | `decision_grade`|
| `export`    | `decision_grade`|

An explicit `--policy` argument always overrides the stage default.

---

### Decision Meanings

| Status               | Meaning                                                      |
|----------------------|--------------------------------------------------------------|
| `allow`              | TI is 1.0 (strict + valid lineage). Proceed normally.        |
| `allow_with_warning` | TI is 0.5 (degraded / no registry). Proceed with caution.   |
| `fail`               | TI is 0.0 (strict + invalid lineage) or inputs are invalid. Stop. |

---

### Reason Codes

| Code                              | Meaning                                                    |
|-----------------------------------|------------------------------------------------------------|
| `strict_valid_lineage`            | TI 1.0 — strict mode, all lineage checks passed            |
| `strict_invalid_lineage`          | TI 0.0 — strict mode, lineage registry has errors          |
| `degraded_no_registry`            | TI 0.5 — no lineage registry supplied                      |
| `missing_traceability_integrity`  | TI field absent from input artifact                        |
| `malformed_traceability_integrity`| TI value is not a recognised governed band (1.0/0.5/0.0)  |
| `missing_lineage_mode`            | `lineage_validation_mode` absent from input artifact       |
| `malformed_lineage_mode`          | `lineage_validation_mode` is not `strict` or `degraded`    |
| `inconsistent_lineage_state`      | Internally contradictory combination of lineage fields     |

---

### Inconsistency Detection

The enforcement layer detects contradictory lineage state combinations and
produces `fail` with reason code `inconsistent_lineage_state`:

| Contradiction                                        | Example                                     |
|------------------------------------------------------|---------------------------------------------|
| TI 1.0 with `lineage_validation_mode == "degraded"`  | strict-valid lineage requires strict mode   |
| TI 0.5 with `lineage_defaulted == False`             | degraded TI implies defaulted should be True|
| TI 0.0 with `lineage_valid == True`                  | invalid lineage cannot also be valid        |
| strict mode + TI 1.0/0.0 with `lineage_valid` absent | strict mode must record lineage_valid       |

These are never silently normalised away.

---

### Exit Codes (CLI)

| Code | Meaning                                         |
|------|-------------------------------------------------|
| 0    | `allow` — proceed                               |
| 1    | `allow_with_warning` — proceed with caution     |
| 2    | `fail` — stop                                   |
| 3    | malformed input / schema error / execution error|

---

### Degraded-Mode Handling

When no lineage registry is supplied, `traceability_integrity_sli` is 0.5
(`degraded`).  The enforcement layer treats this as a real operational state,
not a soft footnote:

- Under `permissive` or `exploratory` policy: `allow_with_warning` with
  `recommended_action: proceed_with_caution`.
- Under `decision_grade` policy: `fail` with
  `recommended_action: halt_degraded_lineage`.

Operators who need to pass `decision_grade` stages must supply a lineage
registry so that TI can be validated to 1.0.

---

### Backward Compatibility

The TI Enforcement Layer is a **new module** (`slo_enforcement.py`) that
complements, but does not modify, `slo_control.py`.  Existing callers of
`run_slo_control` are unaffected.

The enforcement layer accepts `slo_evaluation` artifacts produced by
`run_slo_control` as-is, reading `traceability_integrity` from the nested
`slo_evaluation.slis.traceability_integrity` path if the top-level key is
absent.

No existing schemas, functions, or tests were modified.

---

### CLI Usage

```bash
# Default (permissive) policy
python scripts/run_slo_enforcement.py outputs/slo_evaluation.json

# Explicit decision_grade policy
python scripts/run_slo_enforcement.py outputs/slo_evaluation.json --policy decision_grade

# Stage-driven policy (synthesis → decision_grade by default)
python scripts/run_slo_enforcement.py outputs/slo_evaluation.json --stage synthesis

# Custom output path
python scripts/run_slo_enforcement.py outputs/slo_evaluation.json --output /tmp/decision.json
```

The decision artifact is written to `outputs/slo_enforcement_decision.json`
by default, and also returned in the Python API result dict under the key
`enforcement_decision`.

---

### Decision Artifact Schema

Schema: `contracts/schemas/slo_enforcement_decision.schema.json`

Key fields:

| Field                        | Type          | Description                                   |
|------------------------------|---------------|-----------------------------------------------|
| `artifact_id`                | string        | ID of the evaluated artifact                  |
| `enforcement_policy`         | enum          | Policy profile applied                        |
| `enforcement_scope`          | enum (opt.)   | Stage, if provided                            |
| `decision_status`            | enum          | allow / allow_with_warning / fail             |
| `decision_reason_code`       | enum          | Machine-readable reason                       |
| `traceability_integrity_sli` | number\|null  | TI value evaluated                            |
| `lineage_validation_mode`    | string        | strict or degraded                            |
| `lineage_defaulted`          | boolean       | True when lineage used fail-safe defaults     |
| `lineage_valid`              | boolean\|null | Lineage validity result                       |
| `recommended_action`         | enum          | Machine-readable recommended next step        |
| `warnings`                   | array         | Warning messages                              |
| `errors`                     | array         | Error messages                                |
| `evaluated_at`               | date-time     | When the decision was generated               |
| `contract_version`           | string        | Schema version                                |
| `decision_id`                | string        | Unique decision identifier (ENF-...)          |

---

## Policy Registry + Stage Binding (BN.2)

### Why the Registry Exists

Before BN.2, policy names and stage-to-policy defaults were embedded directly
in `slo_enforcement.py`.  This created policy sprawl risk: future modules
might fork policy semantics or stage binding behaviour, leading to divergent
enforcement across the system.

BN.2 centralises all policy definitions and stage bindings into a governed,
machine-readable registry so that:

- Policy selection is auditable — one source of truth
- Stage bindings are explicit and schema-validated
- Runtime enforcement consumes the registry rather than inline defaults
- New policies or stages can be added in one place without logic drift

### Module Location

```
spectrum_systems/modules/runtime/policy_registry.py
```

The registry module owns policy definitions, stage bindings, validation, and
override resolution.  It does not depend on CLI behaviour.

### Registry Files

| File                                              | Role                           |
|---------------------------------------------------|--------------------------------|
| `data/policy/slo_policy_registry.json`           | Canonical registry data file   |
| `contracts/schemas/slo_policy_registry.schema.json` | JSON Schema 2020-12 for registry |

### Policy Profiles

| Profile         | TI 1.0    | TI 0.5             | TI 0.0 | Warnings | Degraded OK |
|-----------------|-----------|---------------------|--------|----------|-------------|
| `permissive`    | allow     | allow_with_warning  | fail   | yes      | yes         |
| `decision_grade`| allow     | fail                | fail   | no       | no          |
| `exploratory`   | allow     | allow_with_warning  | fail   | yes      | yes         |

Each profile also specifies default `recommended_actions` per decision status.

### Stage Bindings

| Stage       | Default Policy   |
|-------------|-----------------|
| `observe`   | `permissive`    |
| `interpret` | `permissive`    |
| `recommend` | `decision_grade`|
| `synthesis` | `decision_grade`|
| `export`    | `decision_grade`|

### Override Resolution Order

Resolution is implemented in `resolve_effective_slo_policy()` and follows
this strict precedence:

1. **Explicit caller-provided policy** — if `--policy` is given and is a known
   policy name, use it (regardless of stage)
2. **Stage-bound default** — if `--stage` is given and has a registry binding,
   use the bound policy
3. **System default** — `permissive` (registry `default_policy` field)

Unknown policy names and unknown stage names raise governed
`UnknownPolicyError` / `UnknownStageError` exceptions, never uncaught errors.

### Diagnostics Usage

The policy registry exposes helpers for observability:

```python
from spectrum_systems.modules.runtime.policy_registry import (
    list_slo_policies,
    list_slo_stages,
    list_stage_bindings,
    describe_effective_policy,
)

# List all registered policy profile names
policies = list_slo_policies()          # ['decision_grade', 'exploratory', 'permissive']

# List all registered stage names
stages = list_slo_stages()              # ['export', 'interpret', 'observe', 'recommend', 'synthesis']

# Get the full stage → policy bindings map
bindings = list_stage_bindings()

# Describe effective policy resolution (useful for debugging)
info = describe_effective_policy(requested_policy=None, stage="synthesis")
# info["effective_policy"]   == "decision_grade"
# info["resolution_source"]  == "stage_binding"
```

These are also surfaced in the CLI (see below).

### CLI Changes (BN.2)

Three new diagnostics flags were added to `scripts/run_slo_enforcement.py`:

```bash
# List all available policy profile names
python scripts/run_slo_enforcement.py --list-policies

# List all stages and their default policy bindings
python scripts/run_slo_enforcement.py --list-stages

# Show effective policy resolution for given inputs
python scripts/run_slo_enforcement.py --show-effective-policy
python scripts/run_slo_enforcement.py --show-effective-policy --policy decision_grade
python scripts/run_slo_enforcement.py --show-effective-policy --stage synthesis
```

All three flags exit with code 0 and write to stdout.  They do not require an
artifact path argument.  The existing enforcement execution path is unchanged.

### Backward Compatibility Notes

- All existing CLI options (`--policy`, `--stage`, `--output`) work unchanged
- All constants previously exported from `slo_enforcement.py` remain importable
  from the same location (they are now sourced from `policy_registry.py`)
- `resolve_enforcement_policy()` in `slo_enforcement.py` still works; it now
  delegates to `resolve_effective_slo_policy()` from the registry, with an
  inline fallback for registry unavailability
- `evaluate_traceability_policy()` now uses registry profile data for the
  TI-band decision mapping instead of hardcoded if/elif logic
- All 2541 pre-BN.2 tests continue to pass

---

## Stage-Aware Decision Gating Engine (BN.3)

### Why Gating Exists

BN.1 created enforcement decisions.  BN.2 centralised policy and stage
binding.  But neither step was sufficient to *stop* untrustworthy artifacts
from entering decision-bearing stages.  Both layers described risk — they did
not prevent bad execution.

BN.3 closes that gap.  The gating engine consumes an
``slo_enforcement_decision`` artifact and determines whether the downstream
pipeline step may proceed, must halt, or may proceed only in an explicitly
permitted warning state.  This makes the control layer binding, not advisory.

### Enforcement vs. Gating

| Layer       | Artifact                  | Question answered                                      |
|-------------|---------------------------|--------------------------------------------------------|
| Enforcement | `slo_enforcement_decision`| Is this artifact trustworthy under a named policy?     |
| Gating      | `slo_gating_decision`     | May this pipeline step continue given the stage posture? |

Enforcement evaluates TI against a policy profile.
Gating evaluates an enforcement decision against a stage's governed posture.

The outputs are distinct artifacts with distinct schemas.

### Stage-Aware Continuation Rules

Pipeline stages differ in what a ``allow_with_warning`` enforcement decision
means for execution.  The gating engine applies a governed posture per stage:

| Stage       | Warnings allowed | Decision-bearing | Default behaviour on warning |
|-------------|-----------------|------------------|------------------------------|
| `observe`   | Yes             | No               | `proceed_with_warning`       |
| `interpret` | Yes             | No               | `proceed_with_warning`       |
| `recommend` | No              | Yes              | `halt`                       |
| `synthesis` | No              | Yes              | `halt`                       |
| `export`    | No              | Yes              | `halt`                       |

This posture is centralised in ``data/policy/slo_gating_rules.json`` and
validated against ``contracts/schemas/slo_gating_rules.schema.json``.  The
engine falls back to fail-closed posture if the config file is unavailable.

### Gating Outcomes

Gating outcomes are **distinct** from enforcement decision statuses.

| Outcome               | Meaning                                                          |
|-----------------------|------------------------------------------------------------------|
| `proceed`             | Enforcement allowed; stage may continue                          |
| `proceed_with_warning`| Enforcement warned; stage posture permits continuation           |
| `halt`                | Enforcement failed, or warning at a decision-bearing stage       |

### Gating Reason Codes

| Reason code                          | Trigger condition                                          |
|--------------------------------------|------------------------------------------------------------|
| `enforcement_allow`                  | Upstream decision was ``allow``                            |
| `enforcement_warning_allowed`        | Warning; stage posture permits continuation                |
| `enforcement_warning_blocked_by_stage` | Warning; stage posture requires halt                     |
| `enforcement_fail`                   | Upstream decision was ``fail``                             |
| `malformed_enforcement_decision`     | Payload could not be parsed or required fields missing     |
| `missing_enforcement_status`         | `decision_status` field absent from enforcement decision   |
| `unknown_enforcement_status`         | `decision_status` has an unrecognised value                |
| `inconsistent_enforcement_payload`   | Internally contradictory fields detected                   |

### Recommended Actions

Recommended actions are deterministic from gating context.

| Action                       | When emitted                                                        |
|------------------------------|---------------------------------------------------------------------|
| `proceed`                    | Gating outcome is `proceed`                                         |
| `proceed_with_monitoring`    | Gating outcome is `proceed_with_warning`                            |
| `halt_and_review`            | Warning/fail; no specific lineage fault identified                  |
| `halt_and_repair_lineage`    | `lineage_valid` is False; lineage needs correction                  |
| `halt_and_rerun_with_registry`| Degraded lineage mode or `lineage_defaulted` is True               |
| `halt_and_escalate`          | Malformed, inconsistent, or unrecognised enforcement payload        |

### CLI Usage

```bash
# Gate an enforcement decision using the stage embedded in the artifact
python scripts/run_slo_gating.py outputs/slo_enforcement_decision.json

# Override the stage
python scripts/run_slo_gating.py outputs/slo_enforcement_decision.json --stage synthesis

# Non-decision-bearing stage (warnings allowed)
python scripts/run_slo_gating.py outputs/slo_enforcement_decision.json --stage observe

# Write gating decision to a custom path
python scripts/run_slo_gating.py outputs/slo_enforcement_decision.json \
    --output /tmp/gating_decision.json

# Show all stage postures (no artifact required)
python scripts/run_slo_gating.py --show-stage-posture

# Show posture for a specific stage
python scripts/run_slo_gating.py --show-stage-posture --stage synthesis
```

The gating decision artifact is written to ``outputs/slo_gating_decision.json``
by default.  The Python API returns it under the key ``gating_decision``.

**Exit codes:**

| Code | Meaning                                              |
|------|------------------------------------------------------|
| 0    | proceed                                              |
| 1    | proceed_with_warning                                 |
| 2    | halt                                                 |
| 3    | malformed input / schema / execution error           |

Exit code 2 (halt) and exit code 3 (execution error) are deliberately distinct
so operators can distinguish a governed gate stop from an infrastructure fault.

### End-to-End Control Chain

```
run_slo_control   → outputs/slo_evaluation.json          (SLI evaluation)
run_slo_enforcement → outputs/slo_enforcement_decision.json  (policy enforcement)
run_slo_gating    → outputs/slo_gating_decision.json     (stage-aware binding gate)
```

Each step produces a governed machine-readable artifact.  Downstream stages
consume the gating decision's ``gating_outcome`` field: ``proceed`` continues,
``halt`` stops.

The Python convenience path:

```python
from spectrum_systems.modules.runtime.slo_enforcement import run_slo_enforcement
from spectrum_systems.modules.runtime.decision_gating import run_slo_gating

# Step 1 — evaluate artifact against enforcement policy
enforcement_result = run_slo_enforcement(raw_artifact, policy="permissive", stage="synthesis")

# Step 2 — gate based on stage posture (run_slo_gating accepts the wrapper dict)
gating_result = run_slo_gating(enforcement_result, stage="synthesis")

outcome = gating_result["gating_outcome"]   # "proceed" | "proceed_with_warning" | "halt"
artifact = gating_result["gating_decision"] # full governed gating artifact
```

### Gating Decision Artifact Schema

Schema: ``contracts/schemas/slo_gating_decision.schema.json``

Key fields:

| Field                         | Type           | Description                                      |
|-------------------------------|----------------|--------------------------------------------------|
| `gating_decision_id`          | string         | Unique ID for this gating decision (GATE-...)    |
| `source_decision_id`          | string         | ID of the upstream enforcement decision          |
| `artifact_id`                 | string         | ID of the evaluated artifact                     |
| `stage`                       | string         | Pipeline stage at which gating was evaluated     |
| `enforcement_policy`          | string         | Policy profile that produced the enforcement decision |
| `enforcement_decision_status` | string         | allow / allow_with_warning / fail                |
| `gating_outcome`              | enum           | proceed / proceed_with_warning / halt            |
| `gating_reason_code`          | enum           | Machine-readable reason for the outcome          |
| `traceability_integrity_sli`  | number\|null   | TI value from the enforcement decision           |
| `lineage_validation_mode`     | string         | strict or degraded                               |
| `lineage_defaulted`           | boolean\|null  | True when lineage used fail-safe defaults        |
| `lineage_valid`               | boolean\|null  | Lineage validity result                          |
| `recommended_action`          | enum           | Deterministic recommended operator action       |
| `warnings`                    | array          | Warning messages                                 |
| `errors`                      | array          | Error messages                                   |
| `evaluated_at`                | date-time      | When the gating decision was generated           |
| `contract_version`            | string         | Schema version                                   |

### Module Location

```
spectrum_systems/modules/runtime/decision_gating.py
```

### Governed Config Files

| File                                              | Role                                       |
|---------------------------------------------------|--------------------------------------------|
| `data/policy/slo_gating_rules.json`              | Canonical gating posture per stage         |
| `contracts/schemas/slo_gating_rules.schema.json` | JSON Schema 2020-12 for gating rules       |
| `contracts/schemas/slo_gating_decision.schema.json` | JSON Schema 2020-12 for gating artifacts |

### Backward Compatibility Notes

- No existing modules, functions, schemas, or exit codes were modified
- `run_slo_control` and `run_slo_enforcement` are unchanged
- The gating engine is additive; existing callers are unaffected
- `run_slo_gating` accepts either a bare enforcement decision dict or the
  ``{enforcement_decision: ...}`` wrapper returned by ``run_slo_enforcement``
- All pre-BN.3 tests continue to pass


---

## Control-Chain Orchestrator (BN.4)

### Purpose

BN.3 proved that gating works, but it was **advisory** — nothing required it
to run.  BN.4 fixes this by introducing a single canonical execution path that
makes enforcement **and** gating non-optional for decision-bearing stages.

BN.4 eliminates the bypass risk identified in BN.3:

> An `allow` enforcement decision alone could be misinterpreted as "safe to
> proceed" even for decision-bearing stages, because gating was never forced.

### Core Non-Negotiable Rule

**Decision-bearing stages (recommend, synthesis, export) CANNOT proceed
unless:**

1. Gating has been executed (not just enforcement), **and**
2. `gating_outcome != halt`.

There is **no shortcut**, no alternate path, and no silent fallback.

### Module Location

```
spectrum_systems/modules/runtime/control_chain.py
```

### Canonical Execution Path

```
evaluation → enforcement → gating → control decision
```

| Input Kind   | Chain Executed                                  |
|--------------|------------------------------------------------|
| `evaluation` | MUST run enforcement, MUST run gating          |
| `enforcement`| MUST run gating                                 |
| `gating`     | Validate and return (audit/replay mode only)   |

### Why Gating is Mandatory

Enforcement evaluates whether an artifact's TI metric satisfies a policy.
It does **not** account for the downstream stage's decision-bearing status.

Gating translates the enforcement result into a stage-aware binding decision.
At decision-bearing stages, even an `allow_with_warning` enforcement result
**halts** the pipeline — degraded lineage must not flow into recommendations
or exports.

Without mandatory gating, operators could:
- Call `run_slo_enforcement` and treat `allow` as "safe to proceed"
- Skip gating entirely for decision stages
- Route artifacts through exploratory-grade validation on decision-grade stages

BN.4 makes this impossible via the single entry point.

### Single Public API

```python
from spectrum_systems.modules.runtime.control_chain import run_control_chain

result = run_control_chain(
    raw_input,          # evaluation, enforcement, or gating artifact
    stage="synthesis",  # optional override
    policy="permissive", # optional policy override (evaluation input only)
    input_kind=None,    # optional kind override (auto-detected if None)
)

cd = result["control_chain_decision"]
if result["continuation_allowed"]:
    print("Continue:", cd["primary_reason_code"])
else:
    print("Blocked:", cd["blocking_layer"], cd["primary_reason_code"])
```

This function is documented as the **REQUIRED entry point** for
decision-grade operation.  Calling lower-level functions directly bypasses
the control chain and violates the governance contract.

### Control-Chain Decision Artifact

Schema: `contracts/schemas/slo_control_chain_decision.schema.json`

Key fields:

| Field                        | Type           | Description                                            |
|------------------------------|----------------|--------------------------------------------------------|
| `control_chain_decision_id`  | string         | Unique ID (CC-...)                                     |
| `artifact_id`                | string         | ID of the evaluated artifact                           |
| `stage`                      | string         | Pipeline stage                                         |
| `input_kind`                 | enum           | evaluation / enforcement / gating                      |
| `enforcement_decision_id`    | string         | ID of the enforcement decision                         |
| `gating_decision_id`         | string         | ID of the gating decision                              |
| `enforcement_policy`         | string         | Policy profile used                                    |
| `enforcement_decision_status`| string         | allow / allow_with_warning / fail                      |
| `gating_outcome`             | string         | proceed / proceed_with_warning / halt                  |
| `continuation_allowed`       | boolean        | True = stage may continue                              |
| `blocking_layer`             | enum           | none / enforcement / gating / orchestration            |
| `primary_reason_code`        | enum           | Deterministic reason code                              |
| `traceability_integrity_sli` | number\|null   | TI value                                               |
| `warnings`                   | array          | Accumulated warnings                                   |
| `errors`                     | array          | Accumulated errors                                     |
| `recommended_action`         | enum           | Deterministic recommended action                       |
| `schema_version`             | string         | Schema version                                         |
| `stage_source`               | enum           | original / override (optional, BN.4 I.3)               |

### Reason Codes

| Code                                        | Meaning                                              |
|---------------------------------------------|------------------------------------------------------|
| `control_chain_continue`                    | Full chain passed; continue                          |
| `control_chain_continue_with_warning`       | Chain passed with warnings (proceed_with_warning)    |
| `control_chain_blocked_by_gating`           | Gating outcome was halt                              |
| `control_chain_blocked_by_missing_gating`   | Decision stage reached without gating                |
| `control_chain_blocked_by_malformed_input`  | Input could not be parsed                            |
| `control_chain_blocked_by_inconsistent_state` | Internally contradictory state                     |

### Blocking Layers

| Layer            | When assigned                                       |
|------------------|-----------------------------------------------------|
| `none`           | Continuation is allowed                             |
| `enforcement`    | Reserved; enforcement alone does not block for BN.4 |
| `gating`         | Gating outcome was halt                             |
| `orchestration`  | Gating was skipped for a decision-bearing stage     |

### Recommended Actions

| Action                       | Triggered by                                        |
|------------------------------|-----------------------------------------------------|
| `continue`                   | control_chain_continue                              |
| `continue_with_monitoring`   | control_chain_continue_with_warning                 |
| `stop_and_review`            | control_chain_blocked_by_gating (fail)              |
| `stop_and_repair_lineage`    | blocked by gating with warning enforcement status   |
| `stop_and_rerun_with_registry` | (reserved for degraded lineage cases)             |
| `stop_and_escalate`          | missing gating / inconsistent state                 |

### CLI Usage

```
python scripts/run_slo_control_chain.py <artifact.json> \
    [--stage STAGE] [--policy POLICY] [--input-kind KIND] [--output PATH]
```

**Examples:**

```bash
# Gate an SLO evaluation artifact at synthesis (decision-bearing)
python scripts/run_slo_control_chain.py outputs/slo_evaluation.json \
    --stage synthesis

# Gate an enforcement decision artifact
python scripts/run_slo_control_chain.py outputs/slo_enforcement_decision.json

# Audit mode: validate a gating decision artifact
python scripts/run_slo_control_chain.py outputs/slo_gating_decision.json \
    --input-kind gating

# Override policy for an evaluation artifact
python scripts/run_slo_control_chain.py outputs/slo_evaluation.json \
    --stage recommend --policy decision_grade

# Write output to a custom path
python scripts/run_slo_control_chain.py outputs/slo_evaluation.json \
    --stage synthesis --output /tmp/cc_decision.json
```

**Exit codes:**

| Code | Meaning                                            |
|------|----------------------------------------------------|
| 0    | continue                                           |
| 1    | continue_with_warning                              |
| 2    | blocked (halt)                                     |
| 3    | execution / malformed error                        |

Exit code 2 (blocked) NEVER overlaps with exit code 3 (error).  A halt always
returns 2 regardless of schema errors.

### BN.3 Bug Fixes Applied in BN.4

**I.1 — Exit code precedence (run_slo_gating.py)**

Previously, schema errors caused `_outcome_exit_code` to return 3 (error) even
when the gating outcome was `halt`.  Fixed so that `halt` always returns 2,
and schema errors only escalate to 3 on non-halt outcomes.

**I.2 — Gating config fallback visibility (decision_gating.py)**

When `data/policy/slo_gating_rules.json` is unavailable, the built-in fallback
postures are now used **and** a warning is included in the gating artifact:

```
"Gating rules config could not be loaded; built-in fallback postures are in use."
```

**I.3 — stage_source field (optional)**

When stage is overridden by the caller, the control-chain artifact records
`"stage_source": "override"`.  When taken from the artifact itself, it records
`"stage_source": "original"`.  This field is optional in the schema.

### Canonical End-to-End Flow (Updated for BN.4)

```
run_slo_control        → outputs/slo_evaluation.json
                                       ↓
run_slo_enforcement    → outputs/slo_enforcement_decision.json
                                       ↓
run_slo_gating         → outputs/slo_gating_decision.json
                                       ↓
run_slo_control_chain  → outputs/slo_control_chain_decision.json  ← REQUIRED for decision stages
```

For decision-grade operation, **always** use `run_slo_control_chain.py` (or
`run_control_chain(...)` in Python).  The earlier scripts are lower-level
tools that do not enforce mandatory gating.

### Backward Compatibility Notes

- All BN.1–BN.3 modules, schemas, exit codes, and artifacts are unchanged.
- `run_slo_control`, `run_slo_enforcement`, and `run_slo_gating` remain
  available for direct use in non-decision-bearing or testing contexts.
- The control-chain module is additive; existing callers are unaffected.
- `run_control_chain` accepts BN.1/BN.2/BN.3 artifacts directly.

### Follow-On Recommendations

1. Integrate `run_control_chain` into pipeline stage entry points to enforce
   the control chain at the framework level (not just per-invocation).
2. Add a governance check that warns operators when BN.1–BN.3 scripts are
   used directly for decision-grade stages in production workflows.
3. Consider adding a `dry_run` mode to `run_control_chain` that runs the
   full chain but does not write output artifacts.
