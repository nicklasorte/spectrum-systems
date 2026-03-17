# Meeting Minutes Cases

Canonical case library for the Meeting Minutes Engine (SYS-006). Cases here define structured inputs for exercising and evaluating the engine against `contracts/meeting_minutes_contract.yaml`.

## Purpose

- Provide deterministic, versioned case inputs covering normal operation, edge conditions, and regression scenarios.
- Define expected signal counts and extraction patterns so downstream evaluation harnesses can score outputs.
- Document the canonical shape of a meeting minutes case so all contributors and engine implementations use a consistent structure.

## Contract anchor

All outputs produced from these cases must conform to `contracts/meeting_minutes_contract.yaml`. Cases reference the contract version they are designed to exercise. Do not modify the output contract to fit a case — update the case instead.

## Directory layout

```
cases/meeting_minutes/
├── README.md                        # This file
├── case-input-contract.yaml         # Canonical case input template (all fields defined)
├── case-input.schema.json           # JSON Schema for validating case YAML files
├── signal-extraction.yaml           # Structured signal extraction specification
└── examples/
    ├── README.md                    # Index of example cases with scenario descriptions
    ├── case-001-standard-working-session/
    │   ├── case.yaml                # Case metadata and expected signals
    │   └── transcript.txt           # Synthetic transcript input
    ├── case-002-high-signal-decisions/
    │   ├── case.yaml
    │   └── transcript.txt
    └── case-003-edge-missing-timestamps/
        ├── case.yaml
        └── transcript.txt
```

## Case types

| Type | Description |
| --- | --- |
| `standard` | Normal working-session transcript with all expected signals present |
| `edge` | Boundary condition: missing timestamps, no decisions, incomplete attendee list |
| `regression` | Previously failed scenario captured to prevent recurrence |
| `adversarial` | Inputs designed to probe failure modes (e.g., extra fields, schema violations) |

## Adding a new case

1. Create a subdirectory under `examples/` using the naming convention `case-NNN-<short-description>/`.
2. Add `case.yaml` (conforming to `case-input-contract.yaml` and validated by `case-input.schema.json`).
3. Add `transcript.txt` or reference an external transcript path in `case.yaml`.
4. Register the case in `examples/README.md`.
5. If the case exercises a new failure mode, add an entry to `docs/system-failure-modes.md`.

## Governance

- Cases must be synthetic or sanitized — no operational data.
- `case_schema_version` in each `case.yaml` must match the version in `case-input-contract.yaml`.
- Cases that change expected signal counts require a review comment explaining the rationale.
