# HNX-01 Red Team Review 2 — Replay / Trace / Stale-State / Hidden-State / Entropy

- Verdict: **FAIL (fixed in Fix Pack 2)**

## Findings
1. Critical: stale checkpoint acceptance risk without freshness guard.
2. Critical: hidden-state variance could pass without repeated-run comparison.
3. High: trace-linkage mismatch between checkpoint and resume not explicitly blocked.
4. Medium: observability lacked replay mismatch and unresolved feedback metrics.

## Required fixes
- Enforce stale checkpoint rejection and trace linkage match.
- Add repeated-run variance detection in replay validation.
- Expand effectiveness metrics for replay mismatch/unresolved feedback rates.
