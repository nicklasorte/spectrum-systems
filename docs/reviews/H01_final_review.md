# H01 Final Red-Team Review — Routing Authority Encapsulation

- **Review ID:** RVA-H01-FINAL-001
- **Reviewer:** Adversarial-Review-Agent (ARA-FINAL)
- **Reviewed batch:** BATCH-H01-FINAL
- **Review signal:** accepted_review_signal
- **Date:** 2026-04-26

## Intent

Close the remaining H01 routing-authority risks by:

- making the unchecked routing entrypoint internal-only (underscore-prefixed,
  excluded from `__all__`, documented as bypass-only),
- strengthening the structural validation inside
  `route_with_gate_evidence` (no string-only checks, no implicit fallbacks),
- detecting indirect bypass (helper / wrapper / re-export) at preflight time
  with a `ROUTING_BYPASS_ATTEMPT` reason code,
- adding replay-integrity tests that exercise the artifact-store + router
  chain end to end.

## Control Boundary

- TLC remains a non-owning routing support surface. It verifies the presence
  and consistency of evaluator-produced gate evidence; it does not own the
  upstream control signal.
- CDE retains sole authority over `allow / warn / freeze / block`.
- The router's vocabulary is neutral: `accepted_for_route` /
  `rejected_for_route` / `gate_evidence_valid` / `gate_evidence_missing`.

## Routing Surface

- `route_with_gate_evidence(artifact, gate_evidence, conditional_route_allowed=False)`
  is the **sole** external routing entrypoint exported from
  `spectrum_systems.modules.orchestration.tlc_router`.
- `_route_artifact_unchecked` is underscore-prefixed, excluded from `__all__`,
  and only legitimate inside `tlc_router.py`.
- `is_terminal`, `pipeline_position`, `validate_transition`,
  `get_full_pipeline`, and `ArtifactRoutingError` remain public for
  inspection / typing only — none of them mutate routing state.

## Replay Guarantees

- `compute_content_hash` (H01B-3) excludes `content_hash`, `trace`, and
  `created_at` so the hash is bound to artifact content, not transport
  metadata.
- `ArtifactStore.register_artifact` recomputes the canonical hash and
  rejects mismatches with `CONTENT_HASH_MISMATCH`.
- Gate evidence carries an optional `target_artifact_id`; when present it
  must match `artifact["artifact_id"]` or routing fails with
  `ARTIFACT_ID_MISMATCH`.
- The artifact store rejects duplicate `artifact_id` registrations, so a
  replay attempt that mutates content while keeping the original id is
  blocked at the store boundary.

## Findings

| ID    | Severity | Description                                                                                                       | Status   |
| ----- | -------- | ----------------------------------------------------------------------------------------------------------------- | -------- |
| F-001 | S4       | Pre-H01B routing entrypoint allowed routing without gate evidence.                                                | resolved |
| F-002 | S3       | Indirect bypass via wrapper / helper / re-export was not detected by preflight.                                   | resolved |
| F-003 | S3       | Gate-evidence validation accepted empty / non-string `eval_summary_id` and non-string `gate_status`.              | resolved |
| F-004 | S3       | Replay integrity tests did not assert that mutated payload + reused gate evidence is rejected at the store seam.  | resolved |
| F-005 | S2       | `route_with_gate_evidence` accepted a non-dict artifact and silently coerced `artifact_type` to `None`.           | resolved |

## Tests Added

- `tests/transcript_pipeline/test_no_unchecked_routing.py` — extended with
  structural validation, preflight bypass-guard cases, and clean-consumer
  negative controls.
- `tests/transcript_pipeline/test_replay_integrity_h01.py` — new file
  covering payload mutation, gate-evidence reuse, conditional gate
  upgrade, and unchecked-symbol bypass attempts.

## Red-Team Findings (post-fix)

- **Direct bypass:** `route_artifact` is not a public attribute; the symbol
  is not in `__all__`. `route_with_gate_evidence` is the only entrypoint.
- **Indirect bypass:** preflight detects `_route_artifact_unchecked`
  imports, calls, re-exports, and public `route_artifact` aliases /
  function definitions outside `tlc_router.py`.
- **Replay attack:** payload mutation invalidates `content_hash`; reusing
  gate evidence with a different `target_artifact_id` is rejected with
  `ARTIFACT_ID_MISMATCH`.
- **Missing eval / trace / artifact:** chaos tests assert BLOCK / FREEZE
  outcomes with reason codes; no silent success paths exist.
- **Authority leakage:** the routing surface uses neutral vocabulary; the
  3LS authority preflight gate-checks protected vocabulary on non-owner
  paths and the AGS-001 shape preflight is clean on the H01 final scope.

No S2+ findings remain.

## Remaining Risk

- **R1 (low):** A future contributor could add a public re-export of an
  unchecked routing helper in a new module that is not changed-file scope
  during preflight. **Mitigation:** the bypass guard fires on any changed
  Python file, and the test suite asserts the guard's pattern set.
- **R2 (low):** The router validates gate evidence shape, not artifact
  content; integrity is delegated to `ArtifactStore`. **Mitigation:**
  `register_artifact` recomputes the canonical hash on every write and
  refuses duplicate ids, so a content-mutated replay is rejected at the
  store boundary even when routing structurally accepts the gate.

## Cleared next phase

H08 — MVP-1 (Transcript Ingestion).
