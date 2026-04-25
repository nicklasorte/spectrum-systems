# HOP-003C-004 — Phase 1 Trial Validation

**Status:** PASS — Phase 2 unlocked.
**Workflow:** transcript → FAQ (`hop_transcript_to_faq_v1`, eval_set v1.0.0).
**Iterations:** 5 (within the 5–10 contract). Two independent runs (`run_a`, `run_b`).
**Driver:** `scripts/hop_run_controlled_trial.py` invoking
`spectrum_systems.modules.hop.trial_runner.run_controlled_trial`.

This document is the empirical evidence required by HOP-003C-004 §3 before any
certification or promotion infrastructure may be added. Every claim below is
backed by an artifact in
`artifacts/hop_trial_run/run_{a,b}/` or by a test that runs in CI.

## 1. Configuration

- Manifest: `contracts/evals/hop/manifest.json` (27 cases:
  13 golden, 11 adversarial, 3 failure-derived placeholders).
- Sandbox: enabled (`spectrum_systems.modules.hop.sandbox.execute_candidate`,
  subprocess-isolated, `-I` flag, env wiped, network/subprocess/file-write
  guards). Used unconditionally by `evaluator.evaluate_candidate`.
- Patterns enabled: `draft_verify`, `label_primer`, `domain_router` (loaded as
  read-only proposer context; their use is bounded by the proposer quota).
- Bootstrap: not applied (the deterministic baseline already saturates the
  search eval; bootstrap would not change the conclusion in this run).

## 2. Baseline vs Best Candidate

| Metric                              | Baseline (`baseline_v1`) | Best candidate (run A) | Best candidate (run B) |
|-------------------------------------|--------------------------|------------------------|------------------------|
| Eval score (pass-rate over 27)      | 1.0                      | 1.0                    | 1.0                    |
| Pass count                          | 27                       | 27                     | 27                     |
| Fail count                          | 0                        | 0                      | 0                      |
| Trace completeness                  | 1.0                      | 1.0                    | 1.0                    |
| Failure modes observed              | none                     | `neutral_change`       | `neutral_change`       |

The deterministic baseline harness already saturates the search eval at 1.0.
The proposer's four bounded mutation templates produce admissible candidates
that preserve the FAQ-output contract. Each mutation evaluates at 1.0 (no
regression) and the trace-diff / failure-analysis chain explicitly classifies
them as `neutral_change` with `suspected_cause = no_observable_per_case_movement`.

This is the **valid-failure** branch of the HOP-003C-004 §3.C gate: no
improvement is claimed, and the absence of improvement is structurally
explained by:

- **eval deltas** (per-case score deltas are zero across all 27 cases — see
  `failures/hop_failure_*.json`);
- **trace evidence** (full traces persisted for every (candidate, case) pair —
  297 traces under `traces/`);
- **failure hypotheses** (causal-analysis stage emits one
  `neutral_change` hypothesis per neutral candidate, blocking promotion only
  on `severity == "reject"`).

Improvement is impossible without expanding the search eval; that is exactly
what Phase 2's `eval_factory` exists to do.

## 3. Frontier Progression

```
[1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
```

Six points: 1 baseline + 5 cycles. Frontier is flat because the baseline is
already optimal under the search eval — the frontier artifact correctly
records this rather than fabricating spurious progression.

Five `hop_harness_frontier` artifacts persisted under `frontiers/` (one per
proposer cycle), each schema-validated, each bounded by the
`max_frontier_window` parameter.

## 4. Artifact Inventory (run_a)

Counts from `artifacts/hop_trial_run/run_a/index.jsonl`:

| artifact_type                       | count |
|-------------------------------------|-------|
| `hop_harness_candidate`             | 11    |
| `hop_harness_run`                   | 11    |
| `hop_harness_score`                 | 11    |
| `hop_harness_trace`                 | 297   |
| `hop_harness_trace_diff`            | 10    |
| `hop_harness_failure_hypothesis`    | 2     |
| `hop_harness_frontier`              | 5     |
| `hop_harness_trial_summary`         | 1     |

Every artifact is schema-validated on write (`ExperienceStore.write_artifact`),
content-hash bound, and immutable (writes refuse overwrite).

## 5. Validation Checks

### A. Sandbox enforcement — PASS

- `evaluator._execute_one_case` calls `execute_candidate` for **every** case;
  there is no path that runs candidate code in-process.
- `tests/hop/test_sandbox.py` (4 cases) and
  `tests/hop/test_adversarial_batch2.py` (22 cases) cover:
  - network access (`socket.socket`) → `sandbox_violation`,
  - subprocess (`subprocess.Popen`) → `sandbox_violation`,
  - file write outside the supplied tempdir → `sandbox_violation`,
  - environment access — wiped before child runs.
- The trial run produced **zero** `sandbox_violation` artifacts because the
  proposer templates are intentionally well-formed; the bypass paths are
  proven closed by the dedicated tests.

### B. Eval integrity — PASS

- `load_eval_set_from_manifest` recomputes each case's `content_hash` and
  cross-checks the manifest entry. Any mismatch fails closed with
  `ValueError("hop_evaluator_tampered_manifest:...")` —
  `tests/hop/test_evaluator.py` exercises this path.
- The evaluator never mutates eval cases; the `EvalSet` dataclass is
  `frozen=True` and exposes cases as a `tuple[Mapping, ...]`.
- `validate_hop_artifact(case, "hop_harness_eval_case")` is called at load
  time AND at every evaluation entry — there is no bypass.

### C. Improvement OR valid failure — PASS (valid failure)

See §2. The score-ceiling on the search eval is structurally explained.

### D. Reproducibility — PASS

`run_a` and `run_b` independent invocations produced **byte-identical** trial
summaries:

- `content_hash = sha256:1b095535172b1bf43b2fb93e5231dde0372ea00275692d48ad457ba7b8a2cd08`
- `artifact_id = hop_trial_1b095535172b1bf4`
- identical `frontier_evolution`, `failure_modes`, `best_score`.

The trial summary excludes wall-clock fields and per-run UUIDs (those live in
the per-run artifacts), so the summary is naturally deterministic across runs.

## 6. Failure Modes Observed

- `neutral_change` (×2 in run_a) — proposer mutations that preserve behavior.
  This is the expected outcome for a saturated baseline; it is not a defect.
- No `runtime_error`, no `sandbox_violation`, no `malformed_artifact`, no
  `unknown_eval_case` in this trial.

## 7. Verification Steps

```bash
# Phase 1 trial — two independent runs
python scripts/hop_run_controlled_trial.py \
    --store-root artifacts/hop_trial_run/run_a \
    --iterations 5 \
    --report-path artifacts/hop_trial_run/run_a_summary.json

python scripts/hop_run_controlled_trial.py \
    --store-root artifacts/hop_trial_run/run_b \
    --iterations 5 \
    --report-path artifacts/hop_trial_run/run_b_summary.json

# Identical content_hash on the trial summary proves reproducibility.
diff <(jq '.trial_summary.content_hash' artifacts/hop_trial_run/run_a_summary.json) \
     <(jq '.trial_summary.content_hash' artifacts/hop_trial_run/run_b_summary.json)

# Phase 1 tests
python -m pytest tests/hop/test_trial_runner.py \
                 tests/hop/test_sandbox.py \
                 tests/hop/test_adversarial_batch2.py -q
```

## 8. Gate Decision

| Gate condition                                   | Result |
|--------------------------------------------------|--------|
| Sandbox bypassable                               | NO     |
| Eval bypassable                                  | NO     |
| Artifacts missing or invalid                     | NO     |
| Results not reproducible                         | NO     |
| Improvement claimed without evidence             | NO     |

**Phase 1 PASSED. Phase 2 (certification + promotion infra) is authorized.**
