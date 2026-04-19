/**
 * Regression Detector
 * Detects policy behavior changes between versions (regressions)
 */

import { PolicyTestCase, PolicyTestResult } from "./policy_test_suite";

export interface OutcomeChange {
  test_id: string;
  test_description: string;
  old_outcome: string;
  new_outcome: string;
  is_regression: boolean;
  severity: "critical" | "high" | "medium" | "low";
  impact_description: string;
}

export interface RegressionAnalysis {
  policy_name: string;
  old_version: number;
  new_version: number;
  total_tests: number;
  tests_with_changes: number;
  regressions: OutcomeChange[];
  improvements: OutcomeChange[];
  regression_detected: boolean;
  blocked_by_regression: boolean;
  coverage_gaps: string[];
}

export class RegressionDetector {
  detectRegressions(
    policyName: string,
    oldVersion: number,
    newVersion: number,
    oldResults: PolicyTestResult[],
    newResults: PolicyTestResult[]
  ): RegressionAnalysis {
    const regressions: OutcomeChange[] = [];
    const improvements: OutcomeChange[] = [];
    const coverageGaps: string[] = [];

    // Map old results by test_id for easy lookup
    const oldMap = new Map(oldResults.map((r) => [r.test_id, r]));
    const newMap = new Map(newResults.map((r) => [r.test_id, r]));

    // Find tests in new but not in old = coverage gap
    for (const testId of newMap.keys()) {
      if (!oldMap.has(testId)) {
        coverageGaps.push(`New test added: ${testId}`);
      }
    }

    // Find outcome changes
    for (const [testId, oldResult] of oldMap) {
      const newResult = newMap.get(testId);
      if (!newResult) {
        coverageGaps.push(`Test removed: ${testId}`);
        continue;
      }

      if (oldResult.actual_outcome !== newResult.actual_outcome) {
        const change: OutcomeChange = {
          test_id: testId,
          test_description: `${policyName} test case`,
          old_outcome: oldResult.actual_outcome,
          new_outcome: newResult.actual_outcome,
          is_regression: this.isRegression(
            oldResult.actual_outcome,
            newResult.actual_outcome
          ),
          severity: this.getSeverity(
            oldResult.actual_outcome,
            newResult.actual_outcome
          ),
          impact_description: this.getImpactDescription(
            oldResult.actual_outcome,
            newResult.actual_outcome
          ),
        };

        if (change.is_regression) {
          regressions.push(change);
        } else {
          improvements.push(change);
        }
      }
    }

    const totalTests = oldMap.size;
    const testsWithChanges = regressions.length + improvements.length;

    return {
      policy_name: policyName,
      old_version: oldVersion,
      new_version: newVersion,
      total_tests: totalTests,
      tests_with_changes: testsWithChanges,
      regressions,
      improvements,
      regression_detected: regressions.length > 0,
      blocked_by_regression: regressions.some((r) => r.severity === "critical"),
      coverage_gaps: coverageGaps,
    };
  }

  private isRegression(oldOutcome: string, newOutcome: string): boolean {
    // Define what constitutes a regression
    const tighterOutcomes = {
      promote: 0,
      warn: 1,
      freeze: 2,
      block: 3,
    };

    const oldSeverity = (tighterOutcomes as any)[oldOutcome] ?? -1;
    const newSeverity = (tighterOutcomes as any)[newOutcome] ?? -1;

    // Policy got more restrictive = potential regression
    if (newSeverity > oldSeverity) {
      return true;
    }

    // Same severity but different = suspicious
    if (oldSeverity === newSeverity && oldOutcome !== newOutcome) {
      return true;
    }

    return false;
  }

  private getSeverity(
    oldOutcome: string,
    newOutcome: string
  ): "critical" | "high" | "medium" | "low" {
    // Block → promote = critical regression (allowing what was blocked)
    if (oldOutcome === "block" && newOutcome === "promote") {
      return "critical";
    }

    // Promote → block = critical regression (blocking what was allowed)
    if (oldOutcome === "promote" && newOutcome === "block") {
      return "critical";
    }

    // Any change in promotion decisions = high
    if (
      (oldOutcome === "promote" || oldOutcome === "block") &&
      (newOutcome === "promote" || newOutcome === "block")
    ) {
      return "high";
    }

    // Warn/freeze changes = medium
    if (
      (oldOutcome === "warn" || oldOutcome === "freeze") &&
      (newOutcome === "warn" || newOutcome === "freeze")
    ) {
      return "medium";
    }

    return "low";
  }

  private getImpactDescription(oldOutcome: string, newOutcome: string): string {
    const parts = [
      `Policy behavior changed from '${oldOutcome}' to '${newOutcome}'`,
    ];

    if (this.isRegression(oldOutcome, newOutcome)) {
      parts.push(
        `This change is more restrictive than the previous policy version`
      );
    } else if (newOutcome === "promote" && oldOutcome !== "promote") {
      parts.push(`This change is more permissive than the previous version`);
    }

    return parts.join(". ");
  }
}

export function createRegressionDetector(): RegressionDetector {
  return new RegressionDetector();
}
