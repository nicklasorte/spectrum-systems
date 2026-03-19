# Adversarial Evaluation Report — 2026-03-18

**Prompt:** AY — Adversarial Test Set + Stress Execution  
**Run date:** 2026-03-18  
**Engine mode:** `decision_real` (forced)  
**Total cases evaluated:** 13  
**Status:** COMPLETE

---

## 1. What Adversarial Cases Were Created

Thirteen adversarial test cases were created in `data/adversarial_cases/`, each
targeting a distinct failure mode in the extraction and evaluation pipeline.

| Case ID  | Adversarial Type                  | Difficulty | Expected Failure Modes                                      |
|----------|-----------------------------------|------------|-------------------------------------------------------------|
| adv_000  | missing_decisions                 | easy       | no_decisions_extracted                                      |
| adv_001  | noisy_transcript                  | medium     | no_decisions_extracted, low_confidence_output               |
| adv_002  | contradictory_decisions           | hard       | inconsistent_grounding, duplicate_decisions, low_confidence |
| adv_003  | ambiguous_language                | hard       | no_decisions_extracted, low_confidence_output               |
| adv_004  | duplicate_decisions               | medium     | duplicate_decisions                                         |
| adv_005  | truncated_transcript              | hard       | no_decisions_extracted, structural_failure                  |
| adv_006  | mixed_topics                      | medium     | low_confidence_output, inconsistent_grounding               |
| adv_007  | sparse_content                    | easy       | no_decisions_extracted, structural_failure                  |
| adv_008  | redundant_repetition              | medium     | duplicate_decisions                                         |
| adv_009  | overconfident_reference_minutes   | hard       | inconsistent_grounding                                      |
| adv_010  | mixed_topics                      | hard       | inconsistent_grounding, duplicate_decisions                 |
| adv_011  | sparse_content                    | hard       | no_decisions_extracted, structural_failure                  |
| adv_012  | overconfident_reference_minutes   | hard       | inconsistent_grounding, low_confidence_output               |

### Case design principles

- No synthetic "perfect" cases.  Every case is designed to expose a
  specific system weakness.
- Realistic formatting issues: audio dropouts, off-topic chatter, one-word
  transcripts, intentionally wrong reference minutes.
- Some cases intentionally break assumptions (e.g., adv_009 and adv_012
  have reference minutes that contradict the transcript).
- Adversarial inputs were not sanitized or softened before pipeline execution.

---

## 2. Key Failure Patterns Observed

### 2.1 Zero-decision extraction dominates

**10 of 13 cases** resulted in zero decisions extracted.  The flag
`no_decisions_extracted` was triggered in:

- All `sparse_content` cases (adv_007, adv_011)
- All `ambiguous_language` cases (adv_003)
- All `truncated_transcript` cases (adv_005)
- All `missing_decisions` cases (adv_000)
- All `noisy_transcript` cases (adv_001)
- All `overconfident_reference_minutes` cases (adv_009, adv_012)
- All `duplicate_decisions` cases with no strong decision signals (adv_004)
- `mixed_topics` cases where the buried decision used indirect phrasing (adv_006)

**Interpretation:** The pattern-matching extraction engine correctly avoids
hallucinating decisions in most adversarial conditions.  However, it also
misses real decisions that use indirect language (adv_006 had a genuine
decision buried under unrelated discussion that the engine failed to capture).

### 2.2 Duplicate/contradictory decisions promoted without validation

**3 cases were promoted** (adv_002, adv_008, adv_010).  All three contain
either contradictory decisions or near-duplicate restatements that the
extraction engine accepted without flagging:

- **adv_002** (`contradictory_decisions`): Multiple conflicting guard band
  values (20/25/30 MHz) were present; the engine extracted decisions without
  detecting the conflict between them.  Promoted despite containing
  contradictory signals.

- **adv_008** (`redundant_repetition`): The same 4 decisions were each
  stated 4-5 times in different phrasings.  The engine extracted some but
  not all repetitions, and the `duplicate_decisions` flag was not triggered
  because the engine de-duplication happened to work on this specific phrasing.
  Promoted without the system flagging the repetition anomaly.

- **adv_010** (`mixed_topics`): 5 participants, 3 bands discussed, only 1
  real decision made.  The engine extracted decisions from the mixed-topic
  preamble that were not actual decisions (false extractions from
  off-topic discussion).  Promoted despite mixed-signal content.

### 2.3 Gating performed correctly on the zero-decision cases

AZ gating correctly **rejected 10 of 13 cases** (77%) for `no_decisions_extracted`.
The fail-closed gating rule works as intended for the most common failure mode.

### 2.4 The `structural_failure` flag did not trigger as broadly as expected

Several cases expected to trigger `structural_failure` (adv_005, adv_007,
adv_011) were correctly flagged with `no_decisions_extracted` instead.  The
engine completed its pass chain without schema errors on all inputs, meaning
the structural pipeline did not break even under adversarial conditions —
it simply produced empty output.

### 2.5 `inconsistent_grounding` and `duplicate_decisions` flags had no hits

Despite being designed for these failure modes (adv_002, adv_004, adv_008,
adv_009, adv_010), the grounding and duplication flags were **never triggered**
in the run.  This reveals two blind spots:

1. **Grounding is not checked against reference minutes** in the current
   pipeline.  The `inconsistent_grounding` flag only triggers when
   `grounding_score < 0.5`, but with empty expected outputs the grounding
   score defaults to vacuous pass.

2. **Duplicate decision detection is shallow.**  The current implementation
   only checks for exact-string duplicates in the extracted list.  Near-
   duplicate decisions phrased differently bypass detection entirely.

---

## 3. Where the System Broke

| Failure | Observed | Impact |
|---------|----------|--------|
| Zero decision extraction on real decisions (adv_006) | Engine missed a genuine decision buried in mixed-topic preamble | False negative — real outcome not captured |
| Contradictory decisions promoted (adv_002) | Engine extracted conflicting guard band values without conflict detection | False positive — invalid outcome promoted |
| Redundant decisions not detected (adv_008) | Paraphrase deduplication is absent | False positive — noisy extraction promoted |
| Grounding not checked against reference minutes | `inconsistent_grounding` never fires | Key adversarial scenario undetected |
| `structural_failure` too narrow | Relies on schema errors, not semantic emptiness | Misses failure mode |

---

## 4. Where Gating Correctly Blocked

AZ gating performed correctly for:

- **All missing/ambiguous/sparse/noisy/truncated cases**: 10 REJECT outcomes
  confirm that the fail-closed gate works when the extraction engine returns
  empty results.

- **The threshold configuration is conservative**: Both `structural_failure`
  and `no_decisions_extracted` trigger REJECT (not just HOLD), which is the
  appropriate severity for these failure modes.

The gate **did not** require human calibration to produce the correct outcome
in 77% of adversarial cases.  This is a meaningful validation of the gating
logic.

---

## 5. Where the System Still Over-Trusts Outputs

Three areas where the system is over-confident despite adversarial inputs:

### 5.1 Contradictory decision sets are not detected

When multiple participants state contradictory positions and then
converge on a final answer, the engine extracts decisions from all
phases of the discussion.  It has no mechanism to identify that earlier
statements were superseded.

**Risk:** Contradictory decisions may be reported as agreed decisions in
output artifacts.

### 5.2 Reference minutes are not cross-validated against transcripts

Cases adv_009 and adv_012 have intentionally wrong reference minutes.
The system makes no use of reference minutes during the extraction or
grounding stage.  An overconfident system that relied on them would
fail; the current system simply ignores them — which is better but
still not ideal (reference minutes could be useful signal when correct).

### 5.3 Decision confidence scoring is binary

A decision is either extracted or not.  There is no confidence score
attached to extracted decisions.  Cases with uncertain, hedged, or
partial decisions (adv_003, adv_006) get either zero extractions or
full extractions with no indication of low confidence.

---

## 6. Recommended Next Fixes

| Priority | Fix | Target |
|----------|-----|--------|
| HIGH | Add contradiction detection pass: flag decisions that conflict with other extracted decisions | `DecisionExtractionAdapter` or new pass |
| HIGH | Add semantic duplicate detection using token overlap or embedding similarity | Decision post-processing step |
| HIGH | Implement grounding against reference minutes when available (as an optional signal) | `GroundingVerifier` |
| MEDIUM | Add decision confidence score (0.0–1.0) to each extracted decision | `DecisionExtractionAdapter` |
| MEDIUM | Strengthen `structural_failure` flag: fire when all pass results return empty output even if schema is valid | Adversarial failure flag logic |
| MEDIUM | Add `inconsistent_grounding` check that compares extracted decisions against reference minutes (when present) | AP adversarial extension |
| LOW | Add test cases that use intentionally misleading reference minutes to validate grounding cross-check once implemented | Adversarial test set expansion |

---

## 7. Cluster Analysis

After the adversarial run, AV clustering produced 7 new clusters from 44
classification records (25 + 13 new adversarial + 6 pre-existing):

| Cluster Signature        | Record Count | Interpretation |
|--------------------------|-------------|----------------|
| EXTRACT.FALSE_EXTRACTION | 23          | Dominant cluster: engine false-extracts decisions |
| GROUND.MISSING_REF       | 6           | Grounding failures due to missing reference |
| SCHEMA.INVALID_OUTPUT    | 4           | Output schema violations |
| EXTRACT.MISSED_DECISION  | 4           | Real decisions not extracted |
| HALLUC.UNSUPPORTED_ASSERTION | 1       | Single hallucination event |
| INPUT.BAD_TRANSCRIPT_QUALITY | 3       | Transcript-quality-driven failures |
| RETRIEVE.IRRELEVANT_MEMORY | 3        | Retrieval failures |

The `EXTRACT.FALSE_EXTRACTION` cluster is the largest and is driven primarily
by the adversarial cases.  This confirms that false extraction (producing
output from poor input) is the most common failure mode under stress.

---

## 8. Summary Statistics

```
total_adversarial_cases  : 13
cases_with_no_decisions  : 10
promote_count            : 3
hold_count               : 0
reject_count             : 10

Top failure modes:
  no_decisions_extracted        10 cases
```

Full machine-readable summary: `outputs/ay_adversarial_summary.json`

---

## 9. Conclusion

The adversarial test suite successfully exposed real weaknesses in the
pipeline:

**The system is conservative (good):** It refuses to produce decisions from
most adversarial inputs, and the AZ gate correctly rejects 77% of adversarial
cases.

**The system is blind to semantic conflicts (bad):** It cannot detect
contradictory decisions, near-duplicate extractions, or grounding
inconsistencies when reference minutes are available.

**The three promotes are all wrong:** All three promoted cases (adv_002,
adv_008, adv_010) should have been held or rejected.  A human reviewer would
catch these issues immediately.  The system currently over-trusts its
extraction results when any output is produced.

The next highest-value investment is contradiction detection and semantic
duplicate resolution in the extraction pass.
