# System Ownership Policy (Canonical Governance)

## Scope
This policy governs **authority-bearing behavior** in Spectrum Systems runtime and preflight surfaces.

## Primary rule
Every governed behavior must map to **exactly one owning 3-letter system**.

Governed behavior includes:
- runtime action execution/approval/enforcement decisions
- orchestration and system handoff paths
- artifact emission paths for authority-bearing artifacts
- preflight classification/repair/escalation control paths

## Support-only and shared utility rules
Support code is allowed, but it must remain non-authoritative.

- `support_only`: may assist owning systems but must not assert ownership, emit owner-only artifacts, or execute owner-only actions.
- shared utilities do not inherit authority from callers.
- authority cannot be inferred from directory placement or import graph.

## Canonical sources and runtime source of truth
1. Ownership declarations: `docs/architecture/system_registry.md`
2. Runtime authority source of truth: normalized `contracts/examples/system_registry_artifact.json` built via `scripts/build_system_registry_artifact.py`

The canonical repair sequence is:
**canonicalize → validate → enforce → bounded repair → escalate**.

## New governed code admission policy
For governed runtime/preflight code paths (`spectrum_systems/modules/runtime/`, `spectrum_systems/orchestration/`, `scripts/`), new/changed files must have one of:

1. explicit `owner_system` (3-letter system), or
2. explicit `classification: support_only`.

Classification is validated through `docs/governance/governed_runtime_code_ownership.json` and enforced in contract preflight.

Docs/tests/examples are excluded from this ownership assignment requirement.

## Waivers (bounded)
Temporary waivers are permitted only through explicit entries in `docs/governance/governed_runtime_code_ownership.json` with:
- `path`
- `reason`
- `expires_on` (ISO date)

Expired waivers fail closed.

## Protected ownership invariants
- `execution` → `PQX`
- `execution_admission` → `AEX`
- `failure_diagnosis` → `FRE`
- `review_interpretation` → `RIL`
- `closure_decisions` → `CDE`
- `enforcement` → `SEL`
- `orchestration` → `TLC`

These invariants are non-negotiable and fail closed.
