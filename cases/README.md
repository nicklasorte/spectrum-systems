# Cases

This directory contains canonical case definitions for system evaluation and contract conformance testing. Cases are structured inputs that exercise specific system behaviors across the governed systems in this repository.

## Purpose

Cases provide:
- Versioned, reproducible inputs for evaluation harnesses in downstream engine repos.
- Coverage of normal, edge, and regression scenarios that validate contract conformance.
- Structured signal expectations that downstream engines can score outputs against.

## Relationship to other directories

| Directory | Role |
| --- | --- |
| `cases/<system>/` | Input-side case contracts and example fixtures (this directory) |
| `eval/<system>/` | Output-side evaluation assets: rubrics, test matrices, expected outputs |
| `contracts/` | Authoritative artifact contracts that governed outputs must satisfy |
| `contracts/schemas/` | JSON Schemas for validating governed output payloads |

Cases define **what goes in**. The `eval/` directory defines **what comes out** and how it is scored.

## Directory layout

```
cases/
└── meeting_minutes/       # Canonical cases for the Meeting Minutes Engine (SYS-006)
    ├── README.md
    ├── case-input-contract.yaml   # Canonical case input template
    ├── case-input.schema.json     # JSON Schema for case validation
    ├── signal-extraction.yaml     # Structured signal extraction specification
    └── examples/                  # Example cases (normal, edge, regression)
```

## Adding new system cases

1. Create `cases/<system-name>/` following the `meeting_minutes/` layout.
2. Define a `case-input-contract.yaml` that declares required and optional fields for cases targeting that system.
3. Provide a `case-input.schema.json` that validates case YAML files.
4. Add at least one normal, one edge, and one regression example under `examples/`.
5. Register the case directory in `docs/system-map.md` and the corresponding `eval/<system>/README.md`.

## Governance

Cases are governed by the standards in this repository. Case inputs must:
- Reference the contract version they are designed to validate.
- Be synthetic or sanitized — no operational data.
- Include explicit expected signal counts or signal patterns where outcomes can be asserted deterministically.
- Record the case schema version so downstream harnesses know which validator to apply.
