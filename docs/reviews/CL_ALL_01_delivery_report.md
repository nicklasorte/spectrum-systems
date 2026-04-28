# CL-ALL-01 Delivery Report — Core Loop Compression

## 1. Intent

CL-ALL-01 is the next-phase compression of the canonical core loop:

```
AEX → PQX → EVL → TPA → CDE → SEL
```

The phase replaces ad-hoc loop language with a machine-checkable contract,
locks every adjacent handoff, and produces one compact proof artifact for
every pass / block / freeze scenario. Every change either prevents a
concrete failure or improves a measurable signal. CL is a roadmap label,
**not** a new top-level 3-letter system.

Optimised for debuggability:

* one primary canonical reason per block / freeze;
* supporting reasons preserved alongside;
* per-stage artifact references and per-transition status;
* deterministic precedence (admission → execution → eval → policy →
  decision → action) so reasoning is identical across runs.

## 2. Architecture

CL ships eight pure validator / builder modules and two thin CLIs. All
modules are non-owning support seams under
`spectrum_systems/modules/governance/`. They never decide, gate, or
enforce. Authority remains with AEX, PQX, EVL, TPA, CDE, SEL.

```
contracts/schemas/core_loop_contract.schema.json   ← meta-contract
contracts/schemas/core_loop_proof.schema.json      ← proof artifact

contracts/governance/primary_reason_policy.json
contracts/governance/sel_action_mapping_policy.json
contracts/governance/tpa_policy_input_contract.json
contracts/governance/cde_decision_input_contract.json

spectrum_systems/modules/governance/
  core_loop_contract.py
  core_loop_admission_minimality.py
  core_loop_execution_envelope.py
  core_loop_required_eval_resolver.py
  core_loop_policy_input_contract.py
  core_loop_decision_input_contract.py
  core_loop_action_mapping.py
  core_loop_primary_reason.py
  core_loop_proof.py

scripts/validate_core_loop_contract.py
scripts/print_core_loop_proof.py
```

## 3. Systems touched

| System | Role | Touched? |
|--------|-------|---------|
| AEX    | admission authority             | Validation surface added (admission minimality + bypass detector). No authority change. |
| PQX    | execution authority             | Execution envelope validator + drift detector. No authority change. |
| EVL    | required-eval authority         | Required-eval resolver. No authority change. |
| TPA    | trust/policy authority          | Policy input contract surface. No authority change. |
| CDE    | control / closure authority     | Decision input contract surface. No authority change. |
| SEL    | enforcement authority           | Action-mapping consistency surface. No authority change. |
| GOV    | governance / certification      | Primary-reason policy + core-loop proof live as governance support. No authority change. |

Standards manifest, authority-shape vocabulary, and authority-leak
registry updated to register the new artifacts and protect the new
support files. No new top-level 3-letter system was added.

## 4. Authority boundaries preserved

* AEX retains admission authority; modules only **inspect** packets.
* PQX retains execution authority; modules only **validate** envelopes.
* EVL retains required-eval registry authority; modules only
  **classify** submitted evals against EVL’s declared catalog.
* TPA retains trust/policy authority; modules only **reject ungoverned
  inputs** that TPA must not consume.
* CDE retains control/closure authority; modules only **enforce the
  governed-input shape** that CDE accepts.
* SEL retains enforcement authority; modules only **detect mismatched
  CDE→SEL action pairs**.

Every new module declares `non_authority_assertions` with at least
`preparatory_only` plus the relevant `not_*_authority` tokens. The
authority-shape preflight reports zero violations, and the
authority-leak guard passes after the new files are listed in
`forbidden_contexts.excluded_path_prefixes`.

## 5. New / updated contracts

| Path | Kind | Purpose |
|------|------|---------|
| `contracts/schemas/core_loop_contract.schema.json` | schema | CL-01 meta-contract |
| `contracts/examples/core_loop_contract.json` | example | canonical instance |
| `contracts/schemas/core_loop_proof.schema.json` | schema | CL-25 proof |
| `contracts/examples/core_loop_proof.json` | example | passing instance |
| `contracts/governance/primary_reason_policy.json` | governance policy | CL-22 reason precedence |
| `contracts/governance/sel_action_mapping_policy.json` | governance policy | CL-19 CDE→SEL mapping |
| `contracts/governance/tpa_policy_input_contract.json` | governance policy | CL-13 TPA input contract |
| `contracts/governance/cde_decision_input_contract.json` | governance policy | CL-16 CDE input contract |
| `contracts/standards-manifest.json` | manifest | bumped to 1.3.152, registers CL artifacts |
| `contracts/governance/authority_shape_vocabulary.json` | guard config | adds CL files to guard path prefixes |
| `contracts/governance/authority_registry.json` | guard config | adds CL files to forbidden-context exclusions |

## 6. New / updated modules

| File | Role |
|------|------|
| `core_loop_contract.py` | meta-contract validator + handoff validator (CL-01 / CL-03) |
| `core_loop_admission_minimality.py` | AEX admission minimality + bypass detector (CL-04 / CL-06) |
| `core_loop_execution_envelope.py` | PQX envelope normaliser + drift validator (CL-07 / CL-09) |
| `core_loop_required_eval_resolver.py` | EVL deterministic eval-set classifier (CL-10 / CL-12) |
| `core_loop_policy_input_contract.py` | TPA policy-input contract validator (CL-13 / CL-15) |
| `core_loop_decision_input_contract.py` | CDE decision-input contract validator (CL-16 / CL-18) |
| `core_loop_action_mapping.py` | SEL action-mapping consistency (CL-19 / CL-21) |
| `core_loop_primary_reason.py` | primary-reason precedence selector (CL-22 / CL-24) |
| `core_loop_proof.py` | core loop proof builder (CL-25) |

## 7. New / updated CLIs

| Script | Use |
|--------|-----|
| `scripts/validate_core_loop_contract.py` | Validate a core_loop_contract artifact; exit 0 = ok, 1 = violations, 2 = parse error. |
| `scripts/print_core_loop_proof.py` | Render a core_loop_proof artifact; exit 0 = pass, 1 = block / freeze, 2 = corrupt. |

## 8. Red-team scenarios

For every step CL-02 / CL-05 / CL-08 / CL-11 / CL-14 / CL-17 / CL-20 /
CL-23 / CL-26, an adversarial test asserts a specific fail-closed
behaviour with a stable canonical reason code.

| Step | Adversary | Expected | Reason code |
|------|-----------|----------|-------------|
| CL-02 | corrupt every adjacent transition | block before downstream | `CORE_LOOP_HANDOFF_MISSING_FIELD` / `CORE_LOOP_HANDOFF_MISSING_REF` / `CORE_LOOP_HANDOFF_OUT_OF_ORDER` |
| CL-05 | direct PQX entry without admission | block | `ADMISSION_BYPASS_ATTEMPT` |
| CL-08 | missing trace_id, output_hash, input_refs, run_id mismatch, unreplayable envelope | block | `EXECUTION_*` |
| CL-11 | duplicate / unsupported / missing / required-as-optional / optional-as-required evals | block | `EVAL_*` |
| CL-14 | dashboard / narrative / hidden / undocumented input to TPA | block | `POLICY_*` |
| CL-17 | free-text / dashboard / runbook / stale / missing-TPA decision input | block / freeze | `DECISION_*` |
| CL-20 | promote-on-block, no-op-on-freeze, retry-on-policy-mismatch, mutation-without-allow, repair-without-authorization | block | `ACTION_*` |
| CL-23 | reason flood across all six stages | deterministic admission > execution > eval > policy > decision > action | precedence stable |
| CL-26 | full loop drill: clean pass, every per-stage block, decision freeze, SEL action block, corrupted transition, stale proof, conflicting proof | exact terminal status + primary reason per scenario | full reason matrix |

## 9. Fix passes

Each red-team step has a paired fix-pass commit and a regression test:

* CL-03 — handoff validator rejects malformed transitions.
* CL-06 — admission minimality refuses bypass attempts.
* CL-09 — envelope validator emits stable drift reasons.
* CL-12 — eval resolver builds an eval summary with `healthy | blocked` status.
* CL-15 — policy-input validator rejects ungoverned inputs.
* CL-18 — decision-input validator rejects free-text / dashboard /
  runbook / stale / missing-TPA inputs and unknown decision outcomes.
* CL-21 — action-mapping validator rejects every forbidden CDE→SEL pair.
* CL-24 — primary-reason policy emits stable precedence and preserves
  supporting reasons.
* CL-27 — final fix pass: full-loop red team passes; prior OC / NT /
  NS / NX suites still pass.

## 10. Failure modes prevented

* Authority drift: support modules cannot decide / gate / enforce.
* Silent fallback: every block / freeze emits exactly one canonical
  primary reason plus supporting reasons; no scenario returns "ok"
  while a stage is missing.
* Unsupported allow: SEL action mapping rejects allow-on-block,
  noop-on-freeze, retry-on-policy-mismatch, repair-without-authorization.
* Hidden policy input: TPA inputs are restricted to a bounded set;
  dashboard / narrative / hidden state are explicitly forbidden.
* Free-text closure: CDE decision inputs are restricted to governed
  artifact references; runbook / dashboard / free-text rationales are
  rejected.
* Execution drift: missing trace_id, missing output_hash, missing
  input_refs, run-id mismatch, and unreplayable envelopes block
  before downstream stages.
* Eval-set confusion: duplicates, unsupported names, optional-as-required
  and required-as-optional now have stable reason codes.

## 11. Measurable signals improved

* **Primary-reason determinism** — for any block / freeze, the elected
  primary reason is reproducible across runs (CL-23 regression).
* **Trace continuity coverage** — `core_loop_proof.trace_continuity_ok`
  is a single boolean derived from per-transition status; no implicit
  derivation.
* **Stage coverage** — every proof carries six stage records and five
  transition records; missing stages surface as `missing` not absent.
* **Replay/lineage attachment** — proof artifact carries
  `replay_record_ref` and `lineage_chain_ref` for every scenario.
* **Reason-code inventory** — every core-loop reason code is registered
  by precedence class in `primary_reason_policy.json`.

## 12. Reason-code inventory

`contracts/governance/primary_reason_policy.json#canonical_reason_codes`:

* admission: `ADMISSION_MISSING`, `ADMISSION_CLASS_UNKNOWN`,
  `ADMISSION_CLASS_MISSING`, `ADMISSION_BYPASS_ATTEMPT`,
  `ADMISSION_REPO_MUTATION_WITHOUT_PROOF`.
* execution: `EXECUTION_ENVELOPE_MISSING`, `EXECUTION_TRACE_ID_MISSING`,
  `EXECUTION_RUN_ID_MISMATCH`, `EXECUTION_OUTPUT_HASH_MISSING`,
  `EXECUTION_INPUT_REFS_MISSING`, `EXECUTION_NOT_REPLAYABLE`.
* eval: `EVAL_REQUIRED_MISSING`, `EVAL_REQUIRED_FAILED`,
  `EVAL_DUPLICATE`, `EVAL_UNSUPPORTED_NAME`,
  `EVAL_OPTIONAL_MARKED_REQUIRED`, `EVAL_REQUIRED_MARKED_OPTIONAL`.
* policy: `POLICY_HIDDEN_INPUT`, `POLICY_DASHBOARD_ONLY_INPUT`,
  `POLICY_NARRATIVE_ONLY_INPUT`, `POLICY_UNGOVERNED_INPUT`,
  `POLICY_INPUT_MISSING`, `POLICY_INPUT_STALE`, `POLICY_RESULT_MISSING`.
* decision: `DECISION_INPUT_FREE_TEXT_ONLY`,
  `DECISION_INPUT_DASHBOARD_ONLY`, `DECISION_INPUT_RUNBOOK_ONLY`,
  `DECISION_INPUT_STALE_PROOF`, `DECISION_INPUT_MISSING_TPA`,
  `DECISION_INPUT_MISSING_EVAL`, `DECISION_INPUT_MISSING_EXECUTION`,
  `DECISION_FREEZE_REQUIRED`.
* action: `ACTION_PROMOTE_ON_BLOCK`, `ACTION_NOOP_ON_FREEZE`,
  `ACTION_RETRY_ON_POLICY_MISMATCH`, `ACTION_MUTATION_WITHOUT_ALLOW`,
  `ACTION_REPAIR_WITHOUT_AUTHORIZATION`,
  `ACTION_UNKNOWN_DECISION_MAPPING`.
* pass: `CORE_LOOP_PASS`.

## 13. Trace / replay guarantees

* `core_loop_proof.trace_id` and `run_id` propagate through every stage
  record and every transition record.
* `core_loop_proof.replay_record_ref` and `lineage_chain_ref` are
  required scalar fields; pass scenarios surface them, block / freeze
  scenarios surface `null` only when the upstream artifact is missing.
* Each transition validates the upstream stage’s required output ref
  (CL-01 transitions table); a failed transition fails closed and
  records the missing handoff fields.
* The contract validator and proof builder both fail closed on missing
  references — there is no silent fallback path.

## 14. Tests run

```
tests/test_cl_core_loop_contract.py
tests/test_cl_aex_admission_minimality.py
tests/test_cl_pqx_execution_envelope.py
tests/test_cl_evl_required_eval_resolver.py
tests/test_cl_tpa_policy_input_contract.py
tests/test_cl_cde_decision_input_contract.py
tests/test_cl_sel_action_mapping.py
tests/test_cl_primary_reason_policy.py
tests/test_cl_core_loop_proof.py
tests/test_cl_full_loop_redteam.py
```

10 new CL test modules, 141 test cases. All prior OC / NT / NS / NX
tests continue to pass.

## 15. Validation commands and results

| Command | Result |
|---------|--------|
| `python scripts/validate_system_registry.py` | `System registry validation passed.` |
| `python scripts/run_authority_shape_preflight.py --base-ref main --head-ref HEAD --suggest-only` | `violation_count: 0` |
| `python scripts/run_contract_enforcement.py` | `failures=0 warnings=0 not_yet_enforceable=0` |
| `python -m pytest tests/test_cl_*.py` | 141 passed |
| `python -m pytest tests/test_oc_*.py tests/test_nt_*.py tests/test_ns_*.py tests/test_nx_*.py tests/test_cl_*.py` | 647 passed |
| `python -m pytest --ignore=tests/transcript_pipeline -q` | 9692 passed, 2 skipped (after authority-leak guard exclusion update) |
| `python scripts/validate_core_loop_contract.py` | `core_loop_contract: ok=True` |
| `python scripts/print_core_loop_proof.py` | exit 0, pass scenario rendered |

## 16. Residual risks

* The TPA / CDE input contracts use a static allow-list; if a new
  governed upstream artifact is introduced, both contracts must be
  extended explicitly. The fail-closed behaviour ensures the new key is
  detected as ungoverned until allow-listed.
* The `proof_age_seconds` parameter for stale-proof detection is
  caller-supplied; no clock is embedded in the validator. Callers must
  source the age from a freshness audit (per existing
  `trust_artifact_freshness_policy.json`).
* Forbidden-pattern detection in `sel_action_mapping_policy.json` uses
  exact (decision, action) pairs. New SEL action verbs require a
  policy update before they can validate.
* The proof artifact intentionally embeds only references — operators
  must follow `lineage_chain_ref` and `replay_record_ref` to inspect
  the underlying records.

## 17. Follow-up recommendations

1. Wire `core_loop_proof` references into the existing
   `loop_proof_bundle` so an operator who opens an OC closure packet
   can pivot to the CL proof in one click.
2. Extend `print_core_loop_proof.py` with an optional
   `--sweep-directory` flag that batches over a directory of proof
   artifacts and surfaces per-scenario reason histograms.
3. Add a scheduled CI gate that runs
   `validate_core_loop_contract.py --path contracts/examples/core_loop_contract.json`
   on every PR touching the canonical contract artifact.
4. Capture the reason-code precedence table in the operator runbook
   so on-call engineers can map a primary reason to the next allowed
   action without reading the JSON policy.
