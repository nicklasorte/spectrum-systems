# MVP-10: Human Review Gate

HUMAN-IN-THE-LOOP. Pipeline pauses here for human review.

## Process

1. Emit require_human_review enforcement_action
2. Human receives draft + eval_summary
3. Human fills review form
4. Human submits review_artifact with decision + findings

## Decision

- approve: No changes needed
- revise: Changes required (S2 findings)
- reject: Reject draft (S3/S4 findings)

## Severity Ladder

- S0/S1: Minor, approve
- S2: Significant, pass_with_fixes → MVP-11
- S3/S4: Critical, reject

## Gate-4

Checks: review_artifact present, reviewer identity valid, decision recorded.
