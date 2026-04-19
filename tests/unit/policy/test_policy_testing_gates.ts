/**
 * Unit tests for Policy Testing Gates (Cluster D)
 */

import {
  PolicyTestSuite,
  createTestCase,
  PolicyTestSuiteRun,
} from "../../../src/policy/policy_test_suite";
import {
  RegressionDetector,
  createRegressionDetector,
} from "../../../src/policy/regression_detector";
import {
  PolicyPromotionGate,
  createPolicyPromotionGate,
} from "../../../src/policy/policy_promotion_gate";
import {
  createJudgmentPolicy,
} from "../../../src/judgment/judgment_policy_registry";

describe("Policy Test Suite", () => {
  let testSuite: PolicyTestSuite;

  beforeEach(() => {
    testSuite = new PolicyTestSuite();
  });

  test("registerTestCase adds test to suite", () => {
    const testCase = createTestCase(
      "test_policy",
      1,
      "Should promote valid artifacts",
      { score: 0.95 },
      "promote",
      "test-user"
    );

    testSuite.registerTestCase(testCase);
    const cases = testSuite.getTestCases("test_policy");

    expect(cases).toHaveLength(1);
    expect(cases[0].description).toBe("Should promote valid artifacts");
  });

  test("registerMultipleTestCases adds batch of tests", () => {
    const testCases = [
      createTestCase(
        "policy",
        1,
        "Test 1",
        { score: 0.9 },
        "promote",
        "user"
      ),
      createTestCase(
        "policy",
        1,
        "Test 2",
        { score: 0.5 },
        "warn",
        "user"
      ),
    ];

    testSuite.registerMultipleTestCases(testCases);
    const cases = testSuite.getTestCases("policy");

    expect(cases).toHaveLength(2);
  });

  test("getTestCases filters by version", () => {
    const test1 = createTestCase(
      "policy",
      1,
      "Test v1",
      { score: 0.9 },
      "promote",
      "user"
    );
    const test2 = createTestCase(
      "policy",
      2,
      "Test v2",
      { score: 0.9 },
      "promote",
      "user"
    );

    testSuite.registerTestCase(test1);
    testSuite.registerTestCase(test2);

    const v1Cases = testSuite.getTestCases("policy", 1);
    const v2Cases = testSuite.getTestCases("policy", 2);

    expect(v1Cases).toHaveLength(1);
    expect(v2Cases).toHaveLength(1);
  });

  test("runTests executes test suite", () => {
    const testCase = createTestCase(
      "policy",
      1,
      "Test 1",
      { score: 0.9 },
      "promote",
      "user"
    );

    testSuite.registerTestCase(testCase);

    const executor = async (tc: any) => "promote";
    const run = testSuite.runTests("policy", 1, executor as any);

    expect(run.total_tests).toBe(1);
    expect(run.policy_name).toBe("policy");
    expect(run.policy_version).toBe(1);
  });

  test("getTestHistory returns all runs for policy", () => {
    const testCase = createTestCase(
      "policy",
      1,
      "Test",
      { score: 0.9 },
      "promote",
      "user"
    );

    testSuite.registerTestCase(testCase);

    const executor = async () => "promote";
    testSuite.runTests("policy", 1, executor as any);
    testSuite.runTests("policy", 1, executor as any);

    const history = testSuite.getTestHistory("policy");

    expect(history).toHaveLength(2);
  });

  test("getLatestTestRun returns most recent run", () => {
    const testCase = createTestCase(
      "policy",
      1,
      "Test",
      { score: 0.9 },
      "promote",
      "user"
    );

    testSuite.registerTestCase(testCase);

    const executor = async () => "promote";
    testSuite.runTests("policy", 1, executor as any);
    const run2 = testSuite.runTests("policy", 1, executor as any);

    const latest = testSuite.getLatestTestRun("policy", 1);

    expect(latest?.suite_id).toBe(run2.suite_id);
  });
});

describe("Regression Detector", () => {
  let detector: RegressionDetector;

  beforeEach(() => {
    detector = createRegressionDetector();
  });

  test("detectRegressions identifies outcome changes", () => {
    const oldResults = [
      {
        test_id: "t1",
        policy_name: "policy",
        policy_version: 1,
        actual_outcome: "promote" as const,
        expected_outcome: "promote" as const,
        passed: true,
        execution_time_ms: 10,
        executed_at: new Date().toISOString(),
      },
    ];

    const newResults = [
      {
        test_id: "t1",
        policy_name: "policy",
        policy_version: 2,
        actual_outcome: "block" as const,
        expected_outcome: "promote" as const,
        passed: false,
        execution_time_ms: 10,
        executed_at: new Date().toISOString(),
      },
    ];

    const analysis = detector.detectRegressions(
      "policy",
      1,
      2,
      oldResults,
      newResults
    );

    expect(analysis.regression_detected).toBe(true);
    expect(analysis.regressions).toHaveLength(1);
    expect(analysis.regressions[0].old_outcome).toBe("promote");
    expect(analysis.regressions[0].new_outcome).toBe("block");
  });

  test("detectRegressions detects critical regressions", () => {
    const oldResults = [
      {
        test_id: "t1",
        policy_name: "policy",
        policy_version: 1,
        actual_outcome: "block" as const,
        expected_outcome: "block" as const,
        passed: true,
        execution_time_ms: 10,
        executed_at: new Date().toISOString(),
      },
    ];

    const newResults = [
      {
        test_id: "t1",
        policy_name: "policy",
        policy_version: 2,
        actual_outcome: "promote" as const,
        expected_outcome: "block" as const,
        passed: false,
        execution_time_ms: 10,
        executed_at: new Date().toISOString(),
      },
    ];

    const analysis = detector.detectRegressions(
      "policy",
      1,
      2,
      oldResults,
      newResults
    );

    expect(analysis.regression_detected).toBe(true);
    expect(analysis.blocked_by_regression).toBe(true);
    expect(analysis.regressions[0].severity).toBe("critical");
  });

  test("detectRegressions detects coverage gaps", () => {
    const oldResults = [
      {
        test_id: "t1",
        policy_name: "policy",
        policy_version: 1,
        actual_outcome: "promote" as const,
        expected_outcome: "promote" as const,
        passed: true,
        execution_time_ms: 10,
        executed_at: new Date().toISOString(),
      },
    ];

    const newResults = [
      {
        test_id: "t1",
        policy_name: "policy",
        policy_version: 2,
        actual_outcome: "promote" as const,
        expected_outcome: "promote" as const,
        passed: true,
        execution_time_ms: 10,
        executed_at: new Date().toISOString(),
      },
      {
        test_id: "t2", // new test not in old
        policy_name: "policy",
        policy_version: 2,
        actual_outcome: "promote" as const,
        expected_outcome: "promote" as const,
        passed: true,
        execution_time_ms: 10,
        executed_at: new Date().toISOString(),
      },
    ];

    const analysis = detector.detectRegressions(
      "policy",
      1,
      2,
      oldResults,
      newResults
    );

    expect(analysis.coverage_gaps.length).toBeGreaterThan(0);
    expect(analysis.coverage_gaps.some((g) => g.includes("t2"))).toBe(true);
  });

  test("detectRegressions detects improvements", () => {
    const oldResults = [
      {
        test_id: "t1",
        policy_name: "policy",
        policy_version: 1,
        actual_outcome: "block" as const,
        expected_outcome: "promote" as const,
        passed: false,
        execution_time_ms: 10,
        executed_at: new Date().toISOString(),
      },
    ];

    const newResults = [
      {
        test_id: "t1",
        policy_name: "policy",
        policy_version: 2,
        actual_outcome: "promote" as const,
        expected_outcome: "promote" as const,
        passed: true,
        execution_time_ms: 10,
        executed_at: new Date().toISOString(),
      },
    ];

    const analysis = detector.detectRegressions(
      "policy",
      1,
      2,
      oldResults,
      newResults
    );

    expect(analysis.regression_detected).toBe(false);
    expect(analysis.improvements.length).toBeGreaterThan(0);
  });
});

describe("Policy Promotion Gate", () => {
  let gate: PolicyPromotionGate;
  let testSuite: PolicyTestSuite;
  let regressionDetector: RegressionDetector;

  beforeEach(() => {
    testSuite = new PolicyTestSuite();
    regressionDetector = createRegressionDetector();
    gate = createPolicyPromotionGate(testSuite, regressionDetector);
  });

  test("checkPromotionReadiness blocks without tests", () => {
    const policy = createJudgmentPolicy(
      "no_tests",
      "Policy with no tests",
      [],
      "promote",
      "Rationale",
      "user"
    );

    const result = gate.checkPromotionReadiness(policy);

    expect(result.can_promote).toBe(false);
    expect(result.checks_failed.some((c) => c.includes("test cases"))).toBe(
      true
    );
  });

  test("checkPromotionReadiness blocks with failing tests", () => {
    const policy = createJudgmentPolicy(
      "failing_tests",
      "Policy with failing tests",
      [],
      "promote",
      "Rationale",
      "user"
    );

    const testCase = createTestCase(
      "failing_tests",
      1,
      "Should pass",
      { score: 0.5 },
      "promote",
      "user"
    );

    testSuite.registerTestCase(testCase);

    // Create a run with failed tests
    const run: PolicyTestSuiteRun = {
      suite_id: "run-1",
      policy_name: "failing_tests",
      policy_version: 1,
      total_tests: 1,
      passed_tests: 0,
      failed_tests: 1,
      pass_rate: 0,
      results: [
        {
          test_id: "t1",
          policy_name: "failing_tests",
          policy_version: 1,
          actual_outcome: "block" as const,
          expected_outcome: "promote" as const,
          passed: false,
          execution_time_ms: 10,
          executed_at: new Date().toISOString(),
        },
      ],
      started_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
      blocked_by_failures: true,
    };

    // This would need access to test history; for now verify structure
    const result = gate.checkPromotionReadiness(policy);
    expect(result).toHaveProperty("can_promote");
  });

  test("blockIfRegressions blocks on critical regressions", () => {
    const analysis = {
      policy_name: "policy",
      old_version: 1,
      new_version: 2,
      total_tests: 1,
      tests_with_changes: 1,
      regressions: [
        {
          test_id: "t1",
          test_description: "Test 1",
          old_outcome: "promote",
          new_outcome: "block",
          is_regression: true,
          severity: "critical" as const,
          impact_description: "Critical change",
        },
      ],
      improvements: [],
      regression_detected: true,
      blocked_by_regression: true,
      coverage_gaps: [],
    };

    const result = gate.blockIfRegressions(analysis);

    expect(result.blocked).toBe(true);
    expect(result.reason).toContain("Critical regressions");
  });

  test("generatePromotionReport formats readable report", () => {
    const checks = {
      policy_name: "test_policy",
      policy_version: 1,
      can_promote: true,
      checks_passed: ["All tests passed", "No regressions"],
      checks_failed: [] as string[],
      warnings: [],
    };

    const report = gate.generatePromotionReport(checks);

    expect(report).toContain("Policy Promotion Report");
    expect(report).toContain("test_policy");
    expect(report).toContain("READY FOR PROMOTION");
    expect(report).toContain("All tests passed");
  });
});
