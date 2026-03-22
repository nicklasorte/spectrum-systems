# Architecture Review Action Tracker — Policy Versioning Governance Audit (BAS)

- **Source Review:** `docs/reviews/2026-03-22-policy-versioning-audit.md`
- **Owner:** TBD
- **Last Updated:** 2026-03-22

## Critical Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| PV-CR-1 | Remove permissive fallback from `policy_registry.py` step-3 resolution; replace with raised `PolicyResolutionError`; update all callers to pass explicit `policy_id` | TBD | Open | None | Current fallback silently applies permissive to decision-grade artifacts when caller omits policy_id |
| PV-CR-2 | Enforce policy immutability: restructure policy registries as append-only (versioned individual files + manifest) or content-addressed (hash-derived policy_id); add CI enforcement rejecting in-place edits to existing policy definitions | TBD | Open | None | All three policy registries are currently mutable JSON files with no write-once protection |
| PV-CR-3 | Replace `policy_id: "default"` in `config/regression_policy.json` with a unique version-tagged identifier; update all references; define namespace convention for the three policy identity spaces (gov:, slo:, named-version) | TBD | Open | None | "default" encodes ambient fallback semantics into identity; violates uniqueness and unambiguity requirements |

## High-Priority Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| PV-HI-1 | Add `policy_id` as a required field to `governance/schemas/provenance.schema.json` and `schemas/provenance-schema.json`; bump schema versions; document migration for existing records | TBD | Open | PV-CR-3 (policy_id values must be valid before requiring them in provenance) | Provenance records currently carry no policy_id; artifacts cannot be traced to governing policy at audit time |
| PV-HI-2 | Add version history fields to all policy entries in all registries: `schema_version`, `created_at`, `last_modified_at`, `status` (draft/active/retired), `superseded_by`; update registry schemas to enforce these as required; backfill existing entries from git history | TBD | Open | PV-CR-2 (append-only structure makes this easier and correct) | Without these fields, it is impossible to reconstruct what any policy required at a given historical date |

## Medium-Priority Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| PV-MI-1 | Activate Phase 2 CI enforcement (automated schema and contract validation); make it a hard prerequisite before any artifact is designated production-grade | TBD | Open | PV-CR-1, PV-HI-1 (CI must validate new provenance schema shape) | Phase 2 is designed and documented but not yet operational; snapshot consistency has no automated gate |
| PV-MI-2 | Register policy registries (`slo_policy_registry`, `regression_policy`, governance policy registry) as versioned entries in `contracts/standards-manifest.json` so governance state can be reconstructed from a single manifest snapshot | TBD | Open | PV-CR-2 (stable policy versions needed before manifesting them) | Current manifest tracks contract versions but not policy versions |

## Low-Priority Items
| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
| --- | --- | --- | --- | --- | --- |
| PV-LI-1 | Define cross-namespace policy identity collision registry; add CI check verifying `policy_id` uniqueness across all three policy registries | TBD | Open | PV-CR-3 (namespacing convention must be decided first) | Three independent policy identity spaces with no cross-namespace deduplication |
| PV-LI-2 | Add governance policy GOV-011 to detect artifacts where permissive treatment was applied to a stage that maps to decision_grade binding; emit as error severity | TBD | Open | PV-CR-1 (after fallback is removed, this becomes a safety net for misconfigured callers) | Would surface fallback-policy misapplication as a detectable governance check |

## Blocking Items
- **PV-CR-1** blocks trust in any enforcement result artifact — the policy under which evaluation occurred is not verifiable without an explicit `policy_id` in the result.
- **PV-CR-2** blocks any historical audit claim — policy definitions are currently mutable; past policy state cannot be proven.
- **PV-HI-1** blocks external auditability of any provenance record — artifacts cannot be traced to their governing policy.

## Deferred Items
- Cross-repo audit of downstream implementation repos for `policy_id` propagation correctness — trigger: when RF-1 (fail-closed resolution) and RF-4 (provenance schema update) are implemented and deployed to at least one downstream engine repo.
- Re-audit of policy scope clarity and stage binding completeness — trigger: when any new stage type is introduced to the SLO policy registry.
