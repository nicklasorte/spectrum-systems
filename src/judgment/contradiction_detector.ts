/**
 * Contradiction Detector
 * Detects conflicting policy matches for the same artifact
 */

import {
  JudgmentPolicy,
  JudgmentPolicyRegistry,
  PolicyEvaluationContext,
} from "./judgment_policy_registry";

export interface Contradiction {
  contradiction_id: string;
  conflict_type: "outcome_conflict" | "condition_conflict";
  policy_1: {
    policy_name: string;
    policy_version: number;
    decision_outcome: string;
  };
  policy_2: {
    policy_name: string;
    policy_version: number;
    decision_outcome: string;
  };
  artifact_id: string;
  severity: "critical" | "warning";
  remediation: string;
  detected_at: string;
}

export interface ContradictionAnalysis {
  artifact_id: string;
  has_contradictions: boolean;
  contradictions: Contradiction[];
  resolved: boolean;
  resolution?: string;
}

export class ContradictionDetector {
  constructor(private policyRegistry: JudgmentPolicyRegistry) {}

  detectContradictions(
    context: PolicyEvaluationContext
  ): ContradictionAnalysis {
    const matchingPolicies = this.policyRegistry.findMatchingPolicies(context);
    const matches = matchingPolicies.filter((m) => m.matches);

    const contradictions: Contradiction[] = [];

    // Find conflicting outcomes
    const outcomes = new Map<string, JudgmentPolicy[]>();
    for (const { policy } of matches) {
      const outcome = policy.decision_outcome;
      const policies = outcomes.get(outcome) || [];
      policies.push(policy);
      outcomes.set(outcome, policies);
    }

    // If multiple different outcomes, we have a contradiction
    const outcomeKeys = Array.from(outcomes.keys());
    if (outcomeKeys.length > 1) {
      for (let i = 0; i < outcomeKeys.length; i++) {
        for (let j = i + 1; j < outcomeKeys.length; j++) {
          const outcome1 = outcomeKeys[i];
          const outcome2 = outcomeKeys[j];
          const policies1 = outcomes.get(outcome1)!;
          const policies2 = outcomes.get(outcome2)!;

          for (const policy1 of policies1) {
            for (const policy2 of policies2) {
              contradictions.push({
                contradiction_id: `${policy1.policy_id}-vs-${policy2.policy_id}`,
                conflict_type: "outcome_conflict",
                policy_1: {
                  policy_name: policy1.policy_name,
                  policy_version: policy1.policy_version,
                  decision_outcome: policy1.decision_outcome,
                },
                policy_2: {
                  policy_name: policy2.policy_name,
                  policy_version: policy2.policy_version,
                  decision_outcome: policy2.decision_outcome,
                },
                artifact_id: context.artifact_id,
                severity: this.getConflictSeverity(outcome1, outcome2),
                remediation: this.generateRemediation(policy1, policy2),
                detected_at: new Date().toISOString(),
              });
            }
          }
        }
      }
    }

    return {
      artifact_id: context.artifact_id,
      has_contradictions: contradictions.length > 0,
      contradictions,
      resolved: false,
    };
  }

  private getConflictSeverity(outcome1: string, outcome2: string): "critical" | "warning" {
    const criticalOutcomes = new Set(["promote", "block"]);
    if (criticalOutcomes.has(outcome1) && criticalOutcomes.has(outcome2)) {
      return "critical";
    }
    return "warning";
  }

  private generateRemediation(policy1: JudgmentPolicy, policy2: JudgmentPolicy): string {
    return [
      `Contradiction between policies:`,
      `- ${policy1.policy_name} v${policy1.policy_version} → ${policy1.decision_outcome}`,
      `- ${policy2.policy_name} v${policy2.policy_version} → ${policy2.decision_outcome}`,
      ``,
      `Remediation options:`,
      `1. Escalate to human decision maker`,
      `2. Define policy precedence rules`,
      `3. Refine policy conditions to eliminate overlap`,
      `4. Deprecate conflicting policy in favor of primary policy`,
    ].join("\n");
  }

  resolveContradiction(
    analysis: ContradictionAnalysis,
    resolution: string
  ): ContradictionAnalysis {
    return {
      ...analysis,
      resolved: true,
      resolution,
    };
  }

  getContradictionReport(
    analyses: ContradictionAnalysis[]
  ): {
    total_artifacts: number;
    artifacts_with_contradictions: number;
    contradiction_count: number;
    severity_breakdown: Record<string, number>;
    critical_artifacts: string[];
  } {
    const critical = new Set<string>();
    const severityBreakdown: Record<string, number> = { critical: 0, warning: 0 };

    let totalContradictions = 0;

    for (const analysis of analyses) {
      if (analysis.has_contradictions) {
        if (analysis.contradictions.some((c) => c.severity === "critical")) {
          critical.add(analysis.artifact_id);
        }
        for (const contradiction of analysis.contradictions) {
          severityBreakdown[contradiction.severity]++;
          totalContradictions++;
        }
      }
    }

    return {
      total_artifacts: analyses.length,
      artifacts_with_contradictions: analyses.filter((a) => a.has_contradictions)
        .length,
      contradiction_count: totalContradictions,
      severity_breakdown: severityBreakdown,
      critical_artifacts: Array.from(critical),
    };
  }
}

export function createContradictionDetector(
  policyRegistry: JudgmentPolicyRegistry
): ContradictionDetector {
  return new ContradictionDetector(policyRegistry);
}
