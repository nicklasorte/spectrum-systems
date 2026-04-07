# Strategy Control Document

## Purpose
Define the authoritative strategy controls for governed execution.

## Canonical anchors
Strategy decisions must align to:
1. `README.md`
2. `docs/architecture/system_registry.md`

## Governing model
Spectrum Systems operates as a governed runtime with these mandatory properties:
1. **Artifact-first execution**
2. **Fail-closed behavior**
3. **Promotion requires certification**

## Canonical role ownership
Use role ownership from the system registry only:
`RIL`, `CDE`, `TLC`, `PQX`, `FRE`, `SEL`, `PRG`.

No strategy artifact may redefine these boundaries.

## Execution flow (authoritative)
1. Retrieve authority inputs.
2. Validate required artifacts.
3. Execute bounded work.
4. Evaluate outcomes.
5. Enforce control decisions.
6. Decide closure/promotion state.

## Promotion rule
Promotion is allowed only when certification evidence artifacts are present and valid.
Missing certification is a blocking failure.

## Failure handling rule
Any missing authority, missing artifact, or role conflict is a blocking failure and must fail closed.

## Reference depth rule
High-impact documents must keep required references one level deep.
