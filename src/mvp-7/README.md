# MVP-7: Structured Issue Set

Reorganizes issues into structure required for paper generation.

## Output

structured_issue_set with:
- All issues from issue_registry
- spectrum_band: C | L | S
- policy_section: findings | actions | risks
- paper_section_id: section-4 | section-5 | section-6

## Logic

Maps each issue to target paper section deterministically.
