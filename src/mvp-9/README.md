# MVP-9: Draft Quality Eval Gate

Gate-3: Validates generation step before human review.

## 6 Eval Cases

1. schema_conformance
2. issue_coverage (all issues in draft)
3. section_completeness (all 5 sections)
4. internal_consistency
5. replay_consistency
6. quality_score (Haiku critic)

## Block Condition

Missing spectrum findings, missing section, critic score < threshold.

## Decision

Pass ≥ 80% → allow to MVP-10 (human review)
Fail < 80% → block, emit failure
