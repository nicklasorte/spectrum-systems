# H01 Final Fix Plan — Routing Authority Encapsulation

- **Plan ID:** H01-FINAL-FIX-PLAN
- **Source review:** RVA-H01-FINAL-001
- **Batch:** BATCH-H01-FINAL
- **Created:** 2026-04-26

This plan resolves every S2+ finding from the H01 final review. All fixes
ship via this PR; no out-of-band changes.

## Fixes

### FIX-001 — Eliminate the public unchecked routing entrypoint (S4)

**Finding:** F-001
**Target:** `spectrum_systems/modules/orchestration/tlc_router.py`

- `_route_artifact_unchecked` is underscore-prefixed and excluded from
  `__all__`.
- `__all__` exports only `route_with_gate_evidence`, `ArtifactRoutingError`,
  `is_terminal`, `pipeline_position`, `validate_transition`, and
  `get_full_pipeline`.
- The docstring on `_route_artifact_unchecked` is explicit: external
  callers must use `route_with_gate_evidence`; direct calls produce a
  `ROUTING_BYPASS_ATTEMPT` finding.

### FIX-002 — Detect indirect routing bypass at preflight (S3)

**Finding:** F-002
**Target:** `scripts/run_3ls_authority_preflight.py`

- Added `detect_routing_bypass()` and a pattern set covering:
  - direct calls to `_route_artifact_unchecked`,
  - imports / from-imports of the unchecked symbol,
  - re-exports via `__all__` string literals,
  - public `route_artifact = ...` aliases,
  - public `def route_artifact(...)` definitions outside the owner module.
- All findings carry `reason_code = "ROUTING_BYPASS_ATTEMPT"` and reference
  the canonical authority source.
- The summary now reports `routing_bypass_count`.

### FIX-003 — Strengthen gate-evidence structural validation (S3)

**Finding:** F-003
**Target:** `spectrum_systems/modules/orchestration/tlc_router.py`

- `route_with_gate_evidence` now rejects:
  - non-dict `artifact` (`INVALID_ARTIFACT_ENVELOPE`),
  - empty / non-string `eval_summary_id` (`INVALID_EVAL_SUMMARY_ID`),
  - non-string `gate_status` (`INVALID_GATE_STATUS_TYPE`).
- These checks run before status-set membership tests, so no string-only
  comparison can decide routing in isolation.

### FIX-004 — Replay integrity tests (S3)

**Finding:** F-004
**Target:** `tests/transcript_pipeline/test_replay_integrity_h01.py`

- New test module covering:
  - happy-path baseline (route + register),
  - payload mutation breaks `content_hash`,
  - mutation + re-registration is rejected with `DUPLICATE_ARTIFACT_ID`,
  - gate-evidence reuse across artifacts is rejected with
    `ARTIFACT_ID_MISMATCH`,
  - conditional gate cannot be silently upgraded,
  - direct use of the underscore symbol is documented as a bypass.

### FIX-005 — Reject malformed artifact envelopes (S2)

**Finding:** F-005
**Target:** `spectrum_systems/modules/orchestration/tlc_router.py`

- Non-dict artifacts now raise `ArtifactRoutingError` with
  `INVALID_ARTIFACT_ENVELOPE` as the first check. The previous behaviour
  (silent coercion of `artifact_type` to `None`, then a downstream
  `INVALID_ARTIFACT_TYPE` from `_route_artifact_unchecked`) is gone.

## Regression Coverage

- `tests/transcript_pipeline/test_no_unchecked_routing.py` — extended with
  six new structural-validation cases and six bypass-guard cases.
- `tests/transcript_pipeline/test_replay_integrity_h01.py` — new file.
- `tests/transcript_pipeline/test_chaos_h07.py` (existing) covers the
  routing-failure chaos scenarios; no changes required.

## Verification commands

```sh
python scripts/run_3ls_authority_preflight.py --base-ref origin/main --head-ref HEAD
python scripts/run_authority_leak_guard.py --base-ref origin/main --head-ref HEAD --output outputs/authority_leak_guard/authority_leak_guard_result.json
python scripts/run_system_registry_guard.py --base-ref origin/main --head-ref HEAD --output outputs/system_registry_guard/system_registry_guard_result.json

pytest tests/transcript_pipeline/test_control_routing_enforcement.py
pytest tests/transcript_pipeline/test_h01b_hardening.py
pytest tests/transcript_pipeline/test_no_unchecked_routing.py
pytest tests/transcript_pipeline/test_replay_integrity_h01.py
```
