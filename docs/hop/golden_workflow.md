# HOP Golden Workflow — `transcript -> FAQ`

Owner: HOP (Harness Optimization Pipeline)
Status: foundation (HOP-BATCH-1)
Stable across: BATCH-1 through BATCH-2 freeze; revisions require eval-set
version bump and a frontier recompute.

## 1. Purpose

The golden workflow is the single, stable target the HOP foundation is
allowed to optimize against in BATCH-1. It pins the input shape, the output
shape, the evaluation criteria, and the failure modes that any candidate
must handle. Every candidate harness — including the deterministic baseline
— runs against this workflow against the same versioned eval set.

## 2. Input artifact

**Type:** `transcript` (HOP-internal shape, used inside `hop_harness_eval_case.input`)

```
{
  "transcript_id": str (non-empty, unique within the eval set),
  "turns": [
    {"speaker": "user" | "assistant", "text": str}
  ]
}
```

- Empty `turns` is admissible (adversarial coverage).
- Speakers are restricted to the two-element enum to remove ambiguity.
- `text` is treated as a raw UTF-8 string; the harness must not interpret
  HTML/Markdown.

## 3. Output artifact

**Type:** `hop_harness_faq_output`
**Schema:** `contracts/schemas/hop/harness_faq_output.schema.json`

```
{
  "artifact_type": "hop_harness_faq_output",
  "schema_ref": "hop/harness_faq_output.schema.json",
  "schema_version": "1.0.0",
  "trace": {"primary": str, "related": [str]},
  "content_hash": "sha256:...",
  "transcript_id": str,
  "candidate_id": str,
  "items": [
    {
      "question": str (non-empty),
      "answer": str (non-empty),
      "source_turn_indices": [int]
    }
  ],
  "generated_at": ISO-8601 UTC
}
```

- `additionalProperties: false` everywhere — no free-form extension allowed.
- `items: []` is allowed for legitimately empty cases (adversarial rejection).

## 4. Evaluation criteria

Evaluation is enum-bound. Three judges are valid in BATCH-1; no free-form
LLM judge is permitted.

| Judge | Pass condition |
| --- | --- |
| `structural` | `min_qa_pairs <= len(items) <= max_qa_pairs`, no forbidden substring. |
| `expected_qa_pairs` | `structural` plus required question/answer substrings. |
| `rejection_expected` | `expect_rejection = true` ⇔ `items` is empty. |

Scoring is `pass_count / case_count` (`aggregate_method = "pass_rate"`).
Frontier objectives: `score` (max), `cost` (min), `latency_ms` (min),
`trace_completeness` (max), `eval_coverage` (max).

## 5. Failure modes covered

Each eval case targets one or more of these (enum-bound) failure modes:

- `no_questions` — transcript yields zero QA pairs.
- `ambiguous_attribution` — adjacent same-speaker turns; baseline must not
  collapse multiple user questions onto one answer.
- `interleaved_speakers` — assistant turns interleaved with user turns must
  not break pairing.
- `long_answer_truncation` — assistant turns may be multi-sentence; harness
  must preserve the answer.
- `duplicate_questions` — repeated identical (question, answer) pairs must
  collapse to one item.
- `non_question_marked_question` — sentences ending in `.` must NOT be
  treated as questions.
- `empty_transcript` — empty transcripts produce zero items, not an error.
- `single_turn` — single user question with one assistant answer.
- `leakage_attempt`, `schema_weakening_attempt`, `hardcoded_answer_attempt`
  — failure-derived placeholders for HOP's safety surface; the harness must
  not embed eval ids or hardcoded answer strings.

## 6. Boundaries

HOP does NOT, in this workflow:

- generate transcripts;
- evaluate harness *output style* with a free-form judge;
- promote any candidate (CDE / GOV authority);
- run harness candidates outside the validator + safety_checks gate.

Any extension to the golden workflow requires a new schema version and an
eval-set version bump.
