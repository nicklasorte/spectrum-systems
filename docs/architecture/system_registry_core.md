# System Registry — Core (Companion View)

This document is an explanatory companion only.

`docs/architecture/system_registry.md` remains the sole canonical ownership and enforcement source.

This file must not define or restate canonical ownership.

## Purpose

Provide a compact reference view of the runtime spine and nearby planes for quick reading.

For canonical definitions, invariants, and machine-facing compatibility, see `docs/architecture/system_registry.md`.

## Runtime spine summary

Primary chain:

- AEX → PQX → EVL → TPA → CDE → SEL

Gate overlays used in the same flow:

- REP
- LIN
- OBS

## Nearby planes (summary view)

These names are listed as descriptive context:

- TLC
- FRE
- RIL
- PRG

## Read path

Use this order when reading architecture docs:

1. `docs/architecture/system_registry.md` (canonical)
2. `docs/architecture/runtime_spine.md` (explanatory control-flow view)
3. `docs/architecture/system_registry_support.md` (support-family grouping)
4. `docs/architecture/system_registry_reserved.md` (reserved-name reference)
