/**
 * Policy Test Suite Framework
 * Test suite required before policy deployment and promotion
 */

import { v4 as uuidv4 } from "uuid";

export interface PolicyTestCase {
  test_id: string;
  policy_name: string;
  policy_version: number;
  description: string;
  input: Record<string, any>;
  expected_outcome: "promote" | "freeze" | "block" | "warn" | "escalate";
  created_at: string;
  created_by: string;
}

export interface PolicyTestResult {
  test_id: string;
  policy_name: string;
  policy_version: number;
  actual_outcome: "promote" | "freeze" | "block" | "warn" | "escalate";
  expected_outcome: "promote" | "freeze" | "block" | "warn" | "escalate";
  passed: boolean;
  execution_time_ms: number;
  executed_at: string;
  error?: string;
}

export interface PolicyTestSuiteRun {
  suite_id: string;
  policy_name: string;
  policy_version: number;
  total_tests: number;
  passed_tests: number;
  failed_tests: number;
  pass_rate: number;
  results: PolicyTestResult[];
  started_at: string;
  completed_at: string;
  blocked_by_failures: boolean;
}

export class PolicyTestSuite {
  private testCases: Map<string, PolicyTestCase[]> = new Map(); // policy_name -> test cases
  private testResults: PolicyTestSuiteRun[] = [];

  registerTestCase(testCase: PolicyTestCase): void {
    const key = testCase.policy_name;
    const cases = this.testCases.get(key) || [];
    cases.push(testCase);
    this.testCases.set(key, cases);
  }

  registerMultipleTestCases(testCases: PolicyTestCase[]): void {
    for (const testCase of testCases) {
      this.registerTestCase(testCase);
    }
  }

  getTestCases(policyName: string, version?: number): PolicyTestCase[] {
    const cases = this.testCases.get(policyName) || [];
    if (version === undefined) {
      return cases;
    }
    return cases.filter((c) => c.policy_version === version);
  }

  runTests(
    policyName: string,
    version: number,
    executor: (testCase: PolicyTestCase) => Promise<string>
  ): PolicyTestSuiteRun {
    const testCases = this.getTestCases(policyName, version);

    if (testCases.length === 0) {
      return {
        suite_id: uuidv4(),
        policy_name: policyName,
        policy_version: version,
        total_tests: 0,
        passed_tests: 0,
        failed_tests: 0,
        pass_rate: 0,
        results: [],
        started_at: new Date().toISOString(),
        completed_at: new Date().toISOString(),
        blocked_by_failures: true,
      };
    }

    const results: PolicyTestResult[] = [];
    const startTime = Date.now();

    for (const testCase of testCases) {
      const testStartTime = Date.now();
      let actualOutcome: string = "unknown";
      let error: string | undefined;

      try {
        actualOutcome = executor(testCase).then((outcome) => {
          return outcome as any;
        });
      } catch (e: any) {
        error = e.message || String(e);
        actualOutcome = "error";
      }

      const executionTime = Date.now() - testStartTime;
      const passed =
        actualOutcome === testCase.expected_outcome && !error;

      results.push({
        test_id: testCase.test_id,
        policy_name: testCase.policy_name,
        policy_version: testCase.policy_version,
        actual_outcome: actualOutcome as any,
        expected_outcome: testCase.expected_outcome,
        passed,
        execution_time_ms: executionTime,
        executed_at: new Date().toISOString(),
        error,
      });
    }

    const passedCount = results.filter((r) => r.passed).length;
    const failedCount = results.length - passedCount;
    const passRate = results.length > 0 ? (passedCount / results.length) * 100 : 0;

    const suiteRun: PolicyTestSuiteRun = {
      suite_id: uuidv4(),
      policy_name: policyName,
      policy_version: version,
      total_tests: results.length,
      passed_tests: passedCount,
      failed_tests: failedCount,
      pass_rate: passRate,
      results,
      started_at: new Date(startTime).toISOString(),
      completed_at: new Date().toISOString(),
      blocked_by_failures: failedCount > 0,
    };

    this.testResults.push(suiteRun);
    return suiteRun;
  }

  getTestHistory(policyName: string): PolicyTestSuiteRun[] {
    return this.testResults.filter((r) => r.policy_name === policyName);
  }

  getLatestTestRun(policyName: string, version: number): PolicyTestSuiteRun | undefined {
    const relevant = this.testResults.filter(
      (r) => r.policy_name === policyName && r.policy_version === version
    );
    return relevant[relevant.length - 1];
  }
}

export function createTestCase(
  policyName: string,
  version: number,
  description: string,
  input: Record<string, any>,
  expectedOutcome: "promote" | "freeze" | "block" | "warn" | "escalate",
  createdBy: string
): PolicyTestCase {
  return {
    test_id: uuidv4(),
    policy_name: policyName,
    policy_version: version,
    description,
    input,
    expected_outcome: expectedOutcome,
    created_at: new Date().toISOString(),
    created_by: createdBy,
  };
}
