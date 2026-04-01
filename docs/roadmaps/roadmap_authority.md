# Roadmap Authority — Operational Note

## Primary strategy authority (must be resolved first)
- **Primary governing document:** `docs/architecture/strategy-control.md`
- **Mandatory foundation architecture authority:** `docs/architecture/foundation_pqx_eval_control.md`
- Roadmap generation input order is mandatory:
  1. `docs/architecture/strategy-control.md`
  2. `docs/architecture/foundation_pqx_eval_control.md`
  3. current repository state
  4. current roadmap (`docs/roadmaps/system_roadmap.md` + required compatibility mirror)
  5. source design documents / architecture artifacts
- Every roadmap step must validate alignment against strategy invariants and foundation chain hardening requirements before execution.

## Foundation-first gate (non-compliance if violated)
- Roadmap generation must compare repository state against `docs/architecture/foundation_pqx_eval_control.md` before proposing steps.
- Expansion is blocked when required foundation layers are missing, partial, bypassable, or ambiguous.
- If foundation and roadmap disagree, record mismatch as a foundation gap and prioritize closure; do not rewrite architecture.

## Active roadmap authority file
- **Active editorial authority:** `docs/roadmaps/system_roadmap.md`

## Compatibility rule (B1 transition)
- **Operational compatibility mirror (required until migration complete):** `docs/roadmap/system_roadmap.md`
- The compatibility mirror must remain parseable for existing PQX/tests that still consume `docs/roadmap/system_roadmap.md`.
- During transition, updates to roadmap rows that affect operational parsing must be mirrored in both surfaces.
- Strategic revisions in active authority must not remove legacy executable step IDs/rows from `docs/roadmap/system_roadmap.md` unless runtime/tests are migrated in the same slice.
- Compatibility surfaces must remain aligned to the step execution contract in `docs/roadmap/roadmap_step_contract.md`.

## March 31, 2026 gate note
- The March 31, 2026 roadmap revision adds a mandatory **Control Loop Closure Gate** before broader expansion.
- Future roadmap updates must not skip or bypass this pre-expansion gate.
- RE-05 correction semantics are binding: Phase A (`CL-01..CL-05`) then Phase B (`NX-01..NX-03`) only, with a hard Control Loop Closure Certification Gate pass required before any `NX-04+`.
- Dominant unresolved bottleneck remains enforced learning/recurrence-prevention authority; authority updates must preserve proof-before-scale behavior and must not overstate true closed-loop MVP status.

## PQX authority resolution bridge (B2)
- PQX must resolve roadmap authority from this document first, not from ad-hoc hardcoded path selection.
- Deterministic resolution contract:
  1. Active authority must resolve to `docs/roadmaps/system_roadmap.md`.
  2. Machine-executable roadmap must resolve to `docs/roadmap/system_roadmap.md` until cutover.
  3. If either declaration is missing, ambiguous, or malformed, PQX must fail closed.
- Compatibility integrity rule:
  - `docs/roadmaps/system_roadmap.md` must explicitly declare the compatibility transition rule.
  - `docs/roadmap/system_roadmap.md` must explicitly declare the active authority and remain aligned to `docs/roadmap/roadmap_step_contract.md`.
  - Any mismatch blocks execution.

## Roadmap generator authority normalization
- Reusable roadmap generator prompt authority surface: `docs/architecture/strategy_guided_roadmap_prompt.md`.
- Generator authority note surface: `docs/roadmaps/roadmap_generator_authority.md`.
- Competing roadmap-generator prompt variants are non-compliant; stale variants must be marked and not used for generation.

## Allowed supporting docs
These support execution but are not top-level authority documents:
- `docs/roadmaps/execution_state_inventory.md`
- `docs/roadmaps/codex-prompt-roadmap.md` (reference slicing context)
- `docs/roadmaps/operational-ai-systems-roadmap.md` (historical/reference)
- `docs/roadmap/pqx_queue_roadmap.md` (subordinate queue track)
- `docs/roadmap/pqx_protocol_hardening.md` (subordinate protocol track)
- `docs/roadmap/pqx_execution_map.md` (execution map reference)

## How old roadmaps are treated
- `docs/roadmap/system_roadmap.md`: subordinate for editorial governance, but required as an operational compatibility mirror during migration.
- `docs/roadmap.md`: deprecated historical artifact (subordinate reference only).
- Any roadmap-like document outside `docs/roadmaps/system_roadmap.md` is subordinate planning material or reference history.

## Where future status updates belong
- Editorial status/dependencies/execution-order updates belong in `docs/roadmaps/system_roadmap.md`.
- Implementation-reality updates belong in `docs/roadmaps/execution_state_inventory.md`.
- Compatibility updates needed for legacy consumers must also be mirrored into `docs/roadmap/system_roadmap.md` until migration closes.

## Where future bundle planning belongs
- Create bundle plans in `docs/review-actions/PLAN-<BUNDLE>-<DATE>.md`.
- Keep each plan’s declared file scope explicit and enforce changed-scope verification.

## How design reviews feed roadmap changes
- Review outputs are authored in `docs/reviews/`.
- Follow-up actions are tracked in `docs/review-actions/`.
- After review findings are accepted, update the active roadmap and (if required) the compatibility mirror in one change set.

## Migration closure trigger
- A future migration slice should retire the compatibility mirror only after PQX/runtime/tests stop consuming `docs/roadmap/system_roadmap.md` and pass against the new authority surface alone.
