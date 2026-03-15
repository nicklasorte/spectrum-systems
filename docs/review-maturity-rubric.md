# Claude Review Maturity Rubric

Every Claude architecture or governance review must assign a maturity level and justify it with evidence. Reviews should refuse promotion if evidence is weak or missing and identify both the current level and the next credible level.

## Required sections
1. **Claimed current maturity level** - Explicit level number (0-20) and brief label.
2. **Evidence supporting the claim** - Links to artifacts, runs, telemetry, registries, and contracts that prove the level.
3. **Promotion criteria met** - Evidence that all required capabilities for the claimed level are satisfied.
4. **Promotion criteria not yet met** - Missing proofs that prevent promotion to the next level.
5. **Blocking gaps to next level** - Specific gaps mapped to maturity dimensions and phase criteria.
6. **Risks of false promotion** - Consequences of overstating maturity (e.g., governance drift, untrusted advisories).
7. **Recommended next-level actions** - Ordered steps to close gaps with expected evidence outputs.

## Application notes
- Always map claims to the Level 0-20 playbook and phase criteria.
- Require objective evidence (run manifests, evaluation artifacts, SLO data, provenance records) before promoting.
- Identify the next credible level even if promotion is refused; explain what evidence would unlock it.
- Cross-reference the maturity tracker entry for the system and update it as part of review follow-through.
- Align action items to the review-to-action standard so maturity gaps become trackable work.
