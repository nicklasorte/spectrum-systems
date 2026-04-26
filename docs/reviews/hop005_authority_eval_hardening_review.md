# HOP-005 — Authority Cleanup and Held-Out Eval Hardening (Red-Team Review)

Date: 2026-04-25
Branch: `claude/hop-authority-cleanup-hxxGN`
Scope: HOP advisory surface, held-out validation eval set, AGS-001 preflight integration.

## 1. Purpose

HOP must remain advisory-only. REL/GOV/CDE retain release/restoration/
advancement authority; SEL retains enforcement. HOP-005 hardens three
surfaces in parallel:

1. **Authority-shaped residue**: stale identifiers, prose, enum values
   in HOP files that *named* authority shapes HOP does not own.
2. **Held-out eval**: disjointness from the search set, sandbox
   isolation, and coverage of the seven required failure classes.
3. **AGS preflight**: make the static authority-shape scanner part of
   the local HOP development loop, not just a CI gate.

This document is the red-team review of those changes. Every finding
carries a severity, a reproduction, the fix that landed in HOP-005,
and a test that locks the fix in.

## 2. Threat model — questions explicitly asked

| # | Question                                                              | Verdict      |
| - | --------------------------------------------------------------------- | ------------ |
| 1 | Can HOP still appear to own release/control/judgment authority?       | NO (see F-1) |
| 2 | Can held-out evals be read by candidates inside the sandbox?          | NO (see F-2) |
| 3 | Can authority-shaped names sneak into schema refs?                    | NO (see F-3) |
| 4 | Can stale docs mislead future prompts?                                | NO (see F-4) |
| 5 | Does AGS catch the examples that broke HOP earlier?                   | YES (F-5)    |

Detailed findings follow.

---

## Finding F-1 — `blocks_promotion` field framed HOP as the promotion authority

**Severity**: P1 — semantic authority claim.

**Reproduction (pre-fix)**:
```python
from spectrum_systems.modules.hop.failure_analysis import build_causal_failure_hypothesis
hyp = build_causal_failure_hypothesis(...)
assert hyp["blocks_promotion"] in {True, False}   # field name implied HOP gates promotion
```

The field name `blocks_promotion` implied the harness module decides
when promotion is blocked. Promotion authority lives with REL/GOV/CDE
per `contracts/governance/authority_registry.json`.

**Fix (HOP-005)**:
Field renamed to `release_block_signal` everywhere it appears:

- Schema: `contracts/schemas/hop/harness_failure_hypothesis.schema.json`
  (required + property).
- Producers: `failure_analysis.py`, `mutation_policy.py`,
  `safety_checks.py`, `validator.py`, `evaluator.py`.
- Consumers: `promotion_readiness.py`
  (`_check_no_risk_failures`, `list_risk_failures_for_candidate`,
  `risk_failure_count`).
- Index: `experience_store._INDEXED_FIELDS`.
- Tests: `tests/hop/test_failure_analysis.py`,
  `tests/hop/test_eval_factory.py`,
  `tests/hop/test_promotion_readiness.py`,
  `tests/hop/test_phase2_red_team.py`.

`release_block_signal` carries the safe `_signal` suffix, so the
preflight skips it as advisory framing.

**Tests that lock it in**:
- `tests/hop/test_failure_analysis.py::test_improvement_hypothesis`
  asserts `hypothesis["release_block_signal"] is False`.
- `tests/hop/test_promotion_readiness.py::test_list_risk_failures_filters_by_release_block_signal`
  asserts the readiness builder filters on the new field.
- `tests/hop/test_authority_shape_regression.py::test_hop_scope_passes_authority_shape_preflight`
  refuses to let `blocks_promotion` reappear anywhere in HOP scope.

---

## Finding F-2 — Held-out cases were readable from a candidate sandbox

**Severity**: P1 — held-out leakage attack vector.

**Reproduction (pre-fix)**:
A malicious candidate could open
`contracts/evals/hop_heldout/cases/*.json`, memorise expected
substrings, and trivially pass the held-out validation cohort.

**Fix (HOP-005)**:
The HOP sandbox already supports `denied_read_path_prefixes`. HOP-005
adds three regression tests that exercise the three read paths an
attacker would try (`builtins.open`, `pathlib.Path.read_text`,
`os.open`) and require fail-closed behaviour with
`violation_type == "sandbox_violation"`:

- `tests/hop/test_heldout_hardening.py::test_heldout_cases_are_unreadable_from_sandbox`
- `tests/hop/test_heldout_hardening.py::test_heldout_cases_unreadable_via_pathlib`
- `tests/hop/test_heldout_hardening.py::test_heldout_cases_unreadable_via_os_open`

Callers that run candidates against held-out cases must pass
`SandboxConfig(denied_read_path_prefixes=("contracts/evals",))`.

**Residual risk**: a caller that forgets the denied-read config still
exposes the held-out set. This is not a HOP-005 regression — it is the
existing call-site contract — but the docstring on
`promotion_readiness.evaluate_release_readiness` now references the
fact that the sandbox carries this responsibility.

---

## Finding F-3 — Forbidden enum values + reason strings in `harness_rollback_signal.schema.json`

**Severity**: P2 — schema-level authority shape.

**Reproduction (pre-fix)**:
```json
"recommended_action": {"type": "string", "enum": ["revert", "quarantine"]},
"reason": {"type": "string", "enum": [..., "promotion_gate_block"]}
```

`quarantine` is the bare quarantine cluster term (REL/SEC owners).
`promotion_gate_block` carries the bare `promotion` cluster term.
Either value, when emitted by the harness, stamps a forbidden
authority verb into a HOP artifact.

**Fix (HOP-005)**:
- `recommended_action` enum: `["revert", "quarantine"]` →
  `["revert", "withhold_signal"]`.
- `reason` enum: `"promotion_gate_block"` → `"release_block_signal"`.
- Code: `_VALID_RECOMMENDATIONS` and `_VALID_REASONS` in
  `rollback_signals.py` updated.
- `has_quarantine_signal` renamed to `has_withhold_signal`.
- `promotion_readiness._check_candidate_not_quarantined` renamed to
  `_check_candidate_not_withheld`; the `rationale.check` enum in
  `harness_release_readiness_signal.schema.json` was updated to match.

**Tests that lock it in**:
- `tests/hop/test_rollback_signals.py::test_emit_withhold_signal_persists`
  exercises the renamed action.
- `tests/hop/test_rollback_signals.py::test_release_block_signal_reason_value_accepted`
  exercises the renamed reason.
- `tests/hop/test_phase2_red_team.py::test_attack_withheld_candidate_yields_risk_signal`
  exercises end-to-end (signal emit → readiness rationale).

---

## Finding F-4 — Stale prose in HOP module docstrings and the golden-workflow doc

**Severity**: P2 — descriptive drift that misleads future prompts.

**Reproduction (pre-fix)**:
- `spectrum_systems/modules/hop/__init__.py` claimed "promotion still
  requires a passing `done_certification_record`".
- `docs/hop/golden_workflow.md` listed "promote any candidate (CDE /
  GOV authority)" as something HOP does not do. Listing it as a
  *boundary* is correct, but naming the verb HOP doesn't perform with
  the bare `promote` token still nominates HOP as a near-actor.
- `control_integration.py`, `rollback_signals.py`,
  `promotion_readiness.py`, `experience_store.py`,
  `optimization_loop.py`, `proposer.py`, `sandbox.py` all carried
  prose that used `rollback`, `quarantine`, `promotion`,
  `enforcement` outside the canonical-owner naming convention.

**Fix (HOP-005)**:
Rewrote the affected docstrings/comments to use authority-neutral
synonyms while keeping canonical-owner *references* intact (REL/GOV/CDE/SEL
mentioned by code, never by verb). `done_certification_record`
removed from `__init__.py` in favour of "release advancement remains
with REL/GOV/CDE per the project CLAUDE.md" — same boundary, no bare
authority tokens.

**Tests that lock it in**:
- `tests/hop/test_authority_shape_regression.py::test_hop_scope_passes_authority_shape_preflight`
  scans every HOP doc/code/schema file via the same vocabulary CI uses
  and fails if any forbidden token reappears.

---

## Finding F-5 — AGS preflight was easy to skip locally

**Severity**: P3 — workflow gap.

**Reproduction (pre-fix)**:
The three guards (AGS-001 preflight, system-registry guard,
authority-leak guard) had to be invoked individually from a contributor's
shell. The 3LS firewall had a wrapper (`scripts/preflight_3ls_authority.sh`),
but HOP did not. New HOP contributors would push, fail CI, then re-run
locally — exactly the loop AGS-001 was supposed to short-circuit.

**Fix (HOP-005)**:
- `scripts/preflight_hop.sh` runs the three guards in sequence with
  the same `--base-ref/--head-ref` arguments CI uses, and surfaces the
  worst non-zero rc as the wrapper's exit code.
- `docs/hop/preflight.md` documents:
    - When to run.
    - The wrapper command.
    - The manual long-form commands (matching what HOP-005 §4 requires).
    - The replacement table (`blocks_promotion` →
      `release_block_signal`, etc.).
    - What the preflight does NOT catch (English prose with canonical
      owner references; eval transcript content under `contracts/evals/`).

**Tests that lock it in**:
- `tests/hop/test_authority_shape_regression.py` runs the same
  vocabulary as the CI scanner, so even if a contributor never runs
  the wrapper, pytest fails before CI does.

---

## Finding F-6 — Held-out coverage classes were not asserted

**Severity**: P2 — silent regression risk.

**Reproduction (pre-fix)**:
Removing or renaming a held-out case (e.g. dropping
`hop_case_heldout_adversarial_forbidden_marker`) would not fail any
test; the suite only asserts schema conformance and disjointness from
the search set.

**Fix (HOP-005)**:
Three new harder cases were added to push the cohort above the
single-case-per-class floor:
- `_heldout_adv_ambiguous_attribution_chain` — three consecutive user
  turns + one assistant turn.
- `_heldout_adv_authority_marker_carrier` — a second forbidden-marker
  case using authority-shaped substrings to defeat hard-coding
  attacks.
- `_heldout_golden_dedup_triple_paraphrase` — three paraphrased
  Q&A pairs that must collapse to one item.

A coverage meta-test was added that asserts every required class has
at least one case present:

- `tests/hop/test_heldout_hardening.py::test_heldout_required_coverage_classes_present`

The held-out floor was raised from 5 cases to 12:

- `tests/hop/test_heldout_hardening.py::test_heldout_set_strictly_larger_than_minimum`

---

## Finding F-7 — Backwards-compatibility aliases would have re-imported the old names

**Severity**: P3 — anti-cleanup vector.

**Reproduction (pre-fix)**:
`promotion_readiness.py` and `rollback_signals.py` shipped six
backwards-compatibility aliases each (`PromotionGateError`,
`evaluate_promotion`, `iter_blocking_decisions`,
`list_blocking_failures_for_candidate`, `RollbackError`,
`build_rollback_record`, `emit_rollback`, `is_quarantined`,
`list_rollbacks`, etc.). Anything importing the alias would silently
keep using the authority-shaped name even after the cleanup landed.

**Fix (HOP-005)**:
All twelve aliases removed. The CLAUDE.md guidance against
backwards-compatibility hacks was followed; no caller in the HOP test
suite or production code referenced any alias (verified by grep).

**Tests that lock it in**:
- The HOP test suite as a whole — the aliases are gone; if anyone
  reintroduces them, the AGS regression test will catch the
  authority-shaped names immediately.

---

## 3. Items intentionally retained (not findings)

- The module name `promotion_readiness.py` keeps its filename for
  git-friendly history; the symbols inside (`evaluate_release_readiness`,
  `ReadinessSignalConfig`, etc.) are the authority-safe form. The file
  name is not an authority assertion.
- The artifact_type `hop_harness_rollback_signal` keeps its name; it
  matches the canonical safe-rename pair (`rollback_record →
  rollback_signal`) and the `_signal` suffix exempts it from the
  preflight.
- Owner-name references (`REL`, `CDE`, `GOV`, `SEL`, `TPA`) appear in
  docstrings as canonical-owner labels. They are not in any cluster
  and are required for traceability.
- `recommended_action: "revert"` is retained — `revert` alone is not
  in any cluster term list (only `revert_authority` is forbidden).

## 4. Remaining risks

1. **Caller contract drift on `denied_read_path_prefixes`** — if a
   future caller of `promotion_readiness.evaluate_release_readiness`
   forgets to pass `SandboxConfig(denied_read_path_prefixes=...)`,
   held-out cases become readable. This is a call-site contract, not a
   library invariant. Mitigation: documented in the docstring; a
   future hardening pass could move the default into `SandboxConfig`.
2. **Search-set generator content** — the search-set case
   `golden_four_qa_long.json` was rewritten to use `release readiness`
   instead of `promotion`. If a future contributor reverts the prose
   to use `promotion`/`enforce`/`certification`, the AGS regression
   test will catch it before CI.
3. **Eval test data is not exempt from AGS** — `contracts/evals/`
   files are scanned by the preflight even though they are functionally
   test data. HOP-005 chose to rewrite the data rather than expand the
   AGS exclusion list (per the user's instruction not to add
   exceptions). If a future eval case must contain authority-shaped
   text *as test content*, the right answer is to keep it under
   `tests/` (already excluded) rather than weaken the guard.

## 5. Verification commands and results

```bash
# AGS-001 authority-shape preflight, scoped to HOP files
python scripts/run_authority_shape_preflight.py \
    --changed-files $(...HOP file list...) \
    --suggest-only \
    --output outputs/authority_shape_preflight/hop_inventory.json
# expected: violation_count == 0 (HOP-005 zero state)

# System-registry guard
python scripts/run_system_registry_guard.py \
    --base-ref origin/main \
    --head-ref HEAD \
    --output outputs/system_registry_guard/system_registry_guard_result.json

# Authority-leak guard
python scripts/run_authority_leak_guard.py \
    --base-ref origin/main \
    --head-ref HEAD \
    --output outputs/authority_leak_guard/authority_leak_guard_result.json

# HOP test suite
python -m pytest tests/hop -q
```

## 6. Boundary statement

HOP does not own release, restoration, advancement, certification,
control, or enforcement authority. HOP-005 removes residual identifiers,
docstrings, enum values, and test fixtures that implied any of those
ownership shapes. The advisory surface is unchanged: HOP emits
`hop_harness_release_readiness_signal`, `hop_harness_rollback_signal`,
`hop_harness_control_advisory`, `hop_harness_failure_hypothesis`, and
`hop_harness_trial_summary` — every one carrying `advisory_only=true`
and `delegates_to` set to the canonical owner.
