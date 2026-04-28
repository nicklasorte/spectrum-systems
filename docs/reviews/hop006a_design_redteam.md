# HOP-006A — Design Red-Team Review

Date: 2026-04-28
Branch: `claude/hop-006a-design-review-63ZsQ`
Scope: design-only review of the extraction workflow proposed in
`docs/hop/hop006_issue_extraction_design.md`. No runtime code, no
schemas, no eval cases land with this PR; this document red-teams the
design *before* HOP-006B is allowed to proceed.

## 1. Threat model — questions explicitly asked

| #  | Question                                                                  | Result       |
| -- | ------------------------------------------------------------------------- | ------------ |
| 1  | Is the proposed eval easy enough that the baseline saturates it?          | NO (F-1)     |
| 2  | Can the baseline be tuned post hoc to inflate score without real signal?  | NO (F-2)     |
| 3  | Can a candidate game the eval by memorising expected substrings?          | NO (F-3)     |
| 4  | Can held-out cases leak into the search set or vice versa?                | NO (F-4)     |
| 5  | Does any field in the proposed schema imply HOP owns risk authority?      | NO (F-5)     |
| 6  | Can `category` enums grow into authority-shaped values silently?          | NO (F-6)     |
| 7  | Can a candidate emit a `risk` item that no source turn supports?          | NO (F-7)     |
| 8  | Can `evidence_refs` point off-transcript or be spoofed?                   | NO (F-8)     |
| 9  | Can `owner_text` / `due_date_text` be coerced into commitments?           | NO (F-9)     |
| 10 | Does the design preserve the advisory-only invariant the rest of HOP holds? | YES (F-10) |

Findings below carry severity, the attack vector, the design-time
mitigation captured in §3 of the design doc, and the implementation-time
test that will lock the mitigation in (the test name is recorded so
HOP-006B has an explicit landing target).

---

## Finding F-1 — Eval too easy / baseline saturation

**Severity**: P1 — eval-set integrity.

**Vector**: HOP-006A could ship an eval that the keyword-only baseline
already passes at >0.85, leaving proposers no headroom and turning
frontier motion into noise.

**Mitigation (design-time)**:

- Section 9 of the design doc declares the baseline intentionally
  weak: single-turn keyword scan, hard-coded `confidence_signal=medium`,
  hard-coded `ambiguity_signal=none`, no cross-turn reasoning.
- Sections 7–8 require dedicated cases for ambiguity classes the
  baseline cannot solve by construction (`ambiguous_attribution`,
  `competing_actions`, `conflicting_evidence`, `paraphrased_duplicate`,
  `negation_attempted`).
- Section 9 sets a **baseline ceiling**: `search_score < 0.85` and
  `heldout_score < 0.70`. If exceeded, HOP-006B MUST NOT proceed.

**Test that locks it in (HOP-006B target)**:

- `tests/hop/test_extraction_baseline_ceiling.py::test_baseline_search_score_below_ceiling`
  — runs the baseline against the search set, asserts `score < 0.85`.
- `tests/hop/test_extraction_baseline_ceiling.py::test_baseline_heldout_score_below_ceiling`
  — same against the held-out set with `< 0.70`.

**Residual risk**: the ceiling is a static threshold. If the workflow
matures, a future re-baseline could legitimately exceed it. Adjustment
requires a governed eval-set version bump and a fresh design pass —
captured in design §9.

---

## Finding F-2 — Eval gaming via post-hoc baseline tuning

**Severity**: P1 — silent eval inflation.

**Vector**: A contributor could quietly tune the baseline keyword
list (add "should", "must", etc.) to lift the baseline score after
seeing case content, defeating the point of the ceiling.

**Mitigation (design-time)**:

- Design §9 fixes the keyword list explicitly. Any change to the list
  must touch
  `spectrum_systems/modules/hop/extraction_baseline_harness.py`, which
  is in the AGS preflight scope (`docs/hop/preflight.md` §"When to
  run").
- The baseline ceiling test runs deterministically; CI will fail
  closed if anyone lifts the baseline above the ceiling.
- The proposer (per `proposer.py:50`) is bound to a single declared
  modification path. Adding a *second* candidate path for the
  extraction baseline requires updating
  `proposer.CANDIDATE_MODULE_PATH`, which is grep-visible and
  governed.

**Test that locks it in**:

- The existing `tests/hop/test_authority_shape_regression.py` already
  scans every HOP source file for forbidden tokens; any baseline
  change that introduces authority-shaped keywords will fail before
  CI.
- HOP-006B adds a digest-pin test:
  `tests/hop/test_extraction_baseline_ceiling.py::test_baseline_keyword_set_pinned`
  asserts the SHA-256 of the keyword tuple matches a pinned constant.
  Changing the keyword set is a deliberate, traceable act.

**Residual risk**: low — the digest pin is a tripwire, not a gate.
Anyone deliberately editing the pin gets caught at PR review.

---

## Finding F-3 — Candidate memorising expected substrings

**Severity**: P1 — held-out leakage attack vector (mirror of HOP-005 F-2).

**Vector**: A candidate harness reads
`contracts/evals/hop_extraction_search/cases/*.json` (or the
held-out equivalent) and substring-matches expected categories or
owners. The same attack class HOP-005 closed for the FAQ workflow
re-opens here unless the same defences are wired in.

**Mitigation (design-time)**:

- Design §8 explicitly requires
  `SandboxConfig(denied_read_path_prefixes=("contracts/evals",))` for
  every extraction-eval call site, mirroring
  `docs/reviews/hop005_authority_eval_hardening_review.md` §F-2.
- Design §8 mandates regression tests modelled on
  `tests/hop/test_heldout_hardening.py::test_heldout_cases_are_unreadable_from_sandbox`,
  `test_heldout_cases_unreadable_via_pathlib`, and
  `test_heldout_cases_unreadable_via_os_open`.

**Test that locks it in (HOP-006B target)**:

- `tests/hop/test_extraction_heldout_hardening.py::test_extraction_heldout_unreadable_from_sandbox`
- `tests/hop/test_extraction_heldout_hardening.py::test_extraction_heldout_unreadable_via_pathlib`
- `tests/hop/test_extraction_heldout_hardening.py::test_extraction_heldout_unreadable_via_os_open`

**Residual risk**: identical to FAQ workflow — a caller that forgets
the `denied_read_path_prefixes` config exposes the held-out set. This
is a call-site contract; HOP-006B must reference it in the docstring
of every extraction-eval entry point.

---

## Finding F-4 — Held-out leakage into search set

**Severity**: P1 — eval-set integrity.

**Vector**: A held-out transcript shares verbatim turn text with a
search-set transcript. A candidate that fits the search set
generalises to the held-out set for free, defeating the held-out
cohort's purpose.

**Mitigation (design-time)**:

- Design §8 invariants:
  - disjoint `transcript_id` sets (manifest meta-test);
  - disjoint surface text (token-overlap guard);
  - both invariants asserted at manifest-build time, not at runtime.
- The token-overlap threshold lands with HOP-006B (a concrete
  implementation choice, not a design boundary).

**Test that locks it in (HOP-006B target)**:

- `tests/hop/test_extraction_heldout_hardening.py::test_extraction_heldout_disjoint_transcript_ids`
- `tests/hop/test_extraction_heldout_hardening.py::test_extraction_heldout_disjoint_turn_text`

**Residual risk**: paraphrase-only leakage (same meaning, different
words) is not caught by token overlap. The held-out cohort
intentionally includes `paraphrased_duplicate` cases to keep at least
one paraphrase-aware adversary in scope; HOP-006B should record the
threshold and rationale in the manifest's `coverage_notes` field.

---

## Finding F-5 — Authority-shaped fields

**Severity**: P0 — would re-open HOP-005 F-1 in a new module.

**Vector**: Field names like `risk_blocks_release`, `action_owner_id`,
`due_date`, or `severity` would either embed authority verbs (`block`,
`release`) or claim authority over downstream policy (`severity` is an
EVL responsibility).

**Mitigation (design-time)**:

- Design §4 uses `owner_text` (raw text, never a normalized owner
  id) and `due_date_text` (raw substring, never a parsed date).
- No `severity`, `priority`, `blocks_*`, or `requires_*` fields are
  proposed.
- `confidence_signal` and `ambiguity_signal` carry the safe `_signal`
  suffix; both are bucketed enums, not free-form scores.
- `delegates_to: ["JSX", "EVL"]` is a static const set in the
  schema (per Phase-2 schema family); HOP names the consuming
  authorities by code, never by verb.

**Test that locks it in (HOP-006B target)**:

- `tests/hop/test_authority_shape_regression.py` already scans the
  whole HOP scope; HOP-006B adds the new schema and module to the
  scope list and re-runs.
- A new schema-shape test
  (`tests/hop/test_extraction_schema_shape.py::test_no_forbidden_fields`)
  enumerates the proposed field set and asserts no field name
  contains a forbidden cluster substring.

**Residual risk**: future schema extensions could re-introduce
authority-shaped names. The AGS regression test catches this; the
design doc explicitly forbids field-name drift without a schema
version bump (§4).

---

## Finding F-6 — Schema ambiguity / silent enum drift

**Severity**: P2 — would weaken category-correctness signal.

**Vector**: `category` could be expanded (e.g. with new free-form
labels) without a schema bump, letting a candidate emit
out-of-vocabulary categories that pass structural validation if the
schema is loose.

**Mitigation (design-time)**:

- Design §4 declares `category` enum-bound to exactly five values.
- `additionalProperties: false` everywhere — no free-form fields.
- Adding a category requires a schema *and* eval-set version bump
  (design §4, §11).

**Test that locks it in (HOP-006B target)**:

- `tests/hop/test_extraction_schema_shape.py::test_category_enum_pinned`
  asserts the enum tuple matches a pinned constant.
- `tests/hop/test_extraction_schema_shape.py::test_additional_properties_disallowed`
  asserts every nested object has `additionalProperties: false`.

**Residual risk**: the enum is small and load-bearing. Pinning gives
a tripwire; a deliberate change is a deliberate act.

---

## Finding F-7 — Hallucinated risks / actions / unsupported items

**Severity**: P1 — false positives directly attack the false-positive
metric.

**Vector**: A candidate fabricates a `risk` item with a
plausible-sounding `description` but no source span supports it. The
eval's `category_correctness` could pass on category alone if
`evidence_refs` is optional or weakly required.

**Mitigation (design-time)**:

- Design §4 requires `evidence_refs` minLength 1 *and* requires that
  every ref point to a substring of an actual source turn.
- Design §6 `structural_extraction` judge checks
  `source_turn_indices ⊆ [0, len(turns))` and that
  `evidence_refs.turn_index` matches.
- Design §10 names `evidence_coverage` and `false_positive_rate` as
  diagnostic metrics surfaced in `hop_harness_trace`. A candidate that
  emits unsupported items will move both metrics in the wrong
  direction.

**Test that locks it in (HOP-006B target)**:

- `tests/hop/test_extraction_evaluator.py::test_unsupported_item_fails_structural`
  — emits an item whose `evidence_refs` reference an out-of-range
  `turn_index`; asserts the structural judge fails.
- `tests/hop/test_extraction_evaluator.py::test_unsupported_item_offset_out_of_range`
  — emits `char_start, char_end` outside the turn text length;
  asserts the structural judge fails.

**Residual risk**: a candidate could pick a substring that *exists* in
the transcript but is unrelated to the claimed category (e.g.
extracting "we will release" from a distractor turn and labelling it
`action`). The `distractor_statement` cases in §7 and the
`distractor_authority_carrier` cases in §8 are designed precisely to
catch this.

---

## Finding F-8 — Spoofed evidence_refs

**Severity**: P2 — spoofs `evidence_coverage` without supporting the
item.

**Vector**: A candidate emits `evidence_refs` that **technically**
satisfy `0 <= turn_index < len(turns)` and `0 <= char_start <
char_end <= len(turn.text)` but the highlighted substring has nothing
to do with the `description`.

**Mitigation (design-time)**:

- Design §6 `expected_extraction` judge matches on
  (category, source-turn-set, owner_text-substring) tuples. A
  candidate that points at a structurally-valid but unrelated span
  will not match an expected tuple.
- The `false_positive_rate` metric (§10) is computed against expected
  tuples, not against `evidence_refs` validity alone.

**Test that locks it in (HOP-006B target)**:

- `tests/hop/test_extraction_evaluator.py::test_spoofed_evidence_does_not_match_tuple`
  — emits a structurally-valid item with `evidence_refs` pointing at
  unrelated text; asserts `false_positive_rate > 0` and the
  `expected_extraction` judge fails.

**Residual risk**: the eval can only verify what the cases declare. A
case that lists only category and source-turn-set (without an
expected `owner_text` substring) leaves room for a candidate to
spoof. Cases with an attribution dimension MUST include the
`owner_text`-substring expectation; this is a HOP-006B authoring
discipline requirement and is stated as such in the manifest's
`coverage_notes`.

---

## Finding F-9 — Owner / due-date coerced into commitments

**Severity**: P2 — would re-shape HOP into a planning authority.

**Vector**: Future field-name drift could turn `owner_text` into
`assigned_owner` or `due_date_text` into `due_date` (parsed datetime).
Either move turns extraction output into binding commitment data,
which is JSX/CDE territory.

**Mitigation (design-time)**:

- Design §4 fixes both fields as nullable raw strings.
- Design §2 explicitly disallows owner assignment and due-date
  parsing.
- The Phase-2 schema family (`advisory_only: const true`,
  `delegates_to`) is reused unchanged.

**Test that locks it in (HOP-006B target)**:

- `tests/hop/test_extraction_schema_shape.py::test_owner_text_is_nullable_string`
- `tests/hop/test_extraction_schema_shape.py::test_due_date_text_is_nullable_string`
- `tests/hop/test_extraction_schema_shape.py::test_advisory_only_is_const_true`

**Residual risk**: low — the schema-shape tests are explicit. A
contributor would have to change the schema *and* the test in the
same PR to coerce the field. AGS regression catches authority-shaped
field names regardless.

---

## Finding F-10 — Advisory-only invariant preserved

**Severity**: P0 — class invariant.

**Question**: does HOP-006 preserve the rule that HOP never claims
authority owned by REL / CDE / JDX / SEL?

**Verification (design-time)**:

| invariant                              | location                                                |
| -------------------------------------- | ------------------------------------------------------- |
| `advisory_only: const true`            | design §4 (proposed schema)                             |
| `delegates_to` references canonical owner | design §4 (`["JSX", "EVL"]`)                          |
| no field with bare authority verb       | design §4 + F-5                                        |
| no enum value with bare authority verb  | design §5 + §6 (failure modes / judge names)           |
| no cross-module write outside HOP       | design §11 (no new owner surfaces)                     |
| no proposer modifies anything outside the candidate path | unchanged from `proposer.py:50` |
| held-out sandbox isolation asserted     | design §8 + F-3                                        |
| baseline ceiling asserted               | design §9 + F-1                                        |

The advisory-only invariant is preserved by construction. HOP-006B
inherits the existing AGS preflight, system-registry guard, and
authority-leak guard with no scope changes.

---

## 2. Items intentionally retained (not findings)

- `harness_type = transcript_to_extraction_signal` (proposed in
  design §6) carries the safe `_signal` suffix; the AGS preflight
  exempts safe-suffix tokens (per `docs/hop/preflight.md` §"Repairing
  violations").
- `delegates_to: ["JSX", "EVL"]` lists owners by code. This is the
  exact pattern the Phase-2 schemas (`harness_release_readiness_signal`,
  `harness_restoration_signal`) use; it is a *non-owning reference*, not
  a claim.
- `confidence_signal` enum values (`low` / `medium` / `high`) are
  bucketed labels, not authority verbs. The `_signal` suffix exempts
  them from the preflight by name.

## 3. Open questions for HOP-006B (not blocking)

1. Token-overlap threshold for the held-out disjointness guard
   (§F-4). Default proposal: bigram overlap > 0.5 across any pair of
   transcripts ⇒ reject. Lands as a constant in the manifest builder.
2. Whether the proposer should be allowed to mutate the extraction
   baseline once HOP-006B lands. Default proposal: no — the existing
   four templates target the FAQ baseline only. Extraction-targeted
   templates land in a later batch with their own proposer-quota review.
3. Whether `category_correctness` should be split per-category in
   `hop_harness_score`. Default proposal: keep aggregate for the
   frontier; expose per-category breakdowns in `hop_harness_trace`.

These are implementation choices, not design boundaries. None
blocks HOP-006B.

## 4. Verification commands and results

```bash
# AGS-001 authority-shape preflight, scoped to HOP files touched in HOP-006A
bash scripts/preflight_hop.sh
# expected: violation_count == 0 (HOP-006A is design-only)

# System-registry guard
python scripts/run_system_registry_guard.py \
    --base-ref origin/main \
    --head-ref HEAD \
    --output outputs/system_registry_guard/system_registry_guard_result.json

# Targeted regression (HOP-005 lock-in)
python -m pytest tests/hop/test_authority_shape_regression.py -q
```

Results from this PR are recorded in `outputs/` and summarised in the
HOP-006A PR description.

## 5. Recommendation

**GO for HOP-006B implementation.**

The design preserves the advisory-only invariant, sets a load-bearing
baseline ceiling, mirrors the held-out hardening already proven in
HOP-005, and explicitly forbids authority-shaped field/enum drift. No
new authority is created and no existing authority is extended.

Required fixes before HOP-006B build (all design-time fixes; no code
changes outside HOP-006A's scope):

1. **Land the design + red-team in main** (this PR) so HOP-006B
   has a stable target.
2. **Fix stale registry/docs language** flagged in §1 of the
   HOP-006A PR description (the `no autonomous proposer is implemented
   yet` sentence in `docs/architecture/system_registry.md` and the
   `BATCH-1` framing in `docs/hop/golden_workflow.md` and
   `docs/hop/batch2_followups.md`). These are descriptive drift, not
   authority drift, but they will mislead HOP-006B's prompt context
   if left unfixed. **Done in this PR.**
3. **Pin the baseline ceiling thresholds** in design §9. **Done.**
4. **Pin the category enum** in design §4. **Done.**
5. **Name the regression tests** HOP-006B must land. **Done in §F-1
   through §F-9 above.**

When HOP-006B opens, the first PR comment must reference this red-team
review by section number, and the PR's pytest scope must include all
test names listed under "Test that locks it in (HOP-006B target)"
above.

---

## 6. Boundary statement

HOP does not own issue, risk, action, open-question, or assumption
authority. The extraction workflow proposed in HOP-006A is a
**non-owning support capability** that classifies content already
present in a transcript into advisory items, with `advisory_only=true`
and `delegates_to` set to the consuming canonical owners (JSX, EVL).
Every item is content-bound to a source turn. HOP never emits owner input on
whether an issue "matters", whether a risk "blocks" anything, or
whether an action "must" happen — those judgments remain with the
canonical owners.
