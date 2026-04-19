/**
 * Protected File Registry
 *
 * Source of truth for which files require a governance PR to modify.
 * Distinguishes two violation classes:
 * - SHADOW_OWNERSHIP_OVERLAP: files that define system behavior (CLAUDE.md, CI, schemas)
 * - PROTECTED_AUTHORITY_VIOLATION: files that declare governance direction (roadmaps, ADRs, architecture)
 *
 * NOTE: scripts/check_protected_files.py is NOT in this list.
 * The script itself is safe to ship in a feature PR.
 * Only .github/workflows/ (which wires the script into CI) is protected.
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
  // === SHADOW_OWNERSHIP_OVERLAP paths ===
  // Files that define system behavior and cannot be self-modified
  {
    path: "CLAUDE.md",
    reason: "Agent authority document — defines agent behavior and system standards",
    owner: "system-authority",
    change_requires: "governance_pr",
    violation_class: "SHADOW_OWNERSHIP_OVERLAP",
    example_fix: "git checkout main -- CLAUDE.md",
  },
  {
    path: "AGENTS.md",
    reason: "Agent standards document — injected agent memory per Canonical Harness spec",
    owner: "system-authority",
    change_requires: "governance_pr",
    violation_class: "SHADOW_OWNERSHIP_OVERLAP",
    example_fix: "git checkout main -- AGENTS.md",
  },
  {
    path: "scripts/run_system_registry_guard.py",
    reason: "Registry guard enforcement — cannot be self-modified via feature PR",
    owner: "system-authority",
    change_requires: "governance_pr",
    violation_class: "SHADOW_OWNERSHIP_OVERLAP",
    example_fix: "Open a [GOVERNANCE] PR to modify the registry guard",
  },
  {
    path: ".github/workflows/",
    reason: "CI/CD pipelines — changes affect all builds and enforcement gates",
    owner: "system-authority",
    change_requires: "governance_pr",
    violation_class: "SHADOW_OWNERSHIP_OVERLAP",
    example_fix: "Open a [GOVERNANCE] PR to add or modify workflows",
  },
  {
    path: "contracts/schemas/",
    reason: "Core artifact schemas — changes can break backward compatibility",
    owner: "schema-registry",
    change_requires: "governance_pr",
    violation_class: "SHADOW_OWNERSHIP_OVERLAP",
    example_fix: "Open a [GOVERNANCE] PR with schema migration plan",
  },

  // === PROTECTED_AUTHORITY_VIOLATION paths ===
  // Files that declare governance direction and require explicit authorship + ratification
  {
    path: "docs/roadmaps/",
    reason: "System roadmaps declare governance direction — require explicit authorship + ratification",
    owner: "governance-authority",
    change_requires: "governance_pr",
    violation_class: "PROTECTED_AUTHORITY_VIOLATION",
    example_fix: "Open a [GOVERNANCE] PR titled '[GOVERNANCE] Phase X Roadmap'",
  },
  {
    path: "docs/architecture/",
    reason: "Architecture decisions are authority documents — require ADR process",
    owner: "governance-authority",
    change_requires: "governance_pr",
    violation_class: "PROTECTED_AUTHORITY_VIOLATION",
    example_fix: "Open a [GOVERNANCE] PR following the ADR template",
  },
  {
    path: "docs/adr/",
    reason: "Architectural Decision Records — immutable authority once ratified",
    owner: "governance-authority",
    change_requires: "governance_pr",
    violation_class: "PROTECTED_AUTHORITY_VIOLATION",
    example_fix: "Open a [GOVERNANCE] PR with new ADR number",
  },
];

export class ProtectedFileRegistry {
  private protectedPaths: Map<string, ProtectedFile> = new Map();

  constructor() {
    for (const file of PROTECTED_FILES) {
      this.protectedPaths.set(file.path, file);
    }
  }

  /**
   * Check if a file path is protected
   * Supports both exact paths and directory prefixes
   */
  isProtected(filePath: string): { protected: boolean; file?: ProtectedFile } {
    // Exact match
    const exactMatch = this.protectedPaths.get(filePath);
    if (exactMatch) {
      return { protected: true, file: exactMatch };
    }

    // Directory prefix match
    for (const [protectedPath, protectedFile] of this.protectedPaths.entries()) {
      if (protectedPath.endsWith("/") && filePath.startsWith(protectedPath)) {
        return { protected: true, file: protectedFile };
      }
    }

    return { protected: false };
  }

  /**
   * Validate a list of changed files
   * Returns violations grouped by violation class
   */
  validateChangedFiles(changedFiles: string[]): {
    violations: Array<{ file: string; reason: string; change_requires: string; violation_class: ViolationClass; example_fix: string }>;
    reason_codes: ViolationClass[];
    clean: boolean;
  } {
    const violations: Array<{ file: string; reason: string; change_requires: string; violation_class: ViolationClass; example_fix: string }> = [];
    const violationClassesFound = new Set<ViolationClass>();

    for (const file of changedFiles) {
      const check = this.isProtected(file);
      if (check.protected && check.file) {
        violations.push({
          file,
          reason: check.file.reason,
          change_requires: check.file.change_requires,
          violation_class: check.file.violation_class,
          example_fix: check.file.example_fix,
        });
        violationClassesFound.add(check.file.violation_class);
      }
    }

    return {
      violations,
      reason_codes: Array.from(violationClassesFound),
      clean: violations.length === 0,
    };
  }
}
