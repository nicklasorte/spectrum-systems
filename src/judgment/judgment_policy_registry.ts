/**
 * Judgment Policy Registry
 * Versioned, tested, gated policies for decision-making
 */

import { v4 as uuidv4 } from "uuid";

export interface DecisionCondition {
  condition_name: string;
  description: string;
  evaluable: (context: Record<string, any>) => boolean;
}

export interface JudgmentPolicy {
  policy_id: string;
  policy_name: string;
  policy_version: number;
  description: string;

  // When policy applies
  conditions: DecisionCondition[];

  // What policy prescribes
  decision_outcome: "promote" | "freeze" | "block" | "warn" | "escalate";
  outcome_rationale: string;

  // Lifecycle
  created_at: string;
  created_by: string;
  effective_date: string;
  deprecated: boolean;
  deprecation_reason?: string;
  successor_policy_id?: string;

  // Testing & validation
  test_cases_count: number;
  test_pass_rate: number;
  last_tested_at?: string;

  // Audit trail
  supersedes?: string;
}

export interface PolicyEvaluationContext {
  artifact_id: string;
  artifact_kind: string;
  evaluation_data: Record<string, any>;
}

export class JudgmentPolicyRegistry {
  private policies: Map<string, JudgmentPolicy[]> = new Map(); // policy_name -> versions
  private activeVersions: Map<string, number> = new Map(); // policy_name -> active version

  registerPolicy(policy: JudgmentPolicy): void {
    if (policy.deprecated) {
      console.warn(
        `Registering deprecated policy: ${policy.policy_name} v${policy.policy_version}`
      );
    }

    const versions = this.policies.get(policy.policy_name) || [];
    versions.push(policy);
    this.policies.set(policy.policy_name, versions);

    // New policy is active by default
    this.activeVersions.set(policy.policy_name, policy.policy_version);
  }

  activatePolicy(policyName: string, version: number): boolean {
    const versions = this.policies.get(policyName);
    if (!versions) return false;

    const policy = versions.find((p) => p.policy_version === version);
    if (!policy || policy.deprecated) return false;

    this.activeVersions.set(policyName, version);
    return true;
  }

  getPolicy(
    policyName: string,
    version?: number
  ): JudgmentPolicy | undefined {
    const versions = this.policies.get(policyName);
    if (!versions) return undefined;

    if (version === undefined) {
      const activeVersion = this.activeVersions.get(policyName);
      version = activeVersion;
    }

    return versions.find((p) => p.policy_version === version);
  }

  getActivePolicy(policyName: string): JudgmentPolicy | undefined {
    const activeVersion = this.activeVersions.get(policyName);
    if (!activeVersion) return undefined;
    return this.getPolicy(policyName, activeVersion);
  }

  getAllVersions(policyName: string): JudgmentPolicy[] {
    return this.policies.get(policyName) || [];
  }

  evaluatePolicy(
    policyName: string,
    context: PolicyEvaluationContext
  ): { matches: boolean; outcome: string; rationale: string } {
    const policy = this.getActivePolicy(policyName);
    if (!policy) {
      return {
        matches: false,
        outcome: "unknown",
        rationale: `Policy ${policyName} not found`,
      };
    }

    // Evaluate all conditions
    const conditionResults = policy.conditions.map((cond) => {
      try {
        return cond.evaluable(context.evaluation_data);
      } catch (e) {
        console.error(`Error evaluating condition ${cond.condition_name}:`, e);
        return false;
      }
    });

    const allConditionsMet = conditionResults.every((result) => result);

    return {
      matches: allConditionsMet,
      outcome: policy.decision_outcome,
      rationale: allConditionsMet
        ? policy.outcome_rationale
        : `Conditions not met for policy ${policyName}`,
    };
  }

  findMatchingPolicies(
    context: PolicyEvaluationContext
  ): Array<{ policy: JudgmentPolicy; matches: boolean }> {
    const results: Array<{ policy: JudgmentPolicy; matches: boolean }> = [];

    for (const versions of this.policies.values()) {
      const activePolicy = versions.find(
        (p) => p.policy_version === this.activeVersions.get(p.policy_name)
      );
      if (!activePolicy || activePolicy.deprecated) continue;

      const eval = this.evaluatePolicy(activePolicy.policy_name, context);
      results.push({
        policy: activePolicy,
        matches: eval.matches,
      });
    }

    return results;
  }

  listActivePolicies(): JudgmentPolicy[] {
    const active: JudgmentPolicy[] = [];

    for (const [policyName, version] of this.activeVersions) {
      const policy = this.getPolicy(policyName, version);
      if (policy && !policy.deprecated) {
        active.push(policy);
      }
    }

    return active;
  }

  listAllPolicies(): JudgmentPolicy[] {
    const all: JudgmentPolicy[] = [];
    for (const versions of this.policies.values()) {
      all.push(...versions);
    }
    return all;
  }
}

export function createJudgmentPolicy(
  policyName: string,
  description: string,
  conditions: DecisionCondition[],
  outcome: "promote" | "freeze" | "block" | "warn" | "escalate",
  rationale: string,
  createdBy: string
): JudgmentPolicy {
  return {
    policy_id: uuidv4(),
    policy_name,
    policy_version: 1,
    description,
    conditions,
    decision_outcome: outcome,
    outcome_rationale: rationale,
    created_at: new Date().toISOString(),
    created_by: createdBy,
    effective_date: new Date().toISOString(),
    deprecated: false,
    test_cases_count: 0,
    test_pass_rate: 0,
  };
}

export function deprecatePolicy(
  policy: JudgmentPolicy,
  reason: string,
  successorId: string
): JudgmentPolicy {
  return {
    ...policy,
    deprecated: true,
    deprecation_reason: reason,
    successor_policy_id: successorId,
  };
}
