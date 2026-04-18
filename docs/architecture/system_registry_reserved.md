# System Registry — Reserved and Non-Active

This document is an additive explanatory view. Canonical compatibility and enforcement source remains `docs/architecture/system_registry.md` until dedicated tooling migration is completed.

This document tracks reserved acronyms, placeholder seams, and future candidates.

## Status rule

Reserved entries are **non-active by default**.

Reserved entries are naming reservations only. They are not architecture commitments, not authority grants, and not implementation promises.

## Activation requirement

A reserved entry may move to active status only by same-change updates that include:

1. Canonical owner registration in `system_registry_core.md` or explicit support-family placement in `system_registry_support.md`.
2. Enforced contract surface definition.
3. Tested fail-closed boundary.
4. Explicit authority boundary and must-not-do clauses.
5. Documentation updates in `runtime_spine.md` where gate semantics are affected.

## Current reserved/non-active set

Examples (non-exhaustive):
- LCE, ABX, DBB, SAL, SAS, SHA, RAX, SIV

Legacy placeholders and future seams should be listed here rather than modeled as peer runtime authorities.
