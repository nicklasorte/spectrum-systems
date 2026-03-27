# Control-Loop Certification Pack (trust-boundary/runtime)

## What this certifies

The control-loop certification pack is the canonical governed checkpoint for the `trust-boundary/runtime` slice. It certifies whether the required control-loop hardening evidence set was executed and produced pass/fail/blocked outcomes under one deterministic decision mapping.

Certification artifact type:

- `control_loop_certification_pack`
- Schema: `contracts/schemas/control_loop_certification_pack.schema.json`
- Builder CLI: `python scripts/run_control_loop_certification.py`

## Included checks (required)

The certification runner executes exactly four required checks:

1. Control-loop chaos runner result
   - `python scripts/run_control_loop_chaos_tests.py ...`
2. Targeted control-loop / eval gate test set
   - `pytest tests/test_control_loop.py tests/test_control_loop_chaos.py tests/test_eval_ci_gate.py -q`
3. Pairwise review artifact validation
   - `python scripts/validate_review_artifact.py <review.json> --markdown <review.md>`
4. Repo-level review validator
   - `python scripts/validate_review_artifacts.py`

Fail-closed behavior:

- Missing required command or evidence path ⇒ `blocked`
- Malformed required evidence payload (for chaos summary) ⇒ `blocked`
- Non-zero check exit code ⇒ `fail` for that check

## Decision mapping (deterministic)

Decision mapping is explicit and deterministic:

- All required checks pass ⇒ `certification_status=certified`, `decision=pass`
- Any required check fails (and none blocked) ⇒ `certification_status=uncertified`, `decision=fail`
- Any required evidence missing/malformed, or required check missing ⇒ `certification_status=blocked`, `decision=blocked`

`blocked` has precedence over `fail`.

## What this does **not** certify

This pack does not certify:

- broad repository health outside the four required checks
- downstream deployment safety or production readiness
- architectural compliance outside existing canonical validators

It is a narrow trust-boundary/runtime control-loop certification checkpoint.

## Mandatory promotion gate behavior (control-loop slice)

Control-loop promotion now fails closed unless a valid certification artifact is provided and it reports:

- `certification_status=certified`
- `decision=pass`

This is **mandatory**, not advisory:

- missing artifact ⇒ promotion blocked
- malformed/schema-invalid artifact ⇒ promotion blocked
- `certification_status != certified` ⇒ promotion blocked
- `decision != pass` ⇒ promotion blocked

The canonical promotion/governance seam is the evaluation enforcement bridge in promotion scope (`scripts/run_evaluation_enforcement_bridge.py --scope promotion`), which records certification reference + status + decision + block reason in the emitted `evaluation_enforcement_action` artifact.

## Operational usage before promotion/merge/roadmap advancement

Example:

```bash
python scripts/run_control_loop_certification.py \
  --output outputs/control_loop_certification/control_loop_certification_pack.json

python scripts/run_evaluation_enforcement_bridge.py \
  --input outputs/evaluation_budget_governor/evaluation_budget_decision.json \
  --scope promotion \
  --control-loop-certification outputs/control_loop_certification/control_loop_certification_pack.json \
  --output-dir outputs/evaluation_enforcement_bridge
```

Interpret exit code:

- `0` = certified/pass
- `1` = uncertified/fail
- `2` = blocked

Consume the emitted certification JSON and promotion enforcement JSON artifacts as the canonical evidence record for this checkpoint.
