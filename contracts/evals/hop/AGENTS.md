# HOP Eval Set v1

This directory contains the **versioned** transcript -> FAQ eval set for the
Harness Optimization Pipeline.

## Layout

- `manifest.json` — eval set id + version + ordered case list, schema-bound.
- `cases/*.json` — individual `hop_harness_eval_case` artifacts.
- `generate_eval_set.py` — deterministic generator that emits the manifest and
  every case file. Run with `python contracts/evals/hop/generate_eval_set.py`
  after editing the source-of-truth in the script. The committed JSON files
  are the canonical artifacts; the generator exists so the cases can be
  regenerated bit-identically.

## Categories

- `golden` — should pass under a correctly-built transcript -> FAQ harness.
- `adversarial` — challenges harness robustness; known to be tricky for the
  baseline.
- `failure_derived_placeholder` — placeholders for failure modes wired into
  HOP-BATCH-1's safety / validator surface; expand as failures accrete.

## Versioning

Bump `eval_set_version` in `manifest.json` whenever any case is added,
removed, or modified. The generator script enforces deterministic
content-hash computation so two distinct runs produce identical JSON.
