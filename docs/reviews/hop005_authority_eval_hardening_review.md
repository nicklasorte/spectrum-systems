# HOP-005 — Authority/Eval Hardening Red-Team Review

**Scope:** the residue cleanup and held-out hardening added in HOP-005:

- HOP module + test docstrings (`spectrum_systems/modules/hop/__init__.py`,
  `spectrum_systems/modules/hop/promotion_readiness.py`,
  `spectrum_systems/modules/hop/rollback_signals.py`,
  `tests/hop/test_heldout_eval.py`).
- Held-out eval set (`contracts/evals/hop_heldout/`): generator,
  cases, manifest.
- Sandbox-isolation tests for held-out reads.
- New developer preflight (`scripts/run_authority_shape_preflight.py`,
  `docs/hop/preflight.md`).

**Outcome:** every attack vector below is closed by an explicit test
and/or schema constraint that already lived in the code, plus the new
hardening added in this PR. No guards were weakened; HOP remains
advisory-only.

## Attack matrix

| # | Attack class | Vector | Severity | Status | Fix / mitigation | Test |
|---|---|---|---|---|---|---|
| 1 | HOP appears to own release/promotion/rollback authority | Reader of HOP docstrings concludes HOP can promote/rollback because the docstrings use ownership-claim verbs ("emits", "owns", "decides"). | high | CLOSED | Module + test docstrings rewritten to name the canonical owner (REL/CDE/SEL) explicitly and to drop ownership-claim verbs. Backwards-compat aliases (`PromotionGateError`, `evaluate_promotion`, `build_rollback_record`, …) removed so HOP carries only advisory-named symbols. | `test_heldout_transcript_text_is_authority_safe`, `run_system_registry_guard.py` (passes). |
| 2 | Held-out cases readable by candidate harness | A malicious harness opens `contracts/evals/hop_heldout/cases/*.json`, memorises answers, and trivially saturates the readiness signal. | critical | CLOSED | Evaluator already runs each case under a sandbox with `denied_read_path_prefixes=(contracts/evals,)`. HOP-005 adds two regression tests that prove the sandbox denies a real read attempt: one routes through the evaluator (whole bundle fails sandbox_violation), one calls the sandbox directly. | `test_heldout_cases_unreadable_from_sandbox_via_evaluator`, `test_heldout_cases_unreadable_from_sandbox_directly`. |
| 3 | Authority-shaped names sneak into schema refs | A new HOP schema accidentally uses `artifact_type=hop_harness_promotion_decision` (or `_certification_record`, `_control_decision`, `_rollback_record`) and bypasses review because the structural detector is a CI-only gate. | high | CLOSED | New `scripts/run_authority_shape_preflight.py` runs the structural detector locally and emits suggested renames; CI keeps `run_authority_leak_guard` and `run_system_registry_guard` as fail-closed gates. The detector regex `(decision|certification|promotion|enforcement)` still trips on every banned form. | Existing `tests/hop/test_schemas.py` plus the preflight artifact emitted at `outputs/authority_shape_preflight/authority_shape_preflight_result.json`. |
| 4 | Stale docs mislead future prompts | HOP docs/eval cases contain authority-shaped phrasing ("certification gate", "promotion gates", "allow versus block", "rollback restores the prior promoted harness") that a future prompt or contributor could grep and treat as canonical HOP vocabulary. | high | CLOSED | Held-out generator rewritten to neutral content (`eval bundle`, `routes inputs`, `held-out set`, `input cached`, `input batches`, `trace artifact`). Module + test docstrings rewritten. New test fails closed if any held-out turn text contains an authority-shaped token. | `test_heldout_transcript_text_is_authority_safe`. |
| 5 | AGS misses prior HOP regressions | Earlier HOP regressions (`promotion_decision`, `rollback_record` artifact types; `decision`/`allow`/`block` values; quarantine re-readiness) re-appear and slip past the guards. | high | CLOSED | Replayed each prior regression through `run_authority_leak_guard.py` and `run_authority_shape_preflight.py`: every prior failure surfaces as a structural or vocabulary violation. The HOP-005 changeset itself runs clean (`status: pass` on both guards). The earlier red-team `test_attack_*` suite (`tests/hop/test_phase2_red_team.py`) still passes. | `tests/hop/test_phase2_red_team.py::*`, plus the preflight + leak-guard artifacts. |
| 6 | Held-out eval too close to search set | Held-out cases share structural patterns with search cases, allowing a candidate that overfits the search set to also pass the held-out set, masking the regression the held-out set is supposed to catch. | medium | CLOSED | Added 5 harder held-out cases (long multi-sentence answer, three-topic switch, orphan-assistant-leading turn, qmark-inside-assistant adversarial, leakage-marker-in-question adversarial). Existing `test_heldout_disjoint_from_search_set` still enforces transcript-id disjointness; new `test_heldout_covers_required_failure_categories` enforces the HOP-005 category checklist. | `test_heldout_covers_required_failure_categories`, `test_heldout_size_within_bounds`, `test_baseline_passes_held_out_set`. |
| 7 | Manifest tampering | Caller swaps a case file or manifest entry to a tampered hash (e.g. to drop the leakage case). | high | CLOSED (pre-existing) | The evaluator's manifest loader fails closed on `content_hash` mismatch; HOP-005 leaves that gate untouched. | `test_heldout_tampered_manifest_rejected`. |
| 8 | Forbidden-marker bypass via question text | Adversarial harness embeds the leakage marker `__hop_heldout_leak__` in the *answer* even when the user *question* contains the marker (so the case looks "innocent" to a structural scan that only reads questions). | medium | CLOSED | New adversarial case `adversarial_leakage_in_question_text` puts the marker in the user question and uses `forbidden_substrings_in_answers` to reject any harness that echoes the marker into the answer body. | `test_baseline_passes_held_out_set` exercises the baseline against the new case. |

## Notes on each finding

### 1. Authority-shaped vocabulary in HOP voice

**Before:** The HOP module docstrings said *"HOP emits"* and *"HOP never
self-certifies"*; the test docstrings called the held-out set the
*"certification eval set"*; both `promotion_readiness.py` and
`rollback_signals.py` retained backwards-compat aliases
(`PromotionGateError`, `evaluate_promotion`, `build_rollback_record`,
…). A grep for "promotion" / "rollback" / "certify" inside HOP would
return language that *looks* authoritative.

**After:** Docstrings rewritten so HOP only says *packages*, *signals*,
or *advises*, and every authority verb is followed by an explicit
external-owner reference (REL/CDE/SEL per
`contracts/governance/authority_registry.json`). Backwards-compat
aliases removed: a grep on the HOP modules now returns only
advisory-shaped symbols. Verified via
`grep -nE "Backwards-compatible|backwards-compat|alias" spectrum_systems/modules/hop/*.py`
returning empty.

**Test:** `test_heldout_transcript_text_is_authority_safe` plus the
clean run of `run_system_registry_guard.py` over the changeset.

### 2. Sandbox isolation of held-out cases

**Before:** The evaluator already passed
`denied_read_path_prefixes=(repo_root/contracts/evals,)` to the
sandbox, but no HOP-level test exercised the deny path. A regression
in `evaluator.py` that dropped the deny prefix would be invisible to
the test suite.

**After:** Two regression tests:

1. `test_heldout_cases_unreadable_from_sandbox_via_evaluator` — runs
   an adversarial candidate that opens
   `contracts/evals/hop_heldout/manifest.json`. Asserts the bundle
   pass-count is zero and that at least one failure has
   `failure_class="sandbox_violation"`.
2. `test_heldout_cases_unreadable_from_sandbox_directly` — bypasses
   the evaluator and calls `execute_candidate` with the deny prefix
   set. Asserts `result.violation_type == "sandbox_violation"` and the
   detail names the denied subtree.

If either test goes red, the held-out set is no longer protected and a
candidate can memorise its way to a green readiness signal.

### 3. Authority-shaped names in schema refs

**Before:** The fail-closed structural detector
(`scripts/authority_shape_detector.py`) caught
`(decision|certification|promotion|enforcement)` in `artifact_type` /
`schema_ref`, but only inside CI. A contributor adding a new HOP
schema could ship with `hop_harness_promotion_decision` and only learn
about it on the PR run.

**After:** `scripts/run_authority_shape_preflight.py` runs the same
detector locally, defaulting to `--suggest-only`, and writes a JSON
artifact with `structural_violations`, `vocabulary_violations`, and
`text_hints` that include suggested advisory-safe renames
(`promotion_decision` → `release_readiness_signal`,
`rollback_record` → `rollback_signal`, `quarantine` →
`isolation_recommendation`, etc.). `docs/hop/preflight.md` documents
the contributor flow.

**Test:** Existing `tests/hop/test_schemas.py` enforces every shipped
HOP schema is advisory-safe; the new preflight is verified by the
`outputs/authority_shape_preflight/authority_shape_preflight_result.json`
status field on this changeset.

### 4. Stale docs misleading future prompts

**Before:** Held-out transcripts contained authority-shaped phrasing —
`"How much does the certification gate cost?"`,
`"Who decides allow versus block?"`,
`"Tell me about promotion gates."`,
`"Is rollback reversible?"`,
`"Rollback restores the prior promoted harness."`,
`"Where does the rollback artifact go?"`. A future prompt grepping the
held-out cases for examples could conclude HOP routinely talks about
promotion / rollback / certification.

**After:** Each authority-shaped string rewritten to neutral content
(`eval bundle`, `routes inputs`, `input batches`, `trace artifact`,
`input cached`). New test `test_heldout_transcript_text_is_authority_safe`
fails closed if any future change reintroduces a forbidden token in
turn text.

### 5. AGS catches every prior HOP regression

I replayed each prior HOP regression through the new preflight and the
existing leak/registry guards:

- `promotion_decision` artifact type → `authority_shape_artifact_type`
  violation (caught).
- `rollback_record` artifact type → same (caught).
- `decision`/`allow`/`block`/`promote` field+value → vocabulary
  violation (caught).
- `quarantine` re-readiness → `candidate_not_quarantined` rationale
  forces `risk_signal` (caught at the readiness builder).
- `advisory_only=false` smuggle → schema validation rejects (caught
  in `tests/hop/test_phase2_red_team.py`).

The HOP-005 changeset itself runs clean on all three guards
(`status: pass` for `run_authority_leak_guard`,
`run_system_registry_guard`, and `run_authority_shape_preflight`).

### 6. Held-out / search-set proximity

**Before:** Held-out had 12 cases. While transcript-id disjoint, the
content patterns were close enough to the search set that a candidate
overfitting search-eval phrasing might still saturate held-out.

**After:** 17 cases (5 added). The new cases stress:

- Multi-sentence answer body (longer than existing
  `golden_long_answer`).
- Three-topic switch with three Q/A pairs and three different
  substring checks.
- Orphan leading-assistant turn that the harness must skip without
  pairing it to anything.
- `?` inside an assistant turn that must NOT be treated as a question
  source.
- Leakage marker placed inside the *user question* (not just the
  answer), with `forbidden_substrings_in_answers` enforcing that the
  harness does not echo it back.

`test_heldout_covers_required_failure_categories` fails closed if any
of the seven HOP-005 mandatory categories goes missing.

### 7. Manifest tampering (pre-existing)

Untouched. `test_heldout_tampered_manifest_rejected` still asserts
`load_eval_set_from_manifest` raises
`hop_evaluator_tampered_manifest` when an entry's `content_hash` is
mutated.

### 8. Leakage marker in question

**Before:** The original `adversarial_forbidden_marker` case put the
marker in the *answer* body and asked the harness to not produce it.
A harness that only filtered answer text but ignored question text
would pass — yet would still echo back markers from question text in
real workloads.

**After:** New case `adversarial_leakage_in_question_text` places the
marker in the user question. The case still uses
`forbidden_substrings_in_answers`, so a passing harness must
explicitly strip or refuse to repeat the marker on its way to the
answer field, regardless of where it first appeared.

## Verification

```bash
python scripts/run_authority_shape_preflight.py --suggest-only \
    --changed-files <changed-files> \
    --output outputs/authority_shape_preflight/authority_shape_preflight_result.json
# status: pass  structural_violation_count: 0  vocabulary_violation_count: 0

python scripts/run_system_registry_guard.py \
    --changed-files <changed-files> \
    --output outputs/system_registry_guard/system_registry_guard_result.json
# status: pass

python scripts/run_authority_leak_guard.py \
    --changed-files <changed-files> \
    --output outputs/authority_leak_guard/authority_leak_guard_result.json
# status: pass

python -m pytest tests/hop -q
# 232 passed
```

## Residual risks (intentional)

- The `blocks_promotion` boolean field on
  `hop_harness_failure_hypothesis` is retained because it advises the
  *external* CDE/REL gate. Renaming it would require schema-version
  bumps and migration of every persisted failure hypothesis. The
  semantics are: "if true, the HOP failure is severe enough that an
  external owner should refuse release". The leak guard does not flag
  `blocks_promotion` (it is not in the FORBIDDEN_FIELDS list).
- The module file names `promotion_readiness.py` and
  `rollback_signals.py` are retained because their suffixes (`_readiness`,
  `_signals`) are advisory-shaped and the modules' contents only
  package signals for external owners. Renaming the files would
  cascade into every test and import statement without any guard
  benefit.
- The `quarantine` recommendation value on
  `hop_harness_rollback_signal` is retained because the schema declares
  `delegates_to: REL` (const) — the value names an action that REL,
  not HOP, performs. This is the same rationale that lets the leak
  guard already pass.

These three are documented here so any future cleanup pass knows the
constraints. None of them lets HOP appear to own release, rollback,
promotion, certification, control, enforcement, or judgment authority.
