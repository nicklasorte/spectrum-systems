# Design Review Process

## Artifact Requirement

Every external architecture review (Claude, GPT, or human) must result in a tracked artifact in this repository.

Reviews must be converted into one or more of the following:

- ADR (Architecture Decision Record)
- Finding Issue
- Design Review Artifact under `/design-reviews/`

No review should exist only as chat output.

The repository is the source of truth for architectural decisions and findings.

## CI Surfacing of Repository Actions

Architecture reviews placed in `/design-reviews/` will automatically be scanned by CI.
The workflow surfaces recommended repository actions in the GitHub job summary so maintainers can quickly convert them into ADRs or issues.
