# ASF-01 Authority-Shape Feedback Loop — Red-team Review

Adversarial review of the ASF-01 chain
(`run_changed_scope_authority_scan.py` → RIL packet → FRE candidate →
`validate_authority_repair_candidate.py`). Goal: confirm the loop cannot be
abused to bypass CDE/SEL authority, weaken `authority_shape_preflight`, or
edit canonical ownership.

Severity legend: `must_fix` (blocks merge), `should_fix` (follow-up),
`observation` (acknowledged, no action this PR).

## Attack 1 — Repair candidate edits the authority registry

**Vector.** A coding agent (or a malicious upstream pipeline) crafts a
candidate that lists `contracts/governance/authority_registry.json` as a
target file with `replacement_class = vocabulary_only`, in order to slip an
ownership rewrite through.

**Result.** The TPA validator's `forbidden_target_prefixes` list explicitly
covers the authority registry, the authority-shape vocabulary, the neutral
vocabulary, the system-registry guard policy, the preflight implementation,
and `docs/architecture/system_registry.md`. Any target inside that list
emits `target_protected_authority_file` and the record's status becomes
`fail`. Test:
`test_tpa_rejects_owner_registry_target`.

**Classification.** observation — handled by current implementation.

## Attack 2 — Repair candidate adds an allowlist exception

**Vector.** Candidate carries an `allowlist_changes` field with a request to
exempt a MET path from the preflight scope.

**Result.** TPA validator rejects via the `forbidden_intent_keys` set
(`allowlist_changes`, `scope_prefix_changes`, `vocabulary_changes`,
`registry_edits`, …). Test:
`test_tpa_rejects_allowlist_change_intent`.

**Classification.** observation.

## Attack 3 — Repair candidate changes meaning instead of vocabulary

**Vector.** A candidate proposes a structural rewrite (e.g. flipping a
boolean or removing a check) but labels it `replacement_class:
vocabulary_only`.

**Result.** Two layered defenses:

- The replacement must use a `proposed_symbol` from the existing approved
  neutral vocabulary; arbitrary identifiers fail the
  `replacement_uses_approved_neutral_vocabulary` rule.
- The candidate is explicitly typed `proposed`. Application requires a
  separate, future authorized command which does not exist in this PR.
  ASF-01 only emits artifacts.

Tests:
`test_tpa_rejects_non_neutral_proposed_symbol`,
`test_tpa_rejects_non_vocabulary_only_replacement`.

**Classification.** must_fix → addressed in this PR. The repair candidate
has no apply path; the TPA contract enforces vocabulary-only replacements
drawn from the existing vocabulary.

## Attack 4 — RIL misclassifies a CDE-owned term as neutral

**Vector.** RIL is asked to decide whether `final_decision` is neutral.
Misclassification produces a finding with empty owners and an empty repair
suggestion, then FRE happily proposes the same term as the replacement.

**Result.** RIL does not classify. The interpretation packet copies
`canonical_owners`, `cluster`, and `suggested_replacements` directly from
the scan record. The scan record is produced by the existing
`authority_shape_preflight` library, whose vocabulary clusters are the
canonical truth. RIL adds the unsafe-repair list and the
`canonical_authority_source` pointer without altering the cluster mapping.

**Classification.** observation.

## Attack 5 — FRE proposes a replacement outside the neutral vocabulary

**Vector.** FRE attempts to invent a replacement (e.g. `promotion_verdict`)
under the guise of a vocabulary swap.

**Result.** The TPA validator collects approved terms from the vocabulary
clusters' `advisory_replacements`, the `safe_rename_pairs.to` field, and
the neutral-vocabulary `neutral_replacements` table. A proposed symbol
that is not in this set and that does not have a safety suffix fails the
neutral-vocabulary rule. Test:
`test_tpa_rejects_non_neutral_proposed_symbol`.

**Classification.** must_fix → addressed.

## Attack 6 — PQX scope expansion

**Vector.** The scan or repair targets files outside the changed file set.

**Result.** Two defenses:

- The scan defers changed-file resolution to the canonical
  `resolve_changed_files` helper, which is fail-closed.
- TPA computes `target_files - changed_files` and emits
  `out_of_scope_target_files` if anything leaks. Per-replacement
  `replacement_outside_changed_files` is also emitted. Test:
  `test_tpa_rejects_replacement_outside_changed_files`.

**Classification.** must_fix → addressed.

## Attack 7 — Scanner ignores docs or tests

**Vector.** The scanner could be tricked into ignoring MET-owned docs (the
common HOP failure surface) by leaning on the vocabulary's
`excluded_path_prefixes` list.

**Result.** The vocabulary scope places `docs/` in
`default_scope_prefixes`, so docs are scanned by default. Only `tests/`,
`outputs/`, `artifacts/`, `runs/`, and similar volatile prefixes are
excluded — those are the same prefixes the binding preflight uses; ASF-01
does not weaken them and does not introduce new exclusions. Test:
`test_changed_scope_scan_detects_authority_terms_in_met_docs`.

**Classification.** observation. Tests intentionally remain out of scope
for the scanner because tests must be able to assert forbidden tokens to
exercise the guards.

## Attack 8 — Status escalation in the candidate

**Vector.** A pipeline upgrades `status` from `proposed` to `applied` to
imply authorization.

**Result.** TPA rejects any non-`proposed` status with
`non_proposed_status` and the record fails. Test:
`test_tpa_rejects_non_proposed_status`.

**Classification.** must_fix → addressed.

## Attack 9 — Strip required `prohibited_actions`

**Vector.** Candidate omits `no_owner_registry_change` to leave the door
open for a downstream registry edit.

**Result.** TPA rejects any candidate missing the required prohibited
actions. Test:
`test_tpa_rejects_missing_required_prohibited_actions`.

**Classification.** must_fix → addressed.

## Attack 10 — Wrapper auto-application

**Vector.** A pipeline runs the wrapper with `--apply` to mutate source.

**Result.** The wrapper deliberately exposes no apply flag; the apply
surface does not exist in ASF-01. The wrapper writes only to the
`outputs/authority_shape_preflight/` artifact directory, never to source
files.

**Classification.** observation.

## Summary

| # | Attack                                                   | Severity     | Status                                |
| - | -------------------------------------------------------- | ------------ | ------------------------------------- |
| 1 | Edit authority registry via candidate                    | observation  | Defended (forbidden target prefixes)  |
| 2 | Add allowlist exception via candidate                    | observation  | Defended (forbidden intent fields)    |
| 3 | Change meaning instead of vocabulary                     | must_fix     | Fixed (vocabulary_only + neutral set) |
| 4 | RIL misclassifies CDE term                               | observation  | Defended (RIL is non-deciding)        |
| 5 | FRE invents replacement outside neutral vocabulary       | must_fix     | Fixed (TPA neutral-vocabulary check)  |
| 6 | PQX scope expansion (rewrites outside changed files)     | must_fix     | Fixed (scope check)                   |
| 7 | Scanner ignores docs/tests                               | observation  | Defended (docs in scope, tests by design) |
| 8 | Status escalated past `proposed`                         | must_fix     | Fixed (status check)                  |
| 9 | Strip required prohibited_actions                        | must_fix     | Fixed (required-action check)         |
| 10 | Wrapper auto-application                                | observation  | Defended (no apply surface)           |

All `must_fix` findings are addressed in this PR. Remaining items are
recorded as observations because the existing implementation already
defends them.
