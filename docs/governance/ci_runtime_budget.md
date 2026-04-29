# CI Runtime Budget

**Version:** 1.0.0  
**Produced:** 2026-04-29  
**Owner:** Governance Gate

---

## Purpose

Defines time budgets for each canonical gate across PR, nightly, and release runs. Budget enforcement prevents CI sprawl from re-accumulating through slow tests being promoted to the PR path.

---

## Fast PR Gate Budgets

Target: **≤ 4 minutes total wall-clock time per PR**.

| Gate | Step | Budget | Notes |
|---|---|---|---|
| Contract Gate | Artifact boundary check | ≤ 10s | Fast Python static check |
| Contract Gate | Module architecture validation | ≤ 5s | Fast static check |
| Contract Gate | Orchestration boundary validation | ≤ 5s | Fast static check |
| Contract Gate | Authority shape preflight | ≤ 10s | Suggest-only, non-blocking |
| Contract Gate | Authority drift guard | ≤ 10s | Git-diff-based |
| Contract Gate | System registry guard | ≤ 10s | Registry parse + diff |
| Contract Gate | Authority leak guard | ≤ 10s | Static analysis |
| Contract Gate | Preflight + PQX wrapper | ≤ 30s | Core preflight |
| **Contract Gate total** | | **≤ 90s** | |
| Test Selection Gate | Select and validate targets | ≤ 10s | Pure artifact reads + policy |
| **Test Selection Gate total** | | **≤ 10s** | |
| Runtime Test Gate | Pytest execution (selected targets) | ≤ 120s | Path-targeted subset |
| **Runtime Test Gate total** | | **≤ 120s** | |
| Governance Gate | Strategy compliance (path-gated) | ≤ 15s | Only on touched paths |
| Governance Gate | Registry drift (path-gated) | ≤ 15s | Only on touched paths |
| Governance Gate | Review artifact validation (path-gated) | ≤ 15s | Only on touched paths |
| **Governance Gate total** | | **≤ 45s** | Max when all checks run |
| Certification Gate | Eval CI smoke | ≤ 30s | Example fixtures only |
| Certification Gate | SEL replay smoke | ≤ 15s | Fast mode |
| Certification Gate | Failure injection smoke | ≤ 15s | Fast mode |
| **Certification Gate total (fast)** | | **≤ 60s** | Only when cert paths touched |
| **PR Gate total** | | **≤ 325s (~5.5 min)** | Worst case all gates |
| **PR Gate total (typical)** | | **≤ 4 min** | Most PRs skip cert gate |

---

## Nightly Deep Gate Budgets

Target: **≤ 30 minutes total**.

| Gate | Step | Budget | Notes |
|---|---|---|---|
| Contract Gate | Full preflight | ≤ 90s | Same as PR |
| Runtime Test Gate | Full pytest suite | ≤ 900s | All 835+ test files |
| Governance Gate | All governance checks | ≤ 120s | No path filtering |
| Certification Gate | Full eval CI + SEL replay | ≤ 120s | Full dataset |
| Certification Gate | Lineage validation | ≤ 60s | Full chain check |
| Certification Gate | Done certification | ≤ 60s | Full GOV-10 check |
| Certification Gate | Chaos / fail-closed tests | ≤ 120s | Deep chaos suite |
| Cross-repo compliance | Full compliance scan | ≤ 300s | Weekly / nightly |
| **Nightly total** | | **≤ 28 min** | |

---

## Release Gate Budgets

Target: **≤ 45 minutes total** (superset of nightly).

| Gate | Step | Budget | Notes |
|---|---|---|---|
| All nightly gates | | ≤ 28 min | As above |
| Release canary | Baseline/candidate comparison | ≤ 120s | |
| Certification Gate | Full promotion readiness | ≤ 120s | |
| **Release total** | | **≤ 33 min** | |

---

## Budget Enforcement Rules

1. **Never move slow checks to the PR path without explicit governance approval.** Full pytest (835+ files) is nightly only.
2. **Chaos/replay/deep certification tests run in nightly mode only** unless cert-relevant paths are explicitly touched.
3. **Cross-repo compliance runs weekly (schedule) or on main push** — not on every PR.
4. **Dashboard deploy gate runs only when dashboard paths are touched** (path-filtered).
5. **Any new test added to the PR path must justify the runtime cost** — it must be bounded within the target budget.

---

## Assignment Policy

| Test type | Default assignment |
|---|---|
| Unit tests (fast, < 1s each) | PR path |
| Integration tests (1–10s each) | PR path if path-relevant, nightly otherwise |
| End-to-end tests (> 10s each) | Nightly only |
| Replay/lineage tests | Nightly only (unless cert paths touched) |
| Chaos/injection tests | Nightly only |
| Cross-repo compliance | Weekly/nightly |
| Release canary | Release gate only |
