import { execSync } from "child_process";
import { ProtectedFileRegistry } from "./protected-file-registry";

/**
 * Protected File Checker
 * Run before committing to catch SHADOW_OWNERSHIP_OVERLAP early
 */

export async function checkProtectedFiles(): Promise<{
  clean: boolean;
  violations: any[];
  message: string;
}> {
  const registry = new ProtectedFileRegistry();

  // Get changed files vs main
  let changedFiles: string[] = [];
  try {
    const output = execSync(
      "git diff --name-only main HEAD 2>/dev/null || git diff --name-only HEAD~1 HEAD 2>/dev/null",
      {
        encoding: "utf-8",
      }
    );
    changedFiles = output
      .trim()
      .split("\n")
      .filter(Boolean);
  } catch {
    // No git or no diff — pass
    return { clean: true, violations: [], message: "No changed files detected" };
  }

  const result = registry.validateChangedFiles(changedFiles);

  if (!result.clean) {
    const messages = result.violations.map(
      (v) =>
        `  ❌ ${v.file}\n     Reason: ${v.reason}\n     Requires: ${v.change_requires}`
    );

    return {
      clean: false,
      violations: result.violations,
      message: [
        "SHADOW_OWNERSHIP_OVERLAP: Protected files modified in feature PR.",
        "",
        "Violations:",
        ...messages,
        "",
        "To fix:",
        "  git checkout main -- CLAUDE.md AGENTS.md",
        "  git add CLAUDE.md AGENTS.md",
        "  git commit -m 'Restore protected authority files'",
        "",
        "To change protected files, open a dedicated governance PR.",
      ].join("\n"),
    };
  }

  return {
    clean: true,
    violations: [],
    message: "All protected file checks passed",
  };
}
