# Narrow Real-Engine Integration Report
## 2026-03-18

**Report type:** Operational Evidence  
**Engine mode introduced:** `decision_real`  
**Execution mode:** `deterministic_pattern`  
**Prompt type:** `BUILD` (single narrow pass integration)

---

## What Changed

A narrow real-engine execution path was added to the operationalization
pipeline for the **decision extraction** pass only.

### New files

| File | Purpose |
|------|---------|
| `spectrum_systems/modules/engines/__init__.py` | Package entry point |
| `spectrum_systems/modules/engines/decision_extraction_adapter.py` | `DecisionExtractionAdapter` — pattern-based real engine |

### Modified files

| File | Change |
|------|--------|
| `scripts/run_operationalization.py` | Added `--engine-mode stub\|decision_real` CLI flag; updated `stage_an_ap`, `stage_ar`, `stage_ao` to accept engine mode; creates separate regression baseline in `decision_real` mode |
| `scripts/run_eval.py` | Added `--engine-mode stub\|decision_real` CLI flag to `_build_runner` and `main()` |

---

## Which Pass Now Uses a Real Engine

**Pass type:** `decision_extraction`  
**Optional co-pass:** `transcript_extraction` (action items)  
**Execution mode label:** `deterministic_pattern`

The `DecisionExtractionAdapter` uses regular-expression pattern matching to
identify decision-like sentences in meeting transcripts.  Patterns match
explicit decision markers (`"Decision:"`, `"we will adopt"`, `"we will
request"`, `"is adopted"`, `"interim … threshold"`, etc.) and status is
inferred from phrasing (`"deferred"`, `"interim"`, `"agreed"`).

**There is no live language model in this path.**  This is the smallest honest
step from plumbing-only (stub) evidence to real-reasoning evidence: the system
processes actual transcript text and produces non-empty structured output when
decisions are present.

---

## Which Passes Remain Stubbed

| Pass type | Status |
|-----------|--------|
| `gap_detection` | Stubbed — empty outputs |
| `contradiction_detection` | Stubbed — empty outputs |
| `synthesis` | Stubbed — empty outputs |

Gap, contradiction, and synthesis passes remain unchanged.  Scores for those
pass types remain zero or vacuously passing.

---

## CLI Modes Available

```bash
# stub mode (default — safe, deterministic plumbing)
python scripts/run_operationalization.py
python scripts/run_operationalization.py --engine-mode stub

# narrow real-engine mode
python scripts/run_operationalization.py --engine-mode decision_real

# eval CLI also supports the flag
python scripts/run_eval.py --all --engine-mode decision_real
```

The default is always `stub`.  `decision_real` must be explicitly requested.

---

## Cases Run in Real-Engine Mode

Two golden cases were run in `decision_real` mode:

| Case | Domain | Difficulty |
|------|--------|-----------|
| `case_001` | 7ghz | easy |
| `case_002` | 5g_sharing | medium |

---

## Whether Outputs Became Non-Empty

Yes.  In `decision_real` mode, the `decision_extraction` pass returns non-empty
`decisions` lists for both cases.

**Case 001 extracted decisions:**
- `[agreed]` We will adopt the -114 dBm/MHz interference threshold as proposed,
  and we will request DOD to submit a formal technical justification for the
  15 MHz guard band request by December 15th.
- `[proposed]` Let's schedule that working session for the week of December 9th.

**Case 002 extracted decisions:**
- `[deferred]` We cannot resolve this today without additional technical data.
- `[interim]` We will adopt -96 dBm as the interim coordination trigger
  threshold, pending DOD validation.
- `[deferred]` On protection zones, there is no agreement today.

---

## Resulting Structural / Semantic / Grounding Behavior

| Case | Mode | Structural F1 | Semantic F1 | Grounding |
|------|------|--------------|-------------|-----------|
| case_001 | stub | 0.000 | 0.000 | 1.000 |
| case_001 | decision_real | 0.000 | **0.333** | 1.000 |
| case_002 | stub | 0.000 | 0.000 | 1.000 |
| case_002 | decision_real | 0.000 | **0.225** | 1.000 |

**Semantic scores are now non-zero** in `decision_real` mode.  Structural
scores remain zero because the exact text of extracted decisions does not
match the golden expectations (phrasing differs).  Grounding remains 1.0
in both modes because no synthesis sections are produced (nothing to
misground).

**Overall pass/fail remains FAIL** for both cases because:
1. Structural score is still 0.0 (eval_runner requires `structural_score > 0.0` for PASS)
2. Some expected decisions are still missing (recall is partial)

---

## New Artifact Counts (after decision_real run)

| Directory | New artifacts | Purpose |
|-----------|--------------|---------|
| `data/observability/` | 2 new records | Real-engine observability tied to decision extraction |
| `data/regression_baselines/decision-real-2026-03-18/` | 1 new baseline | Separate regression baseline for narrow real-engine mode |
| `data/error_classifications/` | 2 new records | AU classification of real-engine eval results |
| `data/error_clusters/` | 7 new clusters | AV clustering of classification records |
| `data/validated_clusters/` | 5 new validated clusters | AW0 validation results |
| `data/remediation_plans/` | 5 new plans | AW1 remediation mapping |
| `data/simulation_results/` | 20 new results | AW2 simulation of plans |
| `data/human_feedback/` | 1 new record | AO feedback on case_001 real-engine artifact |

---

## AP Observability: Real-Engine Records

Two `ObservabilityRecord` instances were written for the `decision_real` run.
Both are tied to the real decision-extraction path (`engine_mode: decision_real`
is embedded in the eval result).  These records carry non-zero semantic scores
which flow into the AU/AV/AW0 classification pipeline.

---

## AW2 Results vs Stub Mode

AW2 results (fix simulation) did not change materially between stub and
`decision_real` mode.  The simulation pipeline runs against all accumulated
`RemediationPlan` records regardless of mode.  The new `decision_real` run
added 5 new remediation plans (one per validated cluster in that run's AV/AW0
outputs), which generated 5 additional simulation results.

The simulation promotion recommendations did not change: all simulated plans
received `status=passed, rec=promote`.

---

## Regression Baseline

A separate baseline was created:

```
data/regression_baselines/decision-real-2026-03-18/
  metadata.json          — engine=decision_real:deterministic_pattern
  eval_results.json      — case_001 sem=0.333, case_002 sem=0.225
  observability_records.json
```

The existing stub baseline `operationalization-2026-03-18` was not modified.

---

## Known Limitations

1. **No live model.** The `DecisionExtractionAdapter` uses regex patterns, not
   an LLM.  Extraction quality is bounded by pattern coverage.
2. **Recall is partial.** The adapter matched 2/4 expected decisions for
   case_001 and 1/2 for case_002 (semantic matching).  Some decisions require
   multi-sentence context or implicit language not captured by the current
   patterns.
3. **Structural score is zero.** The exact text of extracted decisions never
   matches the golden expectations verbatim, so the structural F1 stays at 0.
   Semantic F1 is the meaningful measure for this path.
4. **Gap and contradiction passes remain stubbed.** Only decision extraction
   (and optionally action items) uses the real engine.
5. **Grounding is vacuously 1.0.** No synthesis sections are produced; the
   grounding verifier has nothing to verify.
6. **Execution mode must be labelled.** Any downstream consumer must check
   `execution_mode = "deterministic_pattern"` and not assume LLM-quality
   extraction.

---

## Revised Maturity Estimate

| Dimension | Before this integration | After this integration |
|-----------|------------------------|------------------------|
| Plumbing (control loop executes) | ✓ Complete | ✓ Complete |
| Real extraction (non-empty decision output) | ✗ None | ✓ Decision + action-items |
| Structural accuracy | ✗ 0.0 | ✗ 0.0 (phrasing mismatch) |
| Semantic accuracy | ✗ 0.0 | ⚠ 0.23–0.33 (partial match) |
| Grounding | Vacuous (1.0) | Vacuous (1.0) — no synthesis |
| Regression baseline | Stub only | Stub + decision-real |
| Human feedback on real artifact | ✗ | ✓ (1 record, action=accept) |

**Overall maturity:** The system has advanced from plumbing-only evidence to
the first real-reasoning evidence tier.  Decision extraction produces non-empty
outputs with non-zero semantic scores.  Full semantic accuracy requires either
improved pattern coverage or a live language model.  This integration is a
governed, auditable, and reversible first step.

---

*Generated: 2026-03-18*  
*Author: operationalization-agent (Copilot)*  
*Scope: narrow real-engine pass — decision extraction only*
