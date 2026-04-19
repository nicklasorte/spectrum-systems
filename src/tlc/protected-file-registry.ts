/**
 * Protected File Registry
 *
 * Source of truth for which files require a governance PR to modify.
 *
 * NOTE: scripts/check_protected_files.py is NOT in this list.
 * The script itself is safe to ship in a feature PR.
 * Only .github/workflows/ (which wires the script into CI) is protected.
 */

export interface ProtectedFile {
  path: string;
  reason: string;
  owner: string;
  change_requires: "governance_pr" | "admin_override";
  example_fix: string;
}

export const PROTECTED_FILES: ProtectedFile[] = [
  {
    path: "CLAUDE.md",
    reason: "Agent authority document — defines agent behavior and system standards",
    owner: "system-authority",
    change_requires: "governance_pr",
    example_fix: "git checkout main -- CLAUDE.md",
  },
  {
    path: "AGENTS.md",
    reason: "Agent standards document — injected agent memory per Canonical Harness spec",
    owner: "system-authority",
    change_requires: "governance_pr",
    example_fix: "git checkout main -- AGENTS.md",
  },
  {
    path: "scripts/run_system_registry_guard.py",
    reason: "Registry guard enforcement — cannot be self-modified via feature PR",
    owner: "system-authority",
    change_requires: "governance_pr",
    example_fix: "Open a governance PR titled [GOVERNANCE] ...",
  },
  {
    path: ".github/workflows/",
    reason: "CI/CD pipelines — changes affect all builds and enforcement gates",
    owner: "system-authority",
    change_requires: "governance_pr",
    example_fix: "Open a governance PR titled [GOVERNANCE] to add or modify workflows",
  },
  {
    path: "contracts/schemas/",
    reason: "Core artifact schemas — changes can break backward compatibility",
    owner: "schema-registry",
    change_requires: "governance_pr",
    example_fix: "Open a governance PR with schema migration plan",
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
   * Returns violations that would cause SHADOW_OWNERSHIP_OVERLAP
   */
  validateChangedFiles(changedFiles: string[]): {
    violations: Array<{ file: string; reason: string; change_requires: string; example_fix: string }>;
    clean: boolean;
  } {
    const violations: Array<{ file: string; reason: string; change_requires: string; example_fix: string }> = [];

    for (const file of changedFiles) {
      const check = this.isProtected(file);
      if (check.protected && check.file) {
        violations.push({
          file,
          reason: check.file.reason,
          change_requires: check.file.change_requires,
          example_fix: check.file.example_fix,
        });
      }
    }

    return {
      violations,
      clean: violations.length === 0,
    };
  }
}
