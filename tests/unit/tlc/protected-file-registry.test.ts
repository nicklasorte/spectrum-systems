/**
 * Unit tests for Protected File Registry
 */

import { ProtectedFileRegistry } from "../../../src/tlc/protected-file-registry";

describe("Protected File Registry", () => {
  let registry: ProtectedFileRegistry;

  beforeEach(() => {
    registry = new ProtectedFileRegistry();
  });

  describe("isProtected", () => {
    test("should detect CLAUDE.md as protected", () => {
      const result = registry.isProtected("CLAUDE.md");
      expect(result.protected).toBe(true);
      expect(result.file?.change_requires).toBe("governance_pr");
    });

    test("should detect AGENTS.md as protected", () => {
      const result = registry.isProtected("AGENTS.md");
      expect(result.protected).toBe(true);
      expect(result.file?.reason).toContain("Agent standards");
    });

    test("should detect registry guard as protected", () => {
      const result = registry.isProtected("scripts/run_system_registry_guard.py");
      expect(result.protected).toBe(true);
      expect(result.file?.reason).toContain("authority enforcement");
    });

    test("should detect schema directory entries as protected", () => {
      const result = registry.isProtected("contracts/schemas/my-new-schema.json");
      expect(result.protected).toBe(true);
      expect(result.file?.reason).toContain("artifact schemas");
    });

    test("should detect workflows directory entries as protected", () => {
      const result = registry.isProtected(".github/workflows/test.yml");
      expect(result.protected).toBe(true);
      expect(result.file?.reason).toContain("CI/CD");
    });

    test("should allow normal feature files", () => {
      const result = registry.isProtected("src/governance/sli-types.ts");
      expect(result.protected).toBe(false);
    });

    test("should allow test files", () => {
      const result = registry.isProtected("tests/governance/sli-backend.test.ts");
      expect(result.protected).toBe(false);
    });

    test("should allow README.md in subdirectories", () => {
      const result = registry.isProtected("docs/governance/README.md");
      expect(result.protected).toBe(false);
    });
  });

  describe("validateChangedFiles", () => {
    test("should validate clean changeset", () => {
      const result = registry.validateChangedFiles([
        "src/governance/sli-types.ts",
        "tests/governance/sli-backend.test.ts",
      ]);
      expect(result.clean).toBe(true);
      expect(result.violations.length).toBe(0);
    });

    test("should catch SHADOW_OWNERSHIP_OVERLAP in changeset", () => {
      const result = registry.validateChangedFiles([
        "src/governance/sli-types.ts",
        "CLAUDE.md",
        "AGENTS.md",
      ]);
      expect(result.clean).toBe(false);
      expect(result.violations.length).toBe(2);
    });

    test("should catch single protected file violation", () => {
      const result = registry.validateChangedFiles([
        "src/governance/new-feature.ts",
        "CLAUDE.md",
      ]);
      expect(result.clean).toBe(false);
      expect(result.violations.length).toBe(1);
      expect(result.violations[0].file).toBe("CLAUDE.md");
    });

    test("should report correct reason for violation", () => {
      const result = registry.validateChangedFiles(["CLAUDE.md"]);
      expect(result.violations[0].reason).toContain("authority");
      expect(result.violations[0].change_requires).toBe("governance_pr");
    });

    test("should catch workflow changes", () => {
      const result = registry.validateChangedFiles([
        ".github/workflows/test.yml",
        ".github/workflows/build.yml",
      ]);
      expect(result.clean).toBe(false);
      expect(result.violations.length).toBe(2);
    });

    test("should catch schema changes", () => {
      const result = registry.validateChangedFiles([
        "contracts/schemas/v1/artifact.json",
        "contracts/schemas/v2/new-artifact.json",
      ]);
      expect(result.clean).toBe(false);
      expect(result.violations.length).toBe(2);
    });

    test("should handle empty changeset", () => {
      const result = registry.validateChangedFiles([]);
      expect(result.clean).toBe(true);
      expect(result.violations.length).toBe(0);
    });

    test("should handle large changesets with mixed protected/unprotected", () => {
      const result = registry.validateChangedFiles([
        "src/feature1.ts",
        "src/feature2.ts",
        "tests/test1.ts",
        "CLAUDE.md",
        "docs/guide.md",
        ".github/workflows/ci.yml",
        "src/feature3.ts",
      ]);
      expect(result.clean).toBe(false);
      expect(result.violations.length).toBe(2); // CLAUDE.md and .github/workflows/ci.yml
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
