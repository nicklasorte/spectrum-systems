# ASF-01 Red-team Fixes

Tracks every `must_fix` finding from
`ASF-01-authority-shape-feedback-loop-redteam.md` and the corresponding
implementation in this PR.

## Fix #3 — Change meaning instead of vocabulary

**Finding.** A repair candidate could carry a structural rewrite while
labelling it a vocabulary swap.

**Fix.** TPA validator (`scripts/validate_authority_repair_candidate.py`)
enforces two checks:

- `replacement_class` must equal `vocabulary_only`. Any other value emits
  `non_vocabulary_only_replacement` and the record fails.
- `proposed_symbol` must come from the approved neutral vocabulary
  (advisory replacements + safe-rename targets + neutral-vocabulary
  replacements + safety-suffix tokens). Anything else emits
  `non_neutral_replacement`.

In addition, the candidate's `status` is locked to `proposed`, so even a
permissive swap cannot cross into application without a separate, future
authorized command.

**Files changed.**
- `scripts/validate_authority_repair_candidate.py` (new)
- `contracts/schemas/authority_shape_repair_candidate.schema.json` (new)

**Tests added.**
- `tests/governance/test_authority_shape_feedback_loop.py::test_tpa_rejects_non_vocabulary_only_replacement`
- `tests/governance/test_authority_shape_feedback_loop.py::test_tpa_rejects_non_neutral_proposed_symbol`

**Residual risk.** The TPA cannot detect a semantic change inside a
vocabulary-only swap (e.g., flipping `passed_gate` to `failed_gate`). This
is acknowledged: the scope of ASF-01 is vocabulary, not behaviour. Behaviour
diffs remain the responsibility of the existing CI evaluation gates.

## Fix #5 — FRE invents a replacement outside the neutral vocabulary

**Finding.** FRE could propose an arbitrary identifier as the replacement.

**Fix.** TPA validator computes the approved neutral set from the existing
`authority_shape_vocabulary.json` (advisory replacements + safe-rename
targets) and `authority_neutral_vocabulary.json` (neutral_replacements).
Any proposed symbol not in this set, and lacking a safety-suffix token
(`signal`, `observation`, `input`, `recommendation`, …), fails. The vocabulary
files themselves are unchanged in this PR.

**Files changed.**
- `scripts/validate_authority_repair_candidate.py` (new)

**Tests added.**
- `tests/governance/test_authority_shape_feedback_loop.py::test_tpa_rejects_non_neutral_proposed_symbol`

**Residual risk.** Approved-set growth still requires governed adoption of
the vocabulary files. ASF-01 does not extend the vocabulary.

## Fix #6 — PQX scope expansion

**Finding.** Repair could target a file outside the changed-file set.

**Fix.** Three layers:

- The early scan inherits the changed file set from the canonical
  `resolve_changed_files` helper, which is fail-closed and rejects
  working-tree-only inspection.
- TPA validator checks `target_files - scan_record.changed_files` and
  emits `out_of_scope_target_files` if anything leaks. Per-replacement
  paths are also matched against the changed set with
  `replacement_outside_changed_files`.
- The candidate carries a `prohibited_actions` field with the required
  entry `no_cross_file_rewrite_without_evidence`.

**Files changed.**
- `scripts/run_changed_scope_authority_scan.py` (new, calls the canonical resolver)
- `scripts/validate_authority_repair_candidate.py` (new)

**Tests added.**
- `tests/governance/test_authority_shape_feedback_loop.py::test_tpa_rejects_replacement_outside_changed_files`

**Residual risk.** None within ASF-01. Repository-wide rewrites would
require a separate authorized command, which is not introduced by this
PR.

## Fix #8 — Status escalation past `proposed`

**Finding.** A pipeline could upgrade `status` to `applied` to imply
authorization.

**Fix.** TPA rejects any candidate where `status != "proposed"` with
`non_proposed_status`. The repair-candidate schema additionally constrains
`status` to the literal enum `["proposed"]`, so even a malformed candidate
fails schema validation. The `non_authority_assertions` field
(`proposal_only`, `no_application`) is carried explicitly.

**Files changed.**
- `scripts/validate_authority_repair_candidate.py` (new)
- `contracts/schemas/authority_shape_repair_candidate.schema.json` (new)

**Tests added.**
- `tests/governance/test_authority_shape_feedback_loop.py::test_tpa_rejects_non_proposed_status`

**Residual risk.** None within the ASF-01 envelope. Authorization remains
with CDE.

## Fix #9 — Strip required `prohibited_actions`

**Finding.** A candidate could omit `no_owner_registry_change` to leave
room for downstream registry edits.

**Fix.** TPA enforces a required-set check:
`{no_allowlist_change, no_owner_registry_change,
no_cross_file_rewrite_without_evidence}` must all be present. Anything
missing emits `missing_prohibited_actions`. The schema also requires at
least three entries from the closed enum.

**Files changed.**
- `scripts/validate_authority_repair_candidate.py` (new)
- `contracts/schemas/authority_shape_repair_candidate.schema.json` (new)

**Tests added.**
- `tests/governance/test_authority_shape_feedback_loop.py::test_tpa_rejects_missing_required_prohibited_actions`

**Residual risk.** None.

## Cross-cutting residual risks

- ASF-01 is upstream of CI. If the CI binding gates were ever removed, the
  early loop alone would not be sufficient. This PR does not modify the CI
  gates, so the binding remains intact.
- The TPA validator inspects intent fields by name. Future intent fields
  with different names would not be detected automatically; the closed
  schema enum on `prohibited_actions` mitigates this for the common cases.
