# HOP-006 — Hard Workflow Design: Transcript → Issue/Risk/Action Extraction

Status: design (HOP-006A). No runtime, no schemas, no eval cases land with
this document. Implementation only proceeds if the GO recommendation in
section 12 holds after red-team review.

Owner-surface: HOP (advisory support only). Canonical owners (REL/GOV/CDE/
JSX/SEL) are not extended. Every artifact this workflow produces is an
advisory signal, content-bound to source turns and never self-attesting.

## 1. Purpose

Define the second hard workflow the HOP substrate is allowed to optimize
against. The first hard workflow (`transcript → FAQ`) is described in
`docs/hop/golden_workflow.md`; it remains canonical for HOP-BATCH-1 and
HOP-BATCH-2. HOP-006 introduces a *parallel*, independently versioned
workflow that exercises the same substrate (admission, sandbox, evaluator,
frontier, store) on a harder extraction surface:

```
transcript → issue / risk / action / open_question / assumption items
```

The workflow is intentionally a strict **support capability**. It
classifies content present in a transcript into advisory items. It
does not emit policy owner input, gate releases, advance candidates, or rank
risks for the canonical risk authority (EVL).

## 2. Boundary statement (read first)

The extraction harness does NOT, in this workflow:

- assert that an extracted `risk` blocks any release;
- assign owners or due dates as commitments — only as raw text the
  transcript already contains;
- emit what is a "real" issue versus a noise item as owner input — that judgment
  remains with the consuming authority (e.g. JSX/EVL) when one chooses
  to read the artifact;
- emit any free-form summary of the transcript (the schema permits only
  enum-bound categories and source-bound spans);
- modify the input transcript or any prior FAQ output;
- run outside the existing HOP sandbox + admission gate.

Each extracted item is a **non-owning support observation**. The
canonical owners on the consuming side (when one exists) are
referenced by their three-letter code; HOP never names a verb it
does not own.

## 3. Input artifact

**Type:** `transcript` (HOP-internal shape, identical to
`docs/hop/golden_workflow.md` §2 — re-used so admission and sandbox
contracts stay shared).

```
{
  "transcript_id": str (non-empty, unique within the eval set),
  "turns": [
    {"speaker": "user" | "assistant", "text": str}
  ]
}
```

- Empty `turns` is admissible (adversarial coverage).
- `text` is a raw UTF-8 string; the harness MUST NOT interpret HTML or
  Markdown.
- `transcript_id` collisions with the FAQ eval set are forbidden by
  manifest construction (see §6).

## 4. Output artifact (proposed; schema NOT added in this PR)

**Type:** `hop_harness_extraction_signal` (proposed, not registered)

```
{
  "artifact_type": "hop_harness_extraction_signal",
  "schema_ref":    "hop/harness_extraction_signal.schema.json",
  "schema_version": "1.0.0",
  "trace":          {"primary": str, "related": [str]},
  "content_hash":   "sha256:...",
  "advisory_only":  true,                # const: true (mirrors §2)
  "delegates_to":   ["JSX", "EVL"],      # consuming canonical owners
  "transcript_id":  str,
  "candidate_id":   str,
  "items": [ Item, ... ],
  "generated_at":   ISO-8601 UTC
}
```

`Item` (proposed fields, all advisory):

| field                | type                                                                              | notes |
| -------------------- | --------------------------------------------------------------------------------- | --- |
| `item_id`            | string `^hop_extract_[a-z0-9_-]+$`                                                | content-hash-derived; deterministic |
| `category`           | enum `issue` \| `risk` \| `action` \| `open_question` \| `assumption`             | enum-bound; no free-form types |
| `description`        | string, minLength 1                                                               | the harness MUST quote/paraphrase only what the source turns contain |
| `evidence_refs`      | array of source-turn substring offsets (`{turn_index, char_start, char_end}`)     | every item MUST carry ≥1 evidence ref |
| `source_turn_indices` | array of unique non-negative integers                                            | derived from `evidence_refs.turn_index`; explicit for fast filtering |
| `owner_text`         | string \| null                                                                    | exact substring or paraphrase **of text the speaker provided**; never a normalized owner code |
| `due_date_text`      | string \| null                                                                    | raw text, e.g. "by Friday"; **not** parsed into a date |
| `confidence_signal`  | enum `low` \| `medium` \| `high`                                                  | bucketed; no free-form floats |
| `ambiguity_signal`   | enum `none` \| `attribution` \| `commitment` \| `temporal` \| `negation` \| `multi` | enum-bound; declares why the harness is unsure |

Constraints baked into the schema (when added in HOP-006B):

- `additionalProperties: false` everywhere.
- `items: []` is allowed for transcripts that legitimately contain none
  of the five categories (negative cases — see §7).
- `category` is enum-bound; new categories require a schema version
  bump and an eval-set version bump.
- `evidence_refs` minLength 1 — items without source-turn evidence are
  invalid by construction. This forecloses hallucinated risks.
- `owner_text` and `due_date_text` are nullable strings, never enums or
  parsed dates — they are raw text, not commitments.
- `advisory_only: const true` and `delegates_to` is required (mirrors
  the Phase-2 schema family per `docs/reviews/hop_batch4_review.md`).

The exact JSON Schema lands in HOP-006B. This document only fixes the
shape so the eval design and red-team can reason about it.

## 5. Failure modes covered (enum-bound)

Each eval case targets one or more of these, mirroring the
`failure_modes` enum the FAQ workflow uses:

- `no_extractable_items` — transcript yields zero items legitimately.
- `ambiguous_attribution` — adjacent same-speaker turns; harness must
  not attribute an action to the wrong actor.
- `competing_actions` — two assistant turns propose conflicting actions
  for the same question; harness must extract both with appropriate
  `ambiguity_signal=multi` rather than collapse silently.
- `implied_risk` — risk surfaced as a side effect of an answer (not
  named); harness must extract it only when source spans support it,
  with `confidence_signal=low` and `ambiguity_signal=negation` /
  `temporal` as appropriate.
- `unresolved_question` — user asks, assistant defers; must surface as
  `open_question`, not as `issue`.
- `assumption_disclosure` — assistant says "I'll assume X"; must
  surface as `assumption` with the literal substring.
- `negation_attempted` — assistant says "no risk here"; harness must
  NOT emit a `risk` item for the negated topic.
- `distractor_statement` — turn contains an authority-shaped substring
  (e.g. an advancement-cluster verb the harness does not own) that does
  **not** map to an extractable category; must NOT emit an `action` and
  must NOT carry the bare authority verb in `description`.
- `hardcoded_extraction_attempt` — failure-derived placeholder (mirror
  of the FAQ workflow's `hardcoded_answer_attempt`).
- `eval_id_leakage_attempt`, `schema_weakening_attempt` — failure-derived
  placeholders for the safety surface.

Each case names its targeted failure modes inside its
`hop_harness_eval_case` artifact. The judges in §6 assert them.

## 6. Evaluation criteria (proposed; eval cases NOT added in this PR)

Evaluation is enum-bound. The HOP evaluator already supports three
judges; HOP-006B introduces a fourth, all still enum-bound:

| Judge                    | Pass condition |
| ------------------------ | -------------- |
| `structural_extraction`  | `min_items <= len(items) <= max_items`; every item has `category` ∈ enum, `evidence_refs` non-empty, `source_turn_indices` ⊆ `[0, len(turns))`; no forbidden substring in `description`. |
| `expected_extraction`    | `structural_extraction` plus required (category, source-turn-set, owner_text-substring) tuples present. Tuple match is **set-equality**, not order-dependent. |
| `rejection_extraction`   | `expect_no_extractable_items=true` ⇔ `items == []`. |
| `ambiguity_extraction`   | for the case's declared ambiguity class, the harness must emit `ambiguity_signal == declared_class` on at least one item. Catches "false-confident" baselines. |

Scoring is `pass_count / case_count` (`aggregate_method = "pass_rate"`),
mirroring the FAQ workflow so the frontier API is unchanged.

Frontier objectives are unchanged from the FAQ workflow: `score`
(max), `cost` (min), `latency_ms` (min), `trace_completeness` (max),
`eval_coverage` (max). The two workflows share the substrate but live
on disjoint frontiers (different `harness_type`).

## 7. Search-eval design (NOT generated yet)

**Size:** 20–40 cases, target 30. Disjoint `transcript_id` namespace
from the FAQ eval set (`hop_xt_search_*`).

**Mandatory class coverage** (≥1 case each):

1. `ambiguous_attribution` — adjacent same-speaker turns produce two
   plausible owners.
2. `competing_actions` — two assistant turns disagree on the action.
3. `implied_risk` — a risk is supported by a source span only by
   inference.
4. `unresolved_question` — user asks, no answer.
5. `assumption_disclosure` — explicit "I'll assume" framing.
6. `negation_attempted` — assistant denies a risk.
7. `distractor_statement` — authority-shaped substring; expected
   `items == []` for the affected class.
8. `no-action negative` — full transcript with no actions; expected
   `items` contains zero `action` entries.
9. `no-risk negative` — full transcript with no risks; expected
   `items` contains zero `risk` entries.
10. `golden_multi_category` — at least one transcript that yields
    items across all five categories (the load-bearing positive case).

**Negative cases must outnumber positives in at least the
`distractor_statement` class** so a baseline that always emits items
cannot saturate the score (see §9).

## 8. Held-out eval design (NOT generated yet)

**Size:** ≥12 cases (matches the held-out floor asserted by
`tests/hop/test_heldout_hardening.py::test_heldout_set_strictly_larger_than_minimum`
for the FAQ workflow; HOP-006B sets the same floor for the extraction
workflow).

**Disjointness invariants:**

- Disjoint `transcript_id` from search set (asserted by manifest meta-test,
  mirroring `tests/hop/test_heldout_hardening.py`).
- Disjoint surface text — no transcript turn substring in the
  search set may appear verbatim in the held-out set (token-overlap
  guard, threshold TBD in HOP-006B).
- Sandbox-isolated: callers MUST pass
  `SandboxConfig(denied_read_path_prefixes=("contracts/evals",))` per
  Finding F-2 in `docs/reviews/hop005_authority_eval_hardening_review.md`.
  A regression test mirroring
  `test_heldout_cases_are_unreadable_from_sandbox` MUST be added before
  HOP-006B can ship.

**Harder ambiguity surface:**

- `attribution_chain` — three+ consecutive same-speaker turns, only
  one of which carries an actionable verb.
- `conflicting_evidence` — two source spans support opposite
  conclusions; harness MUST emit `ambiguity_signal != none` and MUST
  NOT pick a side silently.
- `distractor_authority_carrier` — turn contains a forbidden authority
  cluster substring (e.g. release-cluster or advancement-cluster verbs
  the harness does not own); harness MUST NOT carry the bare verb in
  `description` and MUST NOT classify
  it as `action`.
- `negation_chain` — three negated statements, one of which is
  *partially* affirmed by a later turn; harness MUST extract only the
  affirmed part with `confidence_signal=low`.
- `paraphrased_duplicate` — three paraphrases of the same risk; harness
  MUST collapse to one item or emit `ambiguity_signal=multi`.

A coverage meta-test mirroring
`test_heldout_required_coverage_classes_present` MUST land in
HOP-006B and assert each held-out class has ≥1 case.

## 9. Baseline harness — intentionally imperfect

The baseline lives under
`spectrum_systems/modules/hop/extraction_baseline_harness.py` (HOP-006B)
and is **deliberately weak** so the eval is not saturated by the
reference. Construction rules:

1. The baseline only inspects single turns at a time (no cross-turn
   reasoning). Anything requiring multi-turn context (attribution
   chains, conflicting evidence, paraphrased duplicates) is expected
   to fail.
2. The baseline uses a hard-coded keyword set:
   - `risk` ← turn contains "risk", "concern", "danger".
   - `action` ← turn contains "we will", "I'll", "let's", "todo".
   - `open_question` ← user turn ends with `?` AND no assistant turn
     in `[idx+1, idx+3]` carries any keyword.
   - `assumption` ← turn contains "assume" / "assuming".
   - `issue` ← turn contains "issue", "problem", "bug", "broken".
3. `confidence_signal` is hard-coded to `medium`. The baseline does not
   distinguish high- from low-confidence extractions.
4. `ambiguity_signal` is hard-coded to `none`. The baseline never
   declares ambiguity, so the `ambiguity_extraction` judge fails for
   every case that targets an ambiguity class — by construction.
5. `evidence_refs` are computed from the matching keyword's offset.
   When a turn contains multiple matches, only the first is kept.

Expected baseline behaviour against the search set:

- Passes `golden_multi_category` (keyword surface is sufficient).
- Fails every `ambiguous_attribution`, `competing_actions`,
  `conflicting_evidence`, and `paraphrased_duplicate` case (no
  cross-turn reasoning).
- Fails every `negation_attempted` case (emits a `risk` for negated
  language).
- Fails every `distractor_statement` case that uses authority-shaped
  substrings the keyword set happens to overlap.

### Baseline ceiling requirement (load-bearing)

> If the baseline scores **above 0.85** on the search set OR above
> **0.70** on the held-out set, the eval is **too easy**, and HOP-006B
> MUST NOT proceed.

Rationale: the FAQ workflow's baseline already passes the easy goldens
and fails the adversarial cohort by construction. The extraction
workflow MUST preserve the same property: the baseline must leave
visible headroom for proposer-driven candidates to climb. A saturated
baseline gives proposers nothing to optimize and turns frontier
movement into noise.

The ceiling is asserted by a meta-test in HOP-006B
(`tests/hop/test_extraction_baseline_ceiling.py`) that runs the
baseline against both eval sets and asserts:

- `search_score.score < 0.85`
- `heldout_score.score < 0.70`

If either threshold is exceeded, the test fails-closed; HOP-006B does
not land. Adjusting the ceiling requires a governed eval-set version
bump.

## 10. Metrics (proposed)

Each metric is computed inside the evaluator (already the canonical
scoring authority) and emitted as part of the existing
`hop_harness_score` + `hop_harness_trace` artifacts. No new authority
is introduced.

| metric                  | definition |
| ----------------------- | ---------- |
| `category_correctness`  | fraction of expected (category, source-turn-set) tuples present in `items`, with category match. |
| `evidence_coverage`     | fraction of emitted items whose `evidence_refs` cover ≥1 character of an expected source span. |
| `false_positive_rate`   | fraction of emitted items NOT matching any expected tuple. Bounded above 0; never negative. |
| `missed_item_rate`      | fraction of expected tuples NOT matched by any emitted item. |
| `source_turn_accuracy`  | fraction of emitted items whose `source_turn_indices` are a non-empty subset of expected source turns. |
| `ambiguity_handling`    | fraction of cases declaring an `ambiguity_class` for which the harness emitted `ambiguity_signal == declared_class` on ≥1 item. |

`score` (the frontier objective) remains `pass_rate`. The metrics above
are diagnostic only — they live in the trace and inform proposer
heuristics, not the gate. This preserves the rule that HOP never
self-attests advancement; advancement remains with REL/GOV/CDE.

## 11. What HOP-006A explicitly does NOT change

- No new schema files under `contracts/schemas/hop/` (only design refs).
- No new eval cases under `contracts/evals/hop_extraction*` (does not
  exist yet).
- No runtime module under `spectrum_systems/modules/hop/extraction*`.
- No registry-level authority changes — HOP remains a non-owning
  support substrate.
- No proposer mutation templates target the extraction harness. The
  existing four FAQ-targeted templates remain unchanged.

The full implementation (schemas, eval cases, baseline, sandbox
config, regression tests, documentation cross-links) ships in
HOP-006B, contingent on the GO recommendation in
`docs/reviews/hop006a_design_redteam.md` §8.

## 12. Cross-references

- `docs/hop/golden_workflow.md` — the FAQ workflow this design
  parallels.
- `docs/hop/preflight.md` — authority-shape preflight; applies as-is to
  the extraction surface.
- `docs/reviews/hop005_authority_eval_hardening_review.md` — sets the
  authority-shape and held-out hardening invariants HOP-006A inherits.
- `docs/reviews/hop_batch4_review.md` — sets the Phase-2 advisory-only
  schema discipline (`advisory_only: const true`, `delegates_to`).
- `docs/architecture/system_registry.md` §HOP — the canonical
  ownership statement; HOP-006 does not extend it.
