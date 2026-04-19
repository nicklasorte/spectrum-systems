/**
 * Protected File Registry
 *
 * Source of truth for which files require a [GOVERNANCE] PR to modify.
 *
 * Two violation classes:
 * - SHADOW_OWNERSHIP_OVERLAP: system behavior files
 * - PROTECTED_AUTHORITY_VIOLATION: governance direction files
 *
 * Note: This file itself is safe to ship in a feature PR.
 * The CI workflow that activates it requires a [GOVERNANCE] PR.
 */

export type ViolationClass = "SHADOW_OWNERSHIP_OVERLAP" | "PROTECTED_AUTHORITY_VIOLATION";

export interface ProtectedFile {
  path: string;
  reason: string;
  owner: string;
  change_requires: "governance_pr" | "admin_override";
  violation_class: ViolationClass;
  example_fix: string;
}

export const PROTECTED_FILES: ProtectedFile[] = [
  // System behavior files (SHADOW_OWNERSHIP_OVERLAP)
  {
    path: "CLAUDE.md",
    reason: "Agent configuration document",
    owner: "system-authority",
    change_requires: "governance_pr",
    violation_class: "SHADOW_OWNERSHIP_OVERLAP",
    example_fix: "git checkout main -- CLAUDE.md",
  },
  {
    path: "AGENTS.md",
    reason: "Agent standards document",
    owner: "system-authority",
    change_requires: "governance_pr",
    violation_class: "SHADOW_OWNERSHIP_OVERLAP",
    example_fix: "git checkout main -- AGENTS.md",
  },
  {
    path: "scripts/run_system_registry_guard.py",
    reason: "Registry guard — requires [GOVERNANCE] PR to modify",
    owner: "system-authority",
    change_requires: "governance_pr",
    violation_class: "SHADOW_OWNERSHIP_OVERLAP",
    example_fix: "Open a [GOVERNANCE] PR",
  },
  {
    path: ".github/workflows/",
    reason: "CI/CD pipeline definitions",
    owner: "system-authority",
    change_requires: "governance_pr",
    violation_class: "SHADOW_OWNERSHIP_OVERLAP",
    example_fix: "Open a [GOVERNANCE] PR to add or modify workflows",
  },
  {
    path: "contracts/schemas/",
    reason: "Artifact schema definitions",
    owner: "schema-registry",
    change_requires: "governance_pr",
    violation_class: "SHADOW_OWNERSHIP_OVERLAP",
    example_fix: "Open a [GOVERNANCE] PR with schema migration plan",
  },
  // Governance direction files (PROTECTED_AUTHORITY_VIOLATION)
  {
    path: "docs/roadmaps/",
    reason: "Roadmap documents",
    owner: "governance-authority",
    change_requires: "governance_pr",
    violation_class: "PROTECTED_AUTHORITY_VIOLATION",
    example_fix: "Open a [GOVERNANCE] PR titled '[GOVERNANCE] Phase X Roadmap'",
  },
  {
    path: "docs/architecture/",
    reason: "Architecture decision documents",
    owner: "governance-authority",
    change_requires: "governance_pr",
    violation_class: "PROTECTED_AUTHORITY_VIOLATION",
    example_fix: "Open a [GOVERNANCE] PR following the ADR template",
  },
  {
    path: "docs/adr/",
    reason: "Architectural Decision Records",
    owner: "governance-authority",
    change_requires: "governance_pr",
    violation_class: "PROTECTED_AUTHORITY_VIOLATION",
    example_fix: "Open a [GOVERNANCE] PR with new ADR number",
  },
];

export class ProtectedFileRegistry {
  private entries: ProtectedFile[];

  constructor(entries: ProtectedFile[] = PROTECTED_FILES) {
    this.entries = entries;
  }

  isProtected(filePath: string): { protected: boolean; file?: ProtectedFile } {
    for (const entry of this.entries) {
      if (entry.path.endsWith("/")) {
        if (filePath.startsWith(entry.path)) {
          return { protected: true, file: entry };
        }
      } else {
        if (filePath === entry.path) {
          return { protected: true, file: entry };
        }
      }
    }
    return { protected: false };
  }

  validateChangedFiles(changedFiles: string[]): {
    violations: Array<{
      file: string;
      reason: string;
      change_requires: string;
      violation_class: ViolationClass;
      example_fix: string;
    }>;
    clean: boolean;
  } {
    const violations = changedFiles
      .map((f) => ({ file: f, check: this.isProtected(f) }))
      .filter((x) => x.check.protected)
      .map((x) => ({
        file: x.file,
        reason: x.check.file!.reason,
        change_requires: x.check.file!.change_requires,
        violation_class: x.check.file!.violation_class,
        example_fix: x.check.file!.example_fix,
      }));

    return { violations, clean: violations.length === 0 };
  }
}
