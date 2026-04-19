/**
 * Unit tests for Judgment System (Cluster C)
 */

import {
  createJudgmentRecord,
  addEvidence,
  addPolicySelection,
  addPrecedent,
  addAlternative,
  validateJudgmentRecord,
} from "../../../src/judgment/judgment_record";
import {
  JudgmentPolicyRegistry,
  createJudgmentPolicy,
  deprecatePolicy,
} from "../../../src/judgment/judgment_policy_registry";
import {
  ContradictionDetector,
  createContradictionDetector,
} from "../../../src/judgment/contradiction_detector";
import {
  PrecedentMatcher,
  createPrecedentMatcher,
} from "../../../src/judgment/precedent_matcher";
import { v4 as uuidv4 } from "uuid";

describe("Judgment Record - Creation and Building", () => {
  test("createJudgmentRecord creates valid record", () => {
    const record = createJudgmentRecord(
      uuidv4(),
      "test_artifact",
      "decision-maker-1",
      "system",
      "promote",
      "All checks passed",
      uuidv4()
    );

    expect(record.artifact_kind).toBe("judgment_record");
    expect(record.decision_outcome).toBe("promote");
    expect(record.decision_rationale).toBe("All checks passed");
    expect(record.decider_role).toBe("system");
  });

  test("addEvidence adds evidence to record", () => {
    const record = createJudgmentRecord(
      uuidv4(),
      "test_artifact",
      "system",
      "system",
      "promote",
      "Test",
      uuidv4()
    );

    const updated = addEvidence(
      record,
      uuidv4(),
      "eval_result",
      "high",
      "Test passed with 100% pass rate"
    );

    expect(updated.evidence).toHaveLength(1);
    expect(updated.evidence[0].relevance).toBe("high");
  });

  test("addPolicySelection adds policy to record", () => {
    const record = createJudgmentRecord(
      uuidv4(),
      "test_artifact",
      "system",
      "system",
      "promote",
      "Test",
      uuidv4()
    );

    const updated = addPolicySelection(
      record,
      "must_pass_tests",
      1,
      true,
      "strong",
      ["has_test_results", "pass_rate_meets_threshold"]
    );

    expect(updated.policies_considered).toHaveLength(1);
    expect(updated.policies_considered[0].matched).toBe(true);
  });

  test("addPrecedent adds precedent citation", () => {
    const record = createJudgmentRecord(
      uuidv4(),
      "test_artifact",
      "system",
      "system",
      "promote",
      "Test",
      uuidv4()
    );

    const updated = addPrecedent(
      record,
      uuidv4(),
      uuidv4(),
      0.85,
      true,
      "Similar artifact with same outcome"
    );

    expect(updated.precedents).toHaveLength(1);
    expect(updated.precedents[0].similarity_score).toBe(0.85);
  });

  test("addAlternative tracks evaluated alternatives", () => {
    const record = createJudgmentRecord(
      uuidv4(),
      "test_artifact",
      "system",
      "system",
      "promote",
      "Test",
      uuidv4()
    );

    const updated = addAlternative(
      record,
      "freeze",
      "Freezing would delay processing",
      "Doesn't meet SLA requirements"
    );

    expect(updated.alternatives_evaluated).toHaveLength(1);
    expect(updated.alternatives_evaluated[0].rejected_reason).toContain("SLA");
  });
});

describe("Judgment Record - Validation", () => {
  test("validateJudgmentRecord rejects record with missing fields", () => {
    const record = createJudgmentRecord(
      "",
      "test_artifact",
      "system",
      "system",
      "promote",
      "",
      ""
    );

    const { valid, issues } = validateJudgmentRecord(record);

    expect(valid).toBe(false);
    expect(issues.length).toBeGreaterThan(0);
    expect(issues.some((i) => i.includes("subject_artifact_id"))).toBe(true);
  });

  test("validateJudgmentRecord accepts complete record", () => {
    let record = createJudgmentRecord(
      uuidv4(),
      "test_artifact",
      "system",
      "system",
      "promote",
      "All requirements met",
      uuidv4()
    );

    record = addEvidence(record, uuidv4(), "test", "high", "reason");
    record = addPolicySelection(record, "policy-1", 1, true, "strong", ["condition1"]);

    const { valid, issues } = validateJudgmentRecord(record);

    expect(valid).toBe(true);
    expect(issues).toHaveLength(0);
  });
});

describe("Judgment Policy Registry", () => {
  test("registerPolicy adds policy to registry", () => {
    const registry = new JudgmentPolicyRegistry();
    const policy = createJudgmentPolicy(
      "test_policy",
      "Test policy",
      [],
      "promote",
      "Test rationale",
      "test-user"
    );

    registry.registerPolicy(policy);
    const retrieved = registry.getPolicy("test_policy");

    expect(retrieved).toEqual(policy);
  });

  test("activatePolicy changes active version", () => {
    const registry = new JudgmentPolicyRegistry();
    const policy1 = createJudgmentPolicy(
      "test_policy",
      "Test policy v1",
      [],
      "promote",
      "Rationale",
      "user"
    );

    const policy2 = createJudgmentPolicy(
      "test_policy",
      "Test policy v2",
      [],
      "block",
      "Rationale",
      "user"
    );
    policy2.policy_version = 2;

    registry.registerPolicy(policy1);
    registry.registerPolicy(policy2);

    const active1 = registry.getActivePolicy("test_policy");
    expect(active1?.policy_version).toBe(2); // Latest version is active by default

    registry.activatePolicy("test_policy", 1);
    const active2 = registry.getActivePolicy("test_policy");
    expect(active2?.policy_version).toBe(1);
  });

  test("listActivePolicies returns only active versions", () => {
    const registry = new JudgmentPolicyRegistry();
    const policy1 = createJudgmentPolicy(
      "policy1",
      "Policy 1",
      [],
      "promote",
      "Rationale",
      "user"
    );
    const policy2 = deprecatePolicy(policy1, "Old", policy1.policy_id);

    registry.registerPolicy(policy1);
    registry.registerPolicy(policy2);

    const active = registry.listActivePolicies();
    expect(active).toHaveLength(1);
    expect(active[0].deprecated).toBe(false);
  });
});

describe("Contradiction Detector", () => {
  test("detectContradictions identifies conflicting outcomes", () => {
    const registry = new JudgmentPolicyRegistry();
    const detector = createContradictionDetector(registry);

    const policy1 = createJudgmentPolicy(
      "policy_promote",
      "Always promote",
      [],
      "promote",
      "Test rationale",
      "user"
    );

    const policy2 = createJudgmentPolicy(
      "policy_block",
      "Always block",
      [],
      "block",
      "Test rationale",
      "user"
    );

    registry.registerPolicy(policy1);
    registry.registerPolicy(policy2);

    const context = {
      artifact_id: uuidv4(),
      artifact_kind: "test",
      evaluation_data: {},
    };

    const analysis = detector.detectContradictions(context);

    expect(analysis.has_contradictions).toBe(true);
    expect(analysis.contradictions.length).toBeGreaterThan(0);
  });

  test("detectContradictions detects no conflicts when only one policy matches", () => {
    const registry = new JudgmentPolicyRegistry();
    const detector = createContradictionDetector(registry);

    const policy = createJudgmentPolicy(
      "test_policy",
      "Test policy",
      [
        {
          condition_name: "always_false",
          description: "Never matches",
          evaluable: () => false,
        },
      ],
      "promote",
      "Rationale",
      "user"
    );

    registry.registerPolicy(policy);

    const context = {
      artifact_id: uuidv4(),
      artifact_kind: "test",
      evaluation_data: {},
    };

    const analysis = detector.detectContradictions(context);

    expect(analysis.has_contradictions).toBe(false);
  });

  test("getContradictionReport summarizes contradictions", () => {
    const registry = new JudgmentPolicyRegistry();
    const detector = createContradictionDetector(registry);

    const policy1 = createJudgmentPolicy(
      "p1",
      "Policy 1",
      [],
      "promote",
      "Rationale",
      "user"
    );
    const policy2 = createJudgmentPolicy(
      "p2",
      "Policy 2",
      [],
      "block",
      "Rationale",
      "user"
    );

    registry.registerPolicy(policy1);
    registry.registerPolicy(policy2);

    const analyses = [
      detector.detectContradictions({
        artifact_id: uuidv4(),
        artifact_kind: "test",
        evaluation_data: {},
      }),
      detector.detectContradictions({
        artifact_id: uuidv4(),
        artifact_kind: "test",
        evaluation_data: {},
      }),
    ];

    const report = detector.getContradictionReport(analyses);

    expect(report.total_artifacts).toBe(2);
    expect(report.artifacts_with_contradictions).toBe(2);
    expect(report.contradiction_count).toBeGreaterThan(0);
  });
});

describe("Precedent Matcher", () => {
  test("findSimilarPrecedents returns matching precedents", () => {
    const matcher = createPrecedentMatcher();

    const precedent = createJudgmentRecord(
      uuidv4(),
      "test_type",
      "user",
      "human",
      "promote",
      "Good rationale",
      uuidv4()
    );

    matcher.registerPrecedent(precedent);

    const query = createJudgmentRecord(
      uuidv4(),
      "test_type",
      "user",
      "human",
      "promote",
      "Similar rationale",
      uuidv4()
    );

    const matches = matcher.findSimilarPrecedents(query, 0.5);

    expect(matches.length).toBeGreaterThan(0);
    expect(matches[0].similarity.artifact_kind_match).toBe(true);
  });

  test("findSimilarPrecedents applies threshold", () => {
    const matcher = createPrecedentMatcher();

    const precedent = createJudgmentRecord(
      uuidv4(),
      "different_type",
      "user",
      "human",
      "block",
      "Unrelated",
      uuidv4()
    );

    matcher.registerPrecedent(precedent);

    const query = createJudgmentRecord(
      uuidv4(),
      "test_type",
      "user",
      "human",
      "promote",
      "Query",
      uuidv4()
    );

    const matches = matcher.findSimilarPrecedents(query, 0.9);

    expect(matches).toHaveLength(0);
  });

  test("getPrecedentReport summarizes precedents", () => {
    const matcher = createPrecedentMatcher();

    const p1 = createJudgmentRecord(
      uuidv4(),
      "type1",
      "user",
      "human",
      "promote",
      "Rationale",
      uuidv4()
    );
    const p2 = createJudgmentRecord(
      uuidv4(),
      "type2",
      "user",
      "human",
      "block",
      "Rationale",
      uuidv4()
    );

    matcher.registerPrecedent(p1);
    matcher.registerPrecedent(p2);

    const report = matcher.getPrecedentReport();

    expect(report.total_precedents).toBe(2);
    expect(report.by_outcome["promote"]).toBe(1);
    expect(report.by_outcome["block"]).toBe(1);
    expect(report.by_artifact_kind["type1"]).toBe(1);
    expect(report.by_artifact_kind["type2"]).toBe(1);
  });
});
