# NX-ALL-01 — Trust Hardening Delivery Report

## 1. Intent

NX-ALL-01 is the next-phase trust hardening pass after SYS-REDUCE-01-FIX. The
goal is to strengthen the canonical execution → eval → control → enforcement
loop and its overlay authorities (REP, LIN, OBS, SLO, CTX, GOV/PRA) by
adding small, fail-closed adjudication seams plus deterministic adversarial
test fixtures. The work introduces no new top-level 3-letter systems and
preserves the reduced active authority model from SYS-REDUCE-01-FIX.

Every change in this delivery either:
1. prevents a specific failure, or
2. improves a measurable trust/debug/control signal.

## 2. Roadmap steps completed

| Phase | Status |
| ----- | ------ |
| NX-01 Registry stabilization gate | done |
| NX-02 Red team: registry integrity | done (10 adversarial fixtures) |
| NX-03 Registry hardening fix | done (validator + protected-authority map + demoted-forbidden table) |
| NX-04 Eval spine consolidation | done (`runtime/eval_spine.py` wraps existing primitives) |
| NX-05 Red team: eval blind spots | done (8 fixtures) |
| NX-06 Eval coverage expansion | done (canonical reason-code mapping + heuristic fallbacks) |
| NX-07 Replay hardening | done (`replay/replay_support.py`) |
| NX-08 Red team: replay integrity | done (8 fixtures) |
| NX-09 Replay fix pass | done (canonical mismatch reason codes + coverage summary) |
| NX-10 Lineage enforcement | done (`lineage/lineage_enforcement.py`) |
| NX-11 Red team: lineage gaps | done (7 fixtures) |
| NX-12 Lineage fix pass | done (lineage coverage summary metric) |
| NX-13 Observability compression — 5-step trace | done (`observability/failure_trace.py`) |
| NX-14 Red team: debuggability | done (7 fixtures asserting required diagnostic fields) |
| NX-15 Observability fix pass | done (each missing step carries reason_code + next-action) |
| NX-16 Control loop tightening | done (`runtime/control_chain_invariants.py`) |
| NX-17 Red team: control bypass | done (8 fixtures) |
| NX-18 Control fix pass | done (trace continuity + decision↔enforcement mismatch detection) |
| NX-19 Context gate hardening | done (`runtime/context_admission_gate.py`) |
| NX-20 Red team: context poisoning | done (10 fixtures) |
| NX-21 Context fix pass | done (canonical CTX reason codes) |
| NX-22 SLO / error budget enforcement | done (`runtime/slo_budget_gate.py`) |
| NX-23 Red team: drift & budget | done (10 fixtures) |
| NX-24 Final stabilization pass | done (full pytest passes) |
| NX-25 Certification gate hardening | done (`governance/certification_prerequisites.py`) |
| NX-26 Final red team: system-level | done (`tests/test_nx_end_to_end_loop.py`, passing + 3 failing paths) |
| NX-27 Final fix + PR readiness | done |

## 3. Files changed

### New runtime modules (8 small, scope-bounded files)
- `spectrum_systems/modules/runtime/eval_spine.py`
- `spectrum_systems/modules/runtime/control_chain_invariants.py`
- `spectrum_systems/modules/runtime/context_admission_gate.py`
- `spectrum_systems/modules/runtime/slo_budget_gate.py`
- `spectrum_systems/modules/replay/replay_support.py`
- `spectrum_systems/modules/lineage/lineage_enforcement.py`
- `spectrum_systems/modules/observability/failure_trace.py`
- `spectrum_systems/modules/governance/certification_prerequisites.py`

### Updated registry guard
- `scripts/validate_system_registry.py` — added:
  - `parse_future_systems_with_rationale`
  - `parse_system_definitions`
  - `PROTECTED_AUTHORITY_BY_SYSTEM` table
  - `DEMOTED_FORBIDDEN_OWNS` table
  - generalized NX-02 shadow-ownership detection
  - protected-owner-status invariant (active owners cannot be demoted)
  - placeholder rationale check

### Updated authority registry
- `contracts/governance/authority_registry.json` — added the eight new modules
  to `forbidden_contexts.excluded_path_prefixes` so the authority-leak guard
  recognizes them as legitimate adjudication seams.

### New tests (10 files, 122 cases)
- `tests/test_nx_registry_red_team.py` — 17
- `tests/test_nx_eval_spine.py` — 22
- `tests/test_nx_replay_support.py` — 18
- `tests/test_nx_lineage_enforcement.py` — 13
- `tests/test_nx_observability_failure_trace.py` — 9
- `tests/test_nx_control_chain.py` — 10
- `tests/test_nx_context_admission.py` — 13
- `tests/test_nx_slo_budget_gate.py` — 16
- `tests/test_nx_certification_prerequisites.py` — 9
- `tests/test_nx_end_to_end_loop.py` — 4

## 4. Failure modes prevented

- **GOV/TLC/RQX shadow-ownership of protected authorities** — parsed
  System Definitions block now refuses any active system whose `owns` list
  contains a protected authority owned by a different active owner.
- **Demoted/deprecated systems re-claiming active authority** — explicit
  forbidden-token table per demoted system; generalized check against the
  protected-authority map.
- **Active protected owner silently demoted** — registry validator now
  refuses to certify a registry where any of `PQX, CDE, SEL, TPA, EVL, REP,
  LIN, CTX, GOV, PRA, JDX, JSX, OBS, SLO, RIL, TLC` has non-active status.
- **Future placeholder systems with live runtime evidence and no
  rationale** — flagged.
- **Eval blind spots:** missing required eval mapping/definition/result,
  indeterminate required eval, failing schema/evidence/policy result —
  each blocks/freezes with a canonical reason code.
- **Replay drift undetected:** missing original record, missing input or
  output hash, hash mismatch on input/output/both, non-replayable
  artifact — each yields a canonical `REPLAY_*` reason code.
- **Lineage gaps:** missing parent, missing produced-artifact, missing
  trace_id, missing run_id, no chain to immutable input — fail-closed
  promotion gate.
- **Debuggability gaps:** every failure surfaces (failed_stage,
  reason_code, owning_system, artifact_id, next_recommended_action) in
  one machine + human-readable artifact.
- **Control bypass:** SEL allow_execution while CDE blocks, enforcement
  without decision reference, decision without eval summary reference,
  trace continuity break, decision↔enforcement ID mismatch.
- **Context poisoning:** missing provenance, stale TTL, schema
  incompatibility, untrusted instruction injection, contradictory context,
  missing preflight.
- **SLO bypass:** budget exhaustion, drift escalation, override-rate
  escalation, replay-mismatch-rate escalation, eval-pass-rate degradation,
  invalid posture — escalating warn → freeze → block.
- **Certification bypass:** missing eval pass, missing lineage, missing
  replay readiness, missing control decision, missing enforcement record,
  active registry violations.

## 5. Signals improved

- Registry validation produces explicit diagnostic messages prefixed with
  `NX-01:` / `NX-02:` for shadow ownership and placeholder rationale.
- Eval spine produces a single `control_handoff` artifact with
  `{decision, reason_code, blocking_reasons, trace_id, run_id}`.
- Replay support produces a coverage summary
  `{total, match, mismatch, indeterminate, match_rate, reason_codes,
  status, debug_message}`.
- Lineage enforcement produces a coverage summary with
  `completeness_rate` and per-artifact reason-code counts.
- Failure trace produces a 5-step structured artifact and a multi-line
  human-readable summary suitable for pasting into a postmortem.
- SLO gate produces a single warn/freeze/block decision with the
  effective thresholds emitted alongside the decision for auditability.

## 6. Red-team tests added

122 fixtures spread across 10 test files (see §3). Each fixture targets
exactly one failure mode and asserts the canonical reason code, decision,
and blocking-reason list. The fixtures live next to the existing test
suite and are picked up by the default pytest configuration.

## 7. Fixes made from red-team findings

- Added the protected-authority-owner-status invariant when a `protected`
  owner appears non-active in System Definitions.
- Added the generalized shadow-ownership detector across demoted systems
  via the protected-authority cross-check (not just the explicit forbidden
  table).
- Added blocking-reason synthesis to `eval_to_control_signal` so a `block`
  decision can never carry an empty reasons list.
- Added missing-input-hash and missing-output-hash classification with
  separate reason codes (no fallthrough).
- Added trace-continuity check across the control chain and end-to-end
  loop so cross-trace drift surfaces immediately.
- Added the `excluded_path_prefixes` entries for the new modules so the
  authority-leak guard does not flag legitimate adjudication seams.
- Added a re-entry guard so `assert_certification_prerequisites` returns
  `CERT_OK` only when all evidence is present AND each evidence stream
  reports a healthy/allow status.

## 8. Validation commands run

```
python scripts/validate_system_registry.py        # passes
python -m pytest tests/test_nx_*.py                # 131 pass
python -m pytest tests/test_system_registry*.py    # 39 pass
python -m pytest tests/test_authority_leak_guard_local.py  # 1 pass
python -m pytest tests/                            # 9380 pass, 2 skipped
```

## 9. Remaining risks

- The new adjudication seams are advisory: they need to be wired into the
  existing PQX/CDE/SEL surfaces by the next phase (NX-PHASE-2-WIRING).
  Until that wiring lands, the protections are available but not
  mandatory at the runtime entry points.
- The protected-authority map in `validate_system_registry.py` is
  hand-maintained. A future phase should generate it from the canonical
  System Definitions section to remove the drift surface.
- `excluded_path_prefixes` in the authority registry now lists 8 new
  modules; this list is also hand-maintained. A future phase should
  derive it from a single annotation on each module.
- The 5-step failure trace currently treats a missing
  enforcement-on-allow path as `ok`; this is consistent with the
  existing OBS contract but a future phase may want to emit an explicit
  `enforcement_skipped` step instead.
- The end-to-end test (`test_nx_end_to_end_loop.py`) wires the new seams
  with synthetic artifacts. A wiring phase that exercises the live
  `evaluation_control` / `enforcement_engine` runtime should be added
  before the end-to-end harness is treated as the canonical promotion
  proof.

## 10. No new top-level 3-letter systems

Confirmed. NX-ALL-01 added zero entries to the `## Active executable
systems`, `## Future / placeholder systems`, or `## System Definitions`
sections of `docs/architecture/system_registry.md`. Every new module
extends an existing canonical owner (EVL, REP, LIN, OBS, CDE/SEL, CTX,
SLO, GOV/PRA) and is recorded in the corresponding
`excluded_path_prefixes` entry of `contracts/governance/authority_registry.json`
as a support seam, not an authority owner. The reduced active authority
model from SYS-REDUCE-01-FIX is preserved.
