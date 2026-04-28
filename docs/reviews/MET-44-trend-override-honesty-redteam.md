# MET-44 Trend and Override Honesty Red-Team

## Prompt type
REVIEW

## Findings

### must_fix
1. **Trend-ready pack can hide insufficiency if cases_needed is not explicit for every insufficient pack.**
2. **Override adapter needs explicit absent-state warning when canonical source is not found.**

### should_fix
1. Comparable case gate should keep strict rule metadata visible in API block.
2. Dashboard trend-readiness panel should display unknown state without fallback zero.

### observation
1. No synthetic trend fields were introduced.
2. Override evidence count remains unknown when canonical source is absent.
