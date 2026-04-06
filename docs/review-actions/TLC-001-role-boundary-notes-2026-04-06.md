# TLC-001 Role-Boundary Notes (2026-04-06)

## Purpose
Document the mandatory orchestration-only boundary for the Top-Level Conductor (TLC).

## TLC boundary contract
- TLC orchestrates only.
- TLC does **not** execute work directly; execution is delegated to PQX.
- TLC does **not** parse or classify review output; review interpretation is delegated to RIL.
- TLC does **not** generate recovery logic; recovery generation/execution orchestration is delegated to FRE.
- TLC does **not** create policy; governance and policy behavior remains outside TLC.
- TLC does **not** replace roadmap logic; next-step direction is delegated to PRG.
- TLC does **not** enforce boundaries itself; boundary checks are delegated to SEL.
- TLC consumes CDE closure decisions exactly as emitted and does not reinterpret decision meaning.

## Deterministic bounded behavior
- TLC is a deterministic finite state machine for one bounded run.
- TLC must stop explicitly in one of terminal states: `ready_for_merge`, `blocked`, `exhausted`, or `escalated`.
- No open-ended loops are permitted.
