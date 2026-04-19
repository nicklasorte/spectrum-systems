/**
 * Unit tests for Protected File Registry
 */

import { ProtectedFileRegistry } from "../../../src/tlc/protected-file-registry";

describe("ProtectedFileRegistry", () => {
  let registry: ProtectedFileRegistry;

  beforeEach(() => {
    registry = new ProtectedFileRegistry();
  });

  describe("isProtected — exact matches", () => {
    test("CLAUDE.md is protected", () => {
      expect(registry.isProtected("CLAUDE.md").protected).toBe(true);
    });

    test("AGENTS.md is protected", () => {
      expect(registry.isProtected("AGENTS.md").protected).toBe(true);
    });

    test("registry guard script is protected", () => {
      expect(registry.isProtected("scripts/run_system_registry_guard.py").protected).toBe(true);
    });
  });

  describe("isProtected — directory prefix matches", () => {
    test("any workflow file is protected", () => {
      expect(registry.isProtected(".github/workflows/ci.yml").protected).toBe(true);
      expect(registry.isProtected(".github/workflows/protected-file-check.yml").protected).toBe(true);
    });

    test("any schema file is protected", () => {
      expect(registry.isProtected("contracts/schemas/my-schema.json").protected).toBe(true);
    });
  });

  describe("isProtected — safe files (bootstrap safety)", () => {
    test("feature source files are not protected", () => {
      expect(registry.isProtected("src/governance/sli-types.ts").protected).toBe(false);
      expect(registry.isProtected("src/tlc/protected-file-registry.ts").protected).toBe(false);
      expect(registry.isProtected("tests/unit/tlc/protected-file-registry.test.ts").protected).toBe(false);
    });

    test("check_protected_files.py script is NOT protected (can ship in feature PR)", () => {
      expect(registry.isProtected("scripts/check_protected_files.py").protected).toBe(false);
    });

    test("install_hooks.sh script is NOT protected", () => {
      expect(registry.isProtected("scripts/install_hooks.sh").protected).toBe(false);
    });

    test("regular docs files are not protected", () => {
      expect(registry.isProtected("docs/roadmap/phase-5-completion-summary.md").protected).toBe(false);
    });
  });

  describe("validateChangedFiles", () => {
    test("clean changeset with TLC and scripts passes", () => {
      const result = registry.validateChangedFiles([
        "src/tlc/protected-file-registry.ts",
        "scripts/check_protected_files.py",
        "scripts/install_hooks.sh",
        "tests/unit/tlc/protected-file-registry.test.ts",
      ]);
      expect(result.clean).toBe(true);
      expect(result.violations).toHaveLength(0);
    });

    test("CLAUDE.md in changeset fails", () => {
      const result = registry.validateChangedFiles(["src/governance/sli-types.ts", "CLAUDE.md"]);
      expect(result.clean).toBe(false);
      expect(result.violations).toHaveLength(1);
      expect(result.violations[0].file).toBe("CLAUDE.md");
    });

    test("workflow file in changeset fails", () => {
      const result = registry.validateChangedFiles([
        "src/tlc/protected-file-registry.ts",
        ".github/workflows/protected-file-check.yml",
      ]);
      expect(result.clean).toBe(false);
      expect(result.violations[0].change_requires).toBe("governance_pr");
    });

    test("violation includes actionable example_fix", () => {
      const result = registry.validateChangedFiles(["CLAUDE.md"]);
      expect(result.violations[0].example_fix).toContain("git checkout main");
    });

    test("multiple violations all included with fixes", () => {
      const result = registry.validateChangedFiles([
        "CLAUDE.md",
        "AGENTS.md",
        ".github/workflows/test.yml",
      ]);
      expect(result.violations.length).toBe(3);
      expect(result.violations.every((v) => v.example_fix)).toBe(true);
    });

    test("empty changeset passes", () => {
      const result = registry.validateChangedFiles([]);
      expect(result.clean).toBe(true);
      expect(result.violations.length).toBe(0);
    });

    test("large changeset with mixed protected/unprotected", () => {
      const result = registry.validateChangedFiles([
        "src/feature1.ts",
        "src/feature2.ts",
        "tests/test1.ts",
        "CLAUDE.md",
        "docs/guide.md",
        ".github/workflows/ci.yml",
        "src/feature3.ts",
        "scripts/check_protected_files.py",
      ]);
      expect(result.clean).toBe(false);
      expect(result.violations.length).toBe(2); // CLAUDE.md and .github/workflows/ci.yml
      expect(result.violations.every((v) => v.example_fix)).toBe(true);
    });
  });

  describe("file ownership metadata", () => {
    test("should have system-authority as owner for CLAUDE.md", () => {
      const result = registry.isProtected("CLAUDE.md");
      expect(result.file?.owner).toBe("system-authority");
    });

    test("should have system-authority as owner for registry guard", () => {
      const result = registry.isProtected("scripts/run_system_registry_guard.py");
      expect(result.file?.owner).toBe("system-authority");
    });

    test("should have schema-registry as owner for schemas", () => {
      const result = registry.isProtected("contracts/schemas/test.json");
      expect(result.file?.owner).toBe("schema-registry");
    });
  });

  describe("change requirements", () => {
    test("all protected files should require governance_pr", () => {
      const files = [
        "CLAUDE.md",
        "AGENTS.md",
        "scripts/run_system_registry_guard.py",
        "contracts/schemas/test.json",
        ".github/workflows/test.yml",
      ];

      for (const file of files) {
        const result = registry.isProtected(file);
        expect(result.file?.change_requires).toBe("governance_pr");
      }
    });
  });
});
