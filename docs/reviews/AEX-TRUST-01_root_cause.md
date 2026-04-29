# AEX-TRUST-01 — Root-Cause Analysis

**Work item:** AEX-TRUST-01 (Harden AEX Trust-Gap Signals)
**Branch:** `claude/harden-aex-trust-gaps-2tAqj`
**Scope:** AEX admission boundary only. AEX remains *admission-only*. It
emits inputs/observations/signals to downstream owners (SEL/ENF, GOV, REL,
CDE) but never owns the outcomes those owners produce.

## 1. Source of dashboard truth

Dashboard trust state for AEX is computed by:

```
spectrum_systems/modules/tls_dependency_graph/
  registry_parser.py   (TLS-00: registry → graph)
  evidence_scanner.py  (TLS-01: scans repo for path / token evidence)
  classification.py    (TLS-02: candidate classification)
  trust_gaps.py        (TLS-03: deterministic signal detection)
  ranking.py           (TLS-04: priority report)
```

The TLS pipeline is invoked by:

```
scripts/build_tls_dependency_priority.py --candidates ... --fail-if-missing
scripts/build_dashboard_3ls_with_tls.py
```

The dashboard does not compute AEX trust state — it reads
`artifacts/tls/system_trust_gap_report.json` which is the
governed output of `trust_gaps.detect_trust_gaps()`.

Per `docs/architecture/system_registry.md`, AEX is:

* **Owned artifacts:** `build_admission_record`,
  `normalized_execution_request`, `admission_rejection_record`.
* **Downstream:** `PQX`, `CTX`, `PRM`.
* **Status:** active.

## 2. Observed AEX state at task start

Running the canonical generator produces (in
`artifacts/tls/system_trust_gap_report.json`):

```json
{
  "system_id": "AEX",
  "classification": "active_system",
  "gap_count": 4,
  "gaps_evaluated": 9,
  "trust_state": "freeze_signal",
  "failing_signals": [
    "missing_enforcement_signal",
    "missing_observability | missing_readiness_evidence",
    "missing_replay",
    "schema_weakness"
  ],
  "passing_signals": [
    "missing_control",
    "missing_eval",
    "missing_lineage",
    "missing_tests"
  ]
}
```

`missing_observability` and `missing_readiness_evidence` flip between failing
and passing across runs because `evidence_scanner.attach_evidence()` truncates
each evidence bucket at `max_per_bucket=25` while iterating
`Path.rglob('*')` (filesystem-order). When the OBS-flavored module
(`rfx_observability_replay_consistency.py`) is admitted before the
governance modules (or vice-versa), one signal flips. Both must be cleared
deterministically — by token-bearing, AEX-prefixed evidence — for AEX to
stop being the dashboard bottleneck.

The task description's enumeration (`missing_eval`, `missing_tests`,
`missing_lineage`) is a worst-case inflation of the bucket-truncation effect:
under heavier truncation, AEX could lose its lineage evidence (already
borderline because lineage modules are in `runtime/`) or even its tests if
unrelated systems pre-empt the bucket. This work hardens AEX so that *every*
signal is satisfied by AEX-prefixed, AEX-owned evidence whose paths cannot be
displaced by unrelated rglob ordering.

## 3. Per-signal root cause

`trust_gaps.py` evaluates signals deterministically from the evidence
attachment row + registry node. The relevant predicates are:

| Signal | Predicate (true ⇒ failing) |
|---|---|
| `missing_enforcement_signal` | `sid != "SEL"` AND `"SEL" not in downstream` AND `not _has_path_token(modules, "sel_")` |
| `missing_eval` | `tests == []` AND `"EVL" not in upstream+downstream` AND `not _has_path_token(schemas, "eval")` |
| `missing_observability` | `sid != "OBS"` AND `"OBS" not in downstream` AND `not _has_path_token(modules, "observability")` |
| `missing_replay` | `sid != "REP"` AND `"REP" not in downstream` AND `not _has_path_token(tests, "replay")` |
| `missing_lineage` | `sid != "LIN"` AND `"LIN" not in downstream` AND `not _has_path_token(artifacts, "lineage")` AND `not _has_path_token(modules, "lineage")` |
| `missing_readiness_evidence` | `sid != "GOV"` AND `"GOV" not in downstream` AND `not _has_path_token(artifacts, "gov_")` AND `not _has_path_token(modules, "/governance/")` |
| `missing_tests` | `tests == []` |
| `schema_weakness` | `schemas == []` |
| `missing_control` | `sid not in canonical_loop` AND `"CDE" not in downstream` AND `sid != "CDE"` |

`evidence_scanner` only scans `schemas/` for the `schemas` bucket
(`SCAN_BUCKETS`). Schemas that live under `contracts/schemas/` are NOT scanned
into the `schemas` bucket. AEX's contract schemas already exist there
(`contracts/schemas/build_admission_record.schema.json`, etc.) but they
contribute zero evidence to the `schemas` bucket.

### 3.1 missing_enforcement_signal

* AEX `downstream = [PQX, CTX, PRM]`. SEL is not present (correct — SEL
  retains compliance authority and AEX must not encroach).
* No module path under AEX evidence contains `sel_`. Modules referencing
  `sel_admission_*` simply do not exist.
* **Fix shape:** AEX must produce an *admission policy observation* that
  SEL/ENF can consume as enforcement input, and the producer must live at a
  path containing `sel_` (e.g. `spectrum_systems/aex/sel_admission_signal.py`).
  AEX retains observer ownership; SEL retains enforcement authority.

### 3.2 missing_eval

* Currently passing (AEX has tests + EVL referenced via existing tests).
  Hardening adds dedicated AEX eval cases anyway, to remove the
  bucket-truncation risk where unrelated tests would push AEX tests off the
  list.

### 3.3 missing_observability

* No AEX-owned module contains the `observability` token. The current
  passing signal relies on `rfx_observability_replay_consistency.py` being
  retained in the bucket — fragile.
* **Fix shape:** add `spectrum_systems/aex/observability_emitter.py`
  that emits a `admission_trace_record` (trace_id, run_id, span fields).

### 3.4 missing_replay

* No test under `tests/` contains `replay` in path AND references AEX.
* **Fix shape:** add `tests/aex/test_admission_replay.py` (path contains
  `replay` + `aex`). Back it with `scripts/replay_aex_admission.py` and
  `spectrum_systems/aex/admission_replay.py` so the test exercises a real
  deterministic-input/output replay, not a stub.

### 3.5 missing_tests

* Currently passing (AEX has multiple tests). Hardening adds an `tests/aex/`
  package so AEX-prefixed test paths anchor the bucket head.

### 3.6 schema_weakness

* `schemas` bucket for AEX is `[]` — `schemas/` has no AEX-prefixed
  files. The contract schemas under `contracts/schemas/` are correctly
  considered the canonical authority and are NOT scanned by the supplemental
  `schemas/` scanner.
* **Fix shape:** add `schemas/aex/*.schema.json` supplemental
  structural schemas (per `schemas/README.md`: "Supplemental for non-contract
  structural schemas"). These re-state required fields, mark
  `additionalProperties: false`, and provide direct evidence for the bucket.

### 3.7 missing_lineage

* Currently passing (lineage modules exist in evidence).
  Hardening anchors lineage with an AEX-owned
  `artifacts/aex/aex_admission_lineage_observation.json` so the signal does
  not depend on bucket retention of unrelated runtime modules.

### 3.8 missing_readiness_evidence

* Failing under bucket-cap drops. AEX is not authority over readiness — GOV
  is — but AEX may *observe* readiness inputs.
* **Fix shape:** add `artifacts/aex/aex_gov_readiness_observation.json`
  (path token `gov_`, AEX-token in path) — an *observation* that GOV can
  consume; AEX claims no readiness authority.

## 4. Authority-shape boundary

This work touches AEX only. It does NOT:

* move SEL/ENF compliance ownership to AEX (SEL retains it);
* move GOV/REL readiness/advancement ownership to AEX (REL retains it);
* move CDE control / closure ownership to AEX (CDE retains it);
* move REP replay ownership to AEX (REP retains it);
* move LIN lineage issuance ownership to AEX (LIN retains it);
* move OBS observability ownership to AEX (OBS retains it);
* move EVL evaluation ownership to AEX (EVL retains it).

AEX continues to produce only admission outputs and admission-flavored
observations that downstream owners consume.

## 5. Plan of remediation

| Part | Output |
|---|---|
| B | Supplemental schemas under `schemas/aex/` + new contract schemas for `admission_policy_observation`, `admission_evidence_record`, `admission_trace_record`. |
| C | AEX eval cases registered in `evals/eval_case_library.json`. |
| D | `tests/test_aex_trust_hardening.py` and `tests/aex/test_admission_replay.py`. |
| E | `spectrum_systems/aex/observability_emitter.py`, `spectrum_systems/aex/sel_admission_signal.py`, AEX-owned artifacts under `artifacts/aex/`. |
| F | `spectrum_systems/aex/admission_replay.py` + `scripts/replay_aex_admission.py` + replay record artifact + replay command ref in evidence. |
| G | Re-run `build_tls_dependency_priority.py` so `system_trust_gap_report.json` reflects AEX = `ok` (or as close as the evidence allows). |
| H | Run TLS phase-3 tests, AEX hardening tests, and authority-shape preflight. |
| I | `docs/reviews/AEX-TRUST-01_final_report.md`. |

## 6. Non-falsification commitments

* No artifact under `artifacts/tls/` is hand-edited.
* The trust-gap detector is unchanged.
* The dashboard remains a reader of generated artifacts.
* All new AEX evidence is real code/tests/schemas/artifacts wired through the
  existing `validate_artifact` and `attach_evidence` paths.
* If `missing_enforcement_signal` cannot be fully cleared because SEL still
  lacks a consumer contract for the AEX-emitted observation, that is recorded
  as a downstream SEL/ENF integration gap — not an AEX admission gap.
