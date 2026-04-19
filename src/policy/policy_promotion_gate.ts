/**
 * Policy Promotion Gate
 * Blocks policy promotion without passing tests and no regressions
 */

import {
  PolicyTestSuiteRun,
  PolicyTestSuite,
} from "./policy_test_suite";
import { RegressionAnalysis, RegressionDetector } from "./regression_detector";
import { JudgmentPolicy } from "../judgment/judgment_policy_registry";

export interface PolicyPromotionCheckResult {
  policy_name: string;
  policy_version: number;
  can_promote: boolean;
  checks_passed: string[];
  checks_failed: string[];
  warnings: string[];
  test_suite_run?: PolicyTestSuiteRun;
  regression_analysis?: RegressionAnalysis;
}

export class PolicyPromotionGate {
  constructor(
    private testSuite: PolicyTestSuite,
    private regressionDetector: RegressionDetector
  ) {}

  checkPromotionReadiness(
    policy: JudgmentPolicy
  ): PolicyPromotionCheckResult {
    const checks: PolicyPromotionCheckResult = {
      policy_name: policy.policy_name,
      policy_version: policy.policy_version,
      can_promote: true,
      checks_passed: [],
      checks_failed: [],
      warnings: [],
    };

    // Check 1: Has test cases
    const testCases = this.testSuite.getTestCases(
      policy.policy_name,
      policy.policy_version
    );
    if (testCases.length === 0) {
      checks.checks_failed.push(
        "No test cases defined for this policy version"
      );
      checks.can_promote = false;
    } else {
      checks.checks_passed.push(
        `${testCases.length} test cases defined`
      );
    }

    // Check 2: Get latest test run
    const latestRun = this.testSuite.getLatestTestRun(
      policy.policy_name,
      policy.policy_version
    );

    if (!latestRun) {
      checks.checks_failed.push("No test suite run found for this version");
      checks.can_promote = false;
    } else {
      checks.test_suite_run = latestRun;

      // Check 2a: Tests must pass
      if (latestRun.pass_rate < 100) {
        checks.checks_failed.push(
          `Test pass rate is ${latestRun.pass_rate.toFixed(1)}% (required: 100%)`
        );
        checks.can_promote = false;
      } else {
        checks.checks_passed.push(`All tests passed (100%)`);
      }

      // Check 2b: No test execution errors
      const errorCount = latestRun.results.filter((r) => r.error).length;
      if (errorCount > 0) {
        checks.checks_failed.push(
          `${errorCount} test execution error(s) found`
        );
        checks.can_promote = false;
      } else {
        checks.checks_passed.push(`No test execution errors`);
      }
    }

    // Check 3: Check for regressions (if previous version exists)
    if (policy.policy_version > 1) {
      // This would require tracking of previous version results
      checks.warnings.push(
        `Regression analysis requires previous version test results`
      );
    } else {
      checks.checks_passed.push(`First version - no regression check needed`);
    }

    // Check 4: Policy metadata
    if (!policy.outcome_rationale || policy.outcome_rationale.trim() === "") {
      checks.warnings.push(`No outcome rationale provided`);
    } else {
      checks.checks_passed.push(`Outcome rationale documented`);
    }

    if (policy.test_cases_count === 0 && policy.test_pass_rate === 0) {
      checks.warnings.push(
        `Test statistics not recorded (may indicate incomplete setup)`
      );
    }

    // Final decision
    if (checks.checks_failed.length > 0) {
      checks.can_promote = false;
    }

    return checks;
  }

  blockIfRegressions(
    regressionAnalysis: RegressionAnalysis
  ): { blocked: boolean; reason?: string } {
    if (!regressionAnalysis.regression_detected) {
      return { blocked: false };
    }

    if (regressionAnalysis.blocked_by_regression) {
      return {
        blocked: true,
        reason: `Critical regressions detected: ${regressionAnalysis.regressions.length} outcome change(s)`,
      };
    }

    // Non-critical regressions = warning but don't block
    return { blocked: false };
  }

  generatePromotionReport(
    checks: PolicyPromotionCheckResult
  ): string {
    const lines = [
      `Policy Promotion Report`,
      `======================`,
      `Policy: ${checks.policy_name} v${checks.policy_version}`,
      `Status: ${checks.can_promote ? "✓ READY FOR PROMOTION" : "✗ BLOCKED FROM PROMOTION"}`,
      ``,
      `Checks Passed (${checks.checks_passed.length}):`,
      ...checks.checks_passed.map((c) => `  ✓ ${c}`),
      ``,
      `Checks Failed (${checks.checks_failed.length}):`,
    ];

    if (checks.checks_failed.length > 0) {
      lines.push(...checks.checks_failed.map((c) => `  ✗ ${c}`));
    } else {
      lines.push(`  (none)`);
    }

    lines.push(``, `Warnings (${checks.warnings.length}):`);

    if (checks.warnings.length > 0) {
      lines.push(...checks.warnings.map((w) => `  ⚠ ${w}`));
    } else {
      lines.push(`  (none)`);
    }

    if (checks.test_suite_run) {
      lines.push(
        ``,
        `Test Suite Results:`,
        `  Total: ${checks.test_suite_run.total_tests}`,
        `  Passed: ${checks.test_suite_run.passed_tests}`,
        `  Failed: ${checks.test_suite_run.failed_tests}`,
        `  Pass Rate: ${checks.test_suite_run.pass_rate.toFixed(1)}%`
      );
    }

    return lines.join("\n");
  }
}

export function createPolicyPromotionGate(
  testSuite: PolicyTestSuite,
  regressionDetector: RegressionDetector
): PolicyPromotionGate {
  return new PolicyPromotionGate(testSuite, regressionDetector);
}
