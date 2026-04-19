import * as path from "path";

/**
 * Protected File Registry
 * Files that cannot be modified via feature PRs without governance authorization
 * Enforced by pre-commit hook and CI system registry guard
 */

export interface ProtectedFile {
  path: string;
  reason: string;
  owner: string;
  change_requires: "governance_pr" | "admin_override" | "board_approval";
  last_authorized_at?: string;
}

export const PROTECTED_FILES: ProtectedFile[] = [
  // Authority documents
  {
    path: "CLAUDE.md",
    reason: "Agent authority document — defines agent behavior, injected memory, system standards",
    owner: "system-authority",
    change_requires: "governance_pr",
  },
  {
    path: "AGENTS.md",
    reason: "Agent standards document — injected agent memory/standards per Canonical Harness spec",
    owner: "system-authority",
    change_requires: "governance_pr",
  },
  // Registry guard itself
  {
    path: "scripts/run_system_registry_guard.py",
    reason: "Registry guard is authority enforcement — cannot be self-modified via feature PRs",
    owner: "system-authority",
    change_requires: "governance_pr",
  },
  // Core governance schemas
  {
    path: "contracts/schemas/",
    reason: "Core artifact schemas — changes break backward compatibility",
    owner: "schema-registry",
    change_requires: "governance_pr",
  },
  // CI/CD workflows
  {
    path: ".github/workflows/",
    reason: "CI/CD pipelines — changes affect all builds and enforcement",
    owner: "system-authority",
    change_requires: "governance_pr",
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
    violations: Array<{ file: string; reason: string; change_requires: string }>;
    clean: boolean;
  } {
    const violations: Array<{ file: string; reason: string; change_requires: string }> = [];

    for (const file of changedFiles) {
      const check = this.isProtected(file);
      if (check.protected && check.file) {
        violations.push({
          file,
          reason: check.file.reason,
          change_requires: check.file.change_requires,
        });
      }
    }

    return {
      violations,
      clean: violations.length === 0,
    };
  }
}
