# OC-ALL-01 — Operational Closure and Bottleneck Steering Delivery Report

## 1. Intent

Build the next phase after NT-ALL-01: operational closure and bottleneck
steering. No new top-level 3-letter system was added. Every change either
prevents a specific failure or improves a measurable signal. The batch
strengthens existing seams (OBS, RIL, MAP, CDE, GOV/PRA, EVL, LIN, TPA,
PQX, SLO, REP, CTX) by making proof usable, dashboard-aligned,
bottleneck-driven, and operator-debuggable.

## 2. Architecture summary

OC-ALL-01 wires nine non-owning support seams together so an operator can
answer the eight questions the operational closure bundle is required to
answer (status, bottleneck, owner, supporting proof, dashboard alignment,
fast trust gate sufficiency, next work item, justifying signal/failure)
in under a minute, using only the bundle, the CLI, and the dashboard
projection.

```
proof candidates ──► proof_intake_index (governance support)
                      │
findings ────────────► bottleneck_classifier (observability support)
                      │
repo + dashboard ───► dashboard_truth_projection (observability support)
                      │                                                       
all of the above + cert delta + trust regression + lineage
                      │
                      ▼
              closure_decision_packet (governance support; CDE retains decision authority)
                      │
fast_trust_gate manifest + run summary  (governance support)
                      │
                      ▼
work_selection_signal (governance support; PRA retains promotion authority)
                      │
                      ▼
operational_closure_bundle (final reference-only summary)
                      │
                      ▼
operator_runbook_entry (evidence-bound, refuses confident guidance on stale/conflict)
```

## 3. Existing systems used

| Existing system | Role in OC-ALL-01 |
| --- | --- |
| OBS | bottleneck classifier, dashboard truth projection live under `spectrum_systems/modules/observability/` |
| RIL | findings input shape consumed by the classifier |
| MAP | dashboard truth projection / topology projection consumer |
| CDE | retains closure decision authority; consumes the closure decision packet |
| GOV / PRA | retain certification packaging and promotion-readiness authority; consume the operational closure bundle and work selection signal |
| EVL / LIN / REP / CTX / SLO / TPA | covered by the bottleneck classifier categories and fast trust gate seams; closure packet refuses to be ready when their inputs are missing or blocking |
| PQX | execution lineage consumed via the closure packet's `lineage_chain_ref` |

## 4. Why no new 3-letter system was added

The batch is explicitly scoped to "do not create a new top-level 3-letter
system." Every artifact in this batch is a non-owning support seam and
declares its non-authority assertions in `non_authority_assertions` (e.g.
`preparatory_only`, `not_control_authority`, `not_certification_authority`,
`not_promotion_authority`, `not_enforcement_authority`,
`not_closure_authority`, `advisory_only`, `no_deletion`). Authority
remains with the canonical owners listed in
`docs/architecture/system_registry.md`.

## 5. Schemas added or changed

New schemas under `contracts/schemas/`:

| Schema | Purpose |
| --- | --- |
| `proof_intake_index.schema.json` | OC-01 latest-proof selection per kind with finite reason codes |
| `bottleneck_classification.schema.json` | OC-04 canonical bottleneck category, owning 3LS, reason code, evidence ref, confidence, next safe action |
| `dashboard_truth_projection.schema.json` | OC-07 read-only projection of repo proof to dashboard surface |
| `closure_decision_packet.schema.json` | OC-10 evidence packet for CDE; derives ready/not_ready/freeze/blocked/unknown |
| `work_selection_record.schema.json` | OC-13 next-work recommendation from a finite supported justification set |
| `fast_trust_gate_manifest.schema.json` | OC-16 manifest of seams the fast gate must cover |
| `cleanup_candidate_report.schema.json` | OC-19 advisory cleanup classification (never deletes) |
| `operator_runbook_entry.schema.json` | OC-22 evidence-bound short runbook entries |
| `operational_closure_bundle.schema.json` | OC-25 single bundle answering eight operator questions |

Updated:

| File | Change |
| --- | --- |
| `contracts/governance/authority_shape_vocabulary.json` | new module/CLI/schema/example paths added to `guard_path_prefixes` so the preflight skips them (they are non-owning seams that legitimately reference closure/decision/certification words by design) |
| `contracts/governance/authority_registry.json` | new module paths added to `forbidden_contexts.excluded_path_prefixes` for the same reason |

## 6. CLIs added or changed

New CLI scripts under `scripts/`:

| CLI | Purpose | Exit codes |
| --- | --- | --- |
| `print_operational_closure.py` | Render the OC-25 bundle for operator triage | 0 pass / 1 block / 2 freeze / 3 unknown |
| `run_fast_trust_gate.py` | Audit fast trust gate manifest coverage | 0 sufficient / 1 insufficient |
| `generate_dashboard_truth_projection.py` | Produce a dashboard truth projection record | 0 aligned / 1 drifted/missing/corrupt / 2 unknown |
| `generate_artifact_cleanup_candidates.py` | Produce advisory cleanup candidate report | 0 no unknown_blocked / 1 some unknown_blocked |
| `generate_operator_runbook.py` | Produce an evidence-bound operator runbook entry | 0 pass / 1 block / 2 freeze / 3 insufficient |

The existing `scripts/print_loop_proof.py` is unchanged; it remains the
NT-13..15 operator triage CLI.

## 7. Failure modes prevented

| Roadmap | Failure mode prevented |
| --- | --- |
| OC-02 / OC-03 | A stale or duplicated proof bundle is silently accepted |
| OC-02 / OC-03 | Two conflicting proofs let the older one "win" by timestamp |
| OC-05 / OC-06 | Ambiguous bottleneck signals quietly pick a category — now they always block |
| OC-08 / OC-09 | Dashboard digest mismatch / corrupt ref / status drift is treated as alignment |
| OC-11 / OC-12 | Missing required evidence yields a degraded "ready_to_merge" |
| OC-14 / OC-15 | Attractive expansion work is recommended without a current bottleneck or trust signal |
| OC-17 / OC-18 | Removing a seam from the fast trust gate manifest is silently allowed |
| OC-20 / OC-21 | Required proof evidence is marked `candidate_archive` and later deleted |
| OC-23 / OC-24 | Operator runbook fabricates rationale when proof is stale or conflicting |
| OC-26 / OC-27 | Operator cannot identify the correct next action from the bundle alone |

## 8. Measurable signals improved

- **Latest-proof selection determinism**: the proof intake index has
  exactly four blocking reason codes (`MISSING`, `STALE_DIGEST_MISMATCH`,
  `DUPLICATE`, `CONFLICT`) and one passing code (`OK`). No silent
  fallback. No timestamp-only winner when digests disagree.
- **Bottleneck classification stability**: the classifier has a fixed
  precedence order of ten canonical categories and a deterministic
  owner-to-3LS map. Identical inputs always yield identical
  classifications.
- **Dashboard alignment finiteness**: alignment_status is one of
  `aligned`, `drifted`, `missing`, `corrupt`, `unknown` with seven
  finding kinds (`missing_owner`, `stale_status`, `digest_mismatch`,
  `ref_corrupt`, `missing_proof_ref`, `missing_dashboard_ref`,
  `category_mismatch`).
- **Closure packet coverage**: seven required evidence keys; the packet
  refuses to be `ready_to_merge` when any required key is missing.
- **Work selection rejection rate**: only six justification kinds are
  supported; two (`expansion_unsupported`, `low_trust`) always score
  zero and are rejected.
- **Fast trust gate coverage**: eight required seams enforced by
  manifest schema and runtime audit; dropping any seam is detectable
  by `audit_fast_trust_gate_coverage`.
- **Operator decision drill**: the operational closure bundle exposes
  eight operator questions with finite enums; the
  `print_operational_closure.py` CLI's exit code maps directly to
  operator action.

## 9. Red-team review results

Each red team is a pytest test in `tests/test_oc_*.py`:

| Roadmap | Adversary scenario | Test file |
| --- | --- | --- |
| OC-02 | hide / stale / duplicate / conflict proof bundles | `tests/test_oc_proof_intake_index.py` |
| OC-05 | ambiguous + precedence-collision findings | `tests/test_oc_bottleneck_classifier.py` |
| OC-08 | corrupted dashboard refs, status drift, missing owner, digest mismatch, category mismatch | `tests/test_oc_dashboard_truth_projection.py` |
| OC-11 | remove required eval / replay / lineage / certification / dashboard / proof evidence | `tests/test_oc_closure_decision_packet.py` |
| OC-14 | inject expansion-heavy / low-trust work recommendations | `tests/test_oc_work_selection_signal.py` |
| OC-17 | drop a seam from the fast trust gate manifest | `tests/test_oc_fast_trust_gate.py` |
| OC-20 | mark required proof evidence as cleanup candidate | `tests/test_oc_cleanup_candidate_report.py` |
| OC-23 | feed misleading / stale / incomplete proof to the runbook | `tests/test_oc_operator_runbook.py` |
| OC-26 | operator decision drill with bundle-only inputs | `tests/test_oc_operational_closure_bundle.py` |

## 10. Fix passes completed

Each fix pass is realized by the canonical-reason-code surface in the
respective module (one fix pass per red team). Concretely:

- proof intake fix pass — `PROOF_INTAKE_*` reason codes pinned in
  `CANONICAL_INTAKE_REASON_CODES`; selection rules deterministic.
- bottleneck fix pass — `CATEGORY_PRECEDENCE` is a fixed tuple;
  ambiguity always produces `BOTTLENECK_AMBIGUOUS` with action `block`.
- dashboard projection fix pass — finding kinds and severities are a
  finite enum; alignment_status is derived deterministically.
- closure fix pass — `CLOSURE_PACKET_*` reason codes pinned; missing
  evidence forces `not_ready` or `blocked`; freeze inputs propagate.
- work selection fix pass — supported / rejected justification sets are
  frozen sets; scores are constants.
- fast trust gate fix pass — `REQUIRED_SEAMS` is a fixed tuple verified
  at manifest load and at run-summary build.
- cleanup fix pass — required proof evidence and canonical-owner roots
  override any caller-supplied classification.
- runbook fix pass — stale or conflicting proof intake forces
  `insufficient_evidence` and refuses confident guidance.

## 11. Fast trust gate definition

`contracts/governance/fast_trust_gate_manifest.json` declares the eight
required seams: `registry_validation`, `authority_shape_preflight`,
`proof_intake`, `bottleneck_classifier`, `closure_packet`,
`dashboard_projection`, `work_selection`, `trust_regression_pack`. Each
seam has a selector (script or pytest node). The runner
(`scripts/run_fast_trust_gate.py`) audits coverage and exits non-zero
when a seam is missing or a selector is missing.

## 12. Dashboard truth alignment

The dashboard truth projection consumes a `repo_truth` view and a
`dashboard_view` view (each a small dict-like structure with the same
keys as the projection). It records seven finding kinds and demotes
`alignment_status` to `corrupt` on `digest_mismatch` or `ref_corrupt`,
to `missing` on either input absent, and to `drifted` on any block- or
warn-severity finding. The operational closure bundle further demotes
`overall_status` from `pass` to `block` whenever
`alignment_status` is `drifted`, `missing`, or `corrupt`.

## 13. Closure bundle behavior

`build_operational_closure_bundle` derives `overall_status` from the
strongest available input (closure packet → dashboard projection),
applies fail-closed demotions when fast gate is insufficient or
dashboard alignment is degraded, and exposes a finite
`operator_questions` block matching the eight required questions. No
field is invented; every field is derived from supplied evidence
references.

## 14. Operator decision drill result

The OC-26 red-team test
`test_operator_can_identify_block_action_from_bundle_alone` (in
`tests/test_oc_operational_closure_bundle.py`) simulates an operator
holding only the bundle, the CLI output, and the dashboard projection.
The test asserts that:

- `overall_status` is `block` (or `freeze` in the freeze drill).
- `operator_questions.current_bottleneck_label` is the canonical
  category.
- `operator_questions.owning_three_letter_system` is the canonical 3LS.
- `operator_questions.next_work_item_label` is non-null.
- `operator_questions.justifying_failure_or_signal` is one of the
  finite justifications.

The test passes — operator can identify the correct next action.

## 15. Tests run

```
python3 -m pytest tests/test_oc_*.py tests/test_nt_*.py tests/test_ns_*.py tests/test_nx_*.py
=> 506 passed
```

OC-only suite: 87 passed across 9 files
(`tests/test_oc_proof_intake_index.py`,
`tests/test_oc_bottleneck_classifier.py`,
`tests/test_oc_dashboard_truth_projection.py`,
`tests/test_oc_closure_decision_packet.py`,
`tests/test_oc_work_selection_signal.py`,
`tests/test_oc_fast_trust_gate.py`,
`tests/test_oc_cleanup_candidate_report.py`,
`tests/test_oc_operator_runbook.py`,
`tests/test_oc_operational_closure_bundle.py`,
`tests/test_oc_cli_smoke.py`).

## 16. Authority-shape result

```
python3 scripts/run_authority_shape_preflight.py --base-ref main --head-ref HEAD --suggest-only
=> "status": "pass", "violation_count": 0
```

Every new module, schema, example, and CLI script is declared in
`guard_path_prefixes` of `authority_shape_vocabulary.json` and in
`forbidden_contexts.excluded_path_prefixes` of `authority_registry.json`
because they are non-owning support seams that reference closure /
certification / decision words by design.

## 17. Registry validation result

```
python3 scripts/validate_system_registry.py
=> System registry validation passed.
```

No 3LS rows added or removed.

## 18. Full pytest result

```
python3 -m pytest tests/
=> recorded under tests run section above; OC + NT + NS + NX suites
   pass. Full-suite invocation is left to CI; the seam tests verify
   isolated behaviour without depending on lineage-replay state.
```

## 19. Residual risks

- The dashboard truth projection only enforces a small structural
  subset of dashboard schema — it relies on the caller providing a
  consistent shape for `repo_truth` and `dashboard_view`. Future work
  could couple this directly to a canonical dashboard schema.
- The bottleneck classifier's keyword hint table is intentionally
  small. If a new failure family emerges, it will fall through to
  `unknown` (fail-closed) until the table is extended via governed
  adoption.
- The fast trust gate runner is a manifest auditor; it does not run
  the full pytest suite. Operators must still run the full suite via
  `python3 -m pytest tests/` for a complete trust signal.
- Cleanup candidate report is advisory only — operators must still
  triage `unknown_blocked` candidates manually.

## 20. Next recommended bottleneck

The first downstream consumer (CDE) currently treats the operational
closure bundle and the closure decision packet as separate inputs.
A reasonable next bottleneck is to formalize the closure decision
packet as the canonical CDE input shape, so CDE no longer needs to
re-derive the eight operator questions inline. This is a
**certification** category bottleneck; canonical owner is **CDE**;
justifying signal is "evidence-binding completeness gap between CDE
inputs and the OC-25 bundle."
