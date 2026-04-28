# AEX-FRE-AUTH-SHAPE-01 Delivery Report

## 1. Intent

Stop recurring authority-shape failures *before* they reach
`scripts/run_authority_shape_preflight.py` and
`scripts/run_system_registry_guard.py` in CI by adding a shift-left AEX
admission/preflight check and a bounded FRE repair-candidate generator
for protected authority vocabulary appearing in non-owner contexts.

The goal is purely shift-left. AEX, CDE, SEL, TPA, and the existing
preflight/registry-guard authority surfaces are unchanged. No new
top-level 3-letter system was added.

## 2. Failure pattern addressed

Recent PRs repeatedly passed pytest but failed late on:

* `scripts/run_authority_shape_preflight.py`
* `scripts/run_system_registry_guard.py`

with one of the following recurring causes:

* protected authority words (e.g. `decision`, `enforcement`, `approval`,
  `authority`, `governs`, `owns`, `controls`) used inside non-owner
  reports, schemas, examples, manifests, scripts, and docs;
* non-owner support artifacts registered in `contracts/standards-manifest.json`
  with authority-shaped names like `allow_decision_proof`;
* generated reports using protected headings (e.g. "Contract Enforcement
  Report") instead of evidence/compliance framing.

## 3. AEX admission behavior

A new module wraps the existing static authority-shape preflight and
adds context-kind classification so the same diagnostic surfaces with
fail-closed reason codes ready to drive a bounded repair.

* Module: `spectrum_systems/aex/authority_shape_admission.py`
* CLI: `scripts/run_authority_shape_admission.py`
* Vocabulary source: `contracts/governance/authority_shape_vocabulary.json`
* Owner mapping source: `contracts/governance/authority_registry.json`
  and the cluster `canonical_owners` declared in the vocabulary.

The CLI accepts `--base-ref`, `--head-ref`, `--changed-files`,
`--vocabulary`, `--output`, and `--suggest-only` and writes a JSON
artifact to:

```
outputs/authority_shape_admission/authority_shape_admission_result.json
```

It returns a non-zero exit when admission status is `block` and
`--suggest-only` is not provided, so PQX-equivalent execution cannot
proceed on unrepaired authority-shape leaks.

The scanner targets:

* `contracts/standards-manifest.json`
* `contracts/schemas/**`
* `contracts/examples/**`
* `contracts/governance/**`
* `docs/reviews/**`
* `docs/governance-reports/**`
* `scripts/**`
* `spectrum_systems/modules/**`

Detection layers added on top of the existing identifier scanner:

* JSON manifest/example string-value scan, gated by the existing safety
  suffix set and the standard `not_*_authority` non-authority disclaim
  pattern, so legitimate non-authority assertions still pass.
* Markdown report-heading scan keyed off the protected
  decision/enforcement/approval/authority/control/promotion/certification/
  rollback/release/quarantine cluster terms.
* Per-violation context classification:
  `manifest | schema | example | report | source | doc | script | unknown`.

The emitted artifact is `authority_shape_admission_result` with schema
`contracts/schemas/authority_shape_admission_result.schema.json`.

## 4. FRE repair behavior

A new module turns each blocking diagnostic into a bounded repair
candidate using only the vocabulary's safe-replacement table.

* Module: `spectrum_systems/fix_engine/authority_shape_repair.py`
* Schema: `contracts/schemas/authority_shape_repair_candidate.schema.json`

For each blocking diagnostic the candidate carries:

* exact `file` and `line` (and `json_path` when the diagnostic came from
  a JSON walk),
* `original_text` and `safe_replacement`,
* `replacement_rationale` referencing the canonical owner and cluster,
* `affected_downstream` (mirrors schema↔example pairs and standards
  manifest fan-out),
* `risk_level` (`low | medium | high`),
* `rename_kind` (`content_only | identifier_breaking | schema_breaking`),
* `required_tests` (always includes the existing preflight, the new
  admission, and the new FRE tests; manifest/schema diagnostics also
  pull in the regression pack and contract preflight),
* `candidate_status` (`ready | incomplete | rejected`).

FRE refuses to:

* propose a broad exclusion (`docs/**`, `scripts/**`, `**`, etc.) — the
  candidate is rejected with `broad_exclusion_rejected`;
* invent a safe replacement when the vocabulary cluster declares none —
  the candidate is marked `incomplete` with `missing_safe_replacement`;
* mark a non-owner support file as a canonical authority owner — the
  candidate is rejected with `owner_elevation_rejected`;
* auto-apply broad renames; FRE only proposes, control still owns the
  apply decision.

## 5. Artifacts emitted

| Artifact | Schema | Producer |
|----------|--------|----------|
| `authority_shape_admission_result` | `contracts/schemas/authority_shape_admission_result.schema.json` | AEX admission CLI / module |
| `authority_shape_repair_candidate` | `contracts/schemas/authority_shape_repair_candidate.schema.json` | FRE repair-candidate generator |

The existing `authority_shape_preflight_result` and
`system_registry_guard_result` artifacts are unchanged; the new admission
result is consumed *upstream* of them.

## 6. Fail-closed cases

Each case below produces a blocking admission diagnostic or a refused
repair candidate (covered by the test files listed in section 8):

* Unknown owner context: cluster has no canonical owner mapping → FRE
  candidate marked `incomplete` with `unknown_owner_context` reason code.
* Protected term in non-owner manifest entry → admission `block` with
  `protected_term_in_non_owner_manifest_entry`.
* Protected term in generated report title → admission `block` with
  `protected_term_in_generated_report_heading`.
* Protected term in non-owner module docstring → admission `block` with
  `protected_term_in_non_owner_module_docstring`.
* Repair candidate missing safe replacement → candidate `incomplete`
  with `missing_safe_replacement`.
* Repair candidate proposing broad exclusion → candidate `rejected`
  with `broad_exclusion_rejected`.
* Repair candidate trying to elevate a non-owner support file to an
  authority owner → candidate `rejected` with `owner_elevation_rejected`.

## 7. Red-team cases

Tests prove each red-team path:

| Case | Expected behavior | Test |
|------|-------------------|------|
| Manifest entry contains `allow_decision_proof` in non-owner context | AEX blocks; FRE proposes a safe replacement using the `decision` cluster vocabulary | `test_aex_authority_shape_admission.py::test_manifest_entry_with_allow_decision_proof_blocks` + `test_fre_authority_shape_repair.py::test_manifest_decision_candidate_proposes_safe_replacement` |
| Report heading "Contract Enforcement Report" | AEX blocks; FRE proposes "Contract Compliance Report" content-only | `test_aex_authority_shape_admission.py::test_report_heading_contract_enforcement_report_blocks` + `test_fre_authority_shape_repair.py::test_report_heading_candidate_is_content_only` |
| GOV docstring claims authority | AEX blocks; FRE proposes evidence/observation wording | `test_aex_authority_shape_admission.py::test_non_owner_docstring_claiming_ownership_blocks` |
| SEL/enforcement terms in non-SEL module | AEX blocks; FRE proposes downstream-action evidence wording | `test_aex_authority_shape_admission.py::test_sel_terms_in_non_sel_module_blocks` |
| Broad exclusion proposal `docs/**` | FRE rejects | `test_fre_authority_shape_repair.py::test_broad_exclusion_proposal_is_rejected` |
| Canonical owner file with legitimate protected term | AEX allows | `test_aex_authority_shape_admission.py::test_canonical_owner_file_with_protected_term_passes` |
| Unknown cluster/owner | AEX surfaces with `owner_context_allowed=false` | `test_aex_authority_shape_admission.py::test_unknown_owner_context_surfaces_in_diagnostics` |
| Repair candidate lacks tests / replacement | FRE marks `incomplete` | `test_fre_authority_shape_repair.py::test_missing_safe_replacement_produces_incomplete_candidate` |

The integration loop test
`tests/test_aex_fre_authority_shape_loop.py::test_admission_detects_then_fre_emits_bounded_candidate`
proves the end-to-end shift-left pipeline (AEX detect → FRE bounded
candidate with safe replacement and required tests, no auto-mutation).

## 8. Tests run

Focused new test files added:

* `tests/test_aex_authority_shape_admission.py` — 8 tests
* `tests/test_fre_authority_shape_repair.py` — 8 tests
* `tests/test_aex_fre_authority_shape_loop.py` — 3 tests

Validation commands run, all passing:

```
python scripts/run_authority_shape_admission.py --base-ref main --head-ref HEAD --suggest-only
python scripts/run_authority_shape_preflight.py --base-ref main --head-ref HEAD --suggest-only
python scripts/run_system_registry_guard.py --base-ref main --head-ref HEAD
python -m pytest tests/test_aex_authority_shape_admission.py \
                 tests/test_fre_authority_shape_repair.py \
                 tests/test_aex_fre_authority_shape_loop.py
python -m pytest tests/test_oc_*.py tests/test_nt_*.py tests/test_ns_*.py tests/test_nx_*.py
```

Trust suites (oc/nt/ns/nx) all pass: 506 tests. Combined AEX/FRE/preflight
test runs all pass: 97 tests.

The task description listed `tests/test_cl_*.py` as a trust suite, but no
test file matching that prefix exists in the repository. The other four
prefixes were run in full.

## 9. How this catches the issue earlier

Before this change:

```
PR change → pytest (passes) → run_authority_shape_preflight (CI fails)
                          → run_system_registry_guard (CI fails)
```

After this change:

```
PR change → AEX authority-shape admission scan
          → block before PQX
          → FRE bounded repair candidate (file/line/replacement/tests)
          → control approves narrow fix
          → PQX-equivalent applies fix
          → existing preflight + registry-guard remain green
```

The new admission CLI may be wired into any preflight wrapper that
already bundles `run_authority_shape_preflight.py` and
`run_system_registry_guard.py` (for example the existing
`scripts/run_shift_left_preflight.py` chain) — it is a simple,
stdlib-only entrypoint identical in calling style.

## 10. Confirmation no guardrails were weakened

* The existing `authority_shape_preflight` continues to fail closed on
  the same input (verified by
  `test_aex_fre_authority_shape_loop.py::test_preflight_still_flags_same_files_unchanged`).
* The existing `system_registry_guard` is unchanged; the admission
  artifact only sits upstream.
* The vocabulary file `contracts/governance/authority_shape_vocabulary.json`
  was not modified.
* The authority registry `contracts/governance/authority_registry.json`
  was not modified.
* The system registry `docs/architecture/system_registry.md` was not
  modified.
* No guard-path file was modified.
* The `--suggest-only` mode of the admission CLI exists for advisory
  shift-left runs; in `enforce` mode it returns non-zero, preserving
  fail-closed behavior.
* Repair candidates are advisory only — schema enforces
  `candidate_status ∈ {ready, incomplete, rejected}` (no `applied`
  state); FRE never auto-mutates the repo
  (`test_aex_fre_authority_shape_loop.py::test_repair_candidate_chain_is_advisory_only`).

## 11. Confirmation no new top-level 3-letter system was added

The implementation reuses existing system surfaces:

* AEX admission code lives under `spectrum_systems/aex/` (existing
  package).
* FRE repair code lives under `spectrum_systems/fix_engine/` (existing
  package).
* No new entry was added to the system registry; ownership of admission
  remains with AEX, repair-candidate generation remains with FRE, and
  enforcement/decision/control authority remains with SEL/CDE/TPA.
* No new directory beginning with a new 3-letter code was added; no new
  TPA/SEL/CDE/AEX-equivalent authority is introduced.

The only new files are:

* `spectrum_systems/aex/authority_shape_admission.py` (extends AEX)
* `spectrum_systems/fix_engine/authority_shape_repair.py` (extends FRE)
* `scripts/run_authority_shape_admission.py` (CLI)
* `contracts/schemas/authority_shape_admission_result.schema.json`
* `contracts/schemas/authority_shape_repair_candidate.schema.json`
* `tests/test_aex_authority_shape_admission.py`
* `tests/test_fre_authority_shape_repair.py`
* `tests/test_aex_fre_authority_shape_loop.py`
* `docs/reviews/AEX_FRE_AUTH_SHAPE_01_delivery_report.md` (this report)
