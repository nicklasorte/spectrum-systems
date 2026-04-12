# PLAN-PQX-005-CHANGED-PATH-PREFLIGHT-GUARD-2026-04-12

## Primary Prompt Type
BUILD

## Scope
Fix preflight wrapper changed-path resolution insufficiency in pull_request contexts, preserve fail-closed governance, and add durable compatibility guards.

## Ordered Steps
1. Reproduce failing wrapper build with provided PR SHAs and inspect changed-path resolver behavior.
2. Patch canonical changed-path derivation seam to support PR/push context robustly without fail-open behavior.
3. Keep wrapper/preflight hardening compatibility aligned and deterministic.
4. Add durable tests for push + pull_request + ambiguous ref fail-closed behavior.
5. Add/maintain compatibility guard ensuring built wrapper validates and preflight passes.
6. Run required tests and failing commands; deliver report.
