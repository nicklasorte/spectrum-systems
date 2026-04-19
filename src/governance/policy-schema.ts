import { v4 as uuidv4 } from "uuid";

/**
 * Policy-as-Code Schema
 * Versioned policies with testing and gradual rollout
 */

export interface PolicyDefinition {
  artifact_kind: "policy_definition";
  artifact_id: string;
  policy_name: string;
  policy_version: number;
  policy_text: string;
  owner: string;
  created_at: string;
  supersedes?: string;
  status: "draft" | "reviewed" | "active" | "deprecated";
  test_cases_count: number;
  test_pass_rate: number;
  rollout_percentage: number;
  rollout_started_at?: string;
  incidents_since_deployment: number;
}

export interface PolicyEvalCase {
  artifact_kind: "policy_eval_case";
  artifact_id: string;
  policy_id: string;
  test_input: Record<string, any>;
  expected_output: "allow" | "warn" | "freeze" | "block";
  description: string;
  created_at: string;
}

export interface PolicyEvalResult {
  artifact_kind: "policy_eval_result";
  artifact_id: string;
  policy_id: string;
  eval_case_id: string;
  actual_output: "allow" | "warn" | "freeze" | "block";
  matches_expected: boolean;
  executed_at: string;
}

export function createPolicy(
  policyName: string,
  policyText: string,
  owner: string,
  supersedes?: string
): PolicyDefinition {
  return {
    artifact_kind: "policy_definition",
    artifact_id: uuidv4(),
    policy_name,
    policy_version: 1,
    policy_text,
    owner,
    created_at: new Date().toISOString(),
    supersedes,
    status: "draft",
    test_cases_count: 0,
    test_pass_rate: 0,
    rollout_percentage: 0,
    incidents_since_deployment: 0,
  };
}

export function createPolicyEvalCase(
  policyId: string,
  testInput: Record<string, any>,
  expectedOutput: "allow" | "warn" | "freeze" | "block",
  description: string
): PolicyEvalCase {
  return {
    artifact_kind: "policy_eval_case",
    artifact_id: uuidv4(),
    policy_id: policyId,
    test_input: testInput,
    expected_output: expectedOutput,
    description,
    created_at: new Date().toISOString(),
  };
}
