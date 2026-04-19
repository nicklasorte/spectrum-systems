/**
 * Judgment Record Artifact
 * First-class decision rationale artifacts with explicit evidence and reasoning
 */

import { v4 as uuidv4 } from "uuid";

export interface Evidence {
  artifact_id: string;
  artifact_kind: string;
  relevance: "high" | "medium" | "low";
  reasoning: string;
}

export interface PolicySelection {
  policy_name: string;
  policy_version: number;
  matched: boolean;
  match_strength: "strong" | "weak" | "partial";
  conditions_met: string[];
}

export interface Precedent {
  precedent_id: string;
  decision_id: string;
  similarity_score: number;
  outcome_similarity: boolean;
  cited_reasoning: string;
}

export interface JudgmentRecord {
  artifact_kind: "judgment_record";
  decision_id: string;
  decision_timestamp: string;
  decider_id: string;
  decider_role: "system" | "human" | "automated";

  // What was being decided
  subject_artifact_id: string;
  subject_artifact_kind: string;
  decision_context: Record<string, any>;

  // Evidence considered
  evidence: Evidence[];

  // Policies applied
  policies_considered: PolicySelection[];
  primary_policy?: string;

  // Precedents cited
  precedents: Precedent[];

  // Alternatives evaluated
  alternatives_evaluated: Array<{
    alternative: string;
    evaluation: string;
    rejected_reason: string;
  }>;

  // Decision outcome
  decision_outcome: "promote" | "freeze" | "block" | "warn" | "escalate";
  decision_rationale: string;
  confidence_level: number; // 0-1

  // Metadata
  trace_id: string;
  appeal_possible: boolean;
  appeal_deadline?: string;

  created_at: string;
}

export function createJudgmentRecord(
  subjectArtifactId: string,
  subjectArtifactKind: string,
  deciderId: string,
  deciderRole: "system" | "human" | "automated",
  decisionOutcome: "promote" | "freeze" | "block" | "warn" | "escalate",
  rationale: string,
  traceId: string,
  confidenceLevel: number = 0.95
): JudgmentRecord {
  return {
    artifact_kind: "judgment_record",
    decision_id: uuidv4(),
    decision_timestamp: new Date().toISOString(),
    decider_id: deciderId,
    decider_role: deciderRole,
    subject_artifact_id: subjectArtifactId,
    subject_artifact_kind: subjectArtifactKind,
    decision_context: {},
    evidence: [],
    policies_considered: [],
    precedents: [],
    alternatives_evaluated: [],
    decision_outcome: decisionOutcome,
    decision_rationale: rationale,
    confidence_level: confidenceLevel,
    trace_id: traceId,
    appeal_possible: true,
    created_at: new Date().toISOString(),
  };
}

export function addEvidence(
  record: JudgmentRecord,
  artifactId: string,
  artifactKind: string,
  relevance: "high" | "medium" | "low",
  reasoning: string
): JudgmentRecord {
  return {
    ...record,
    evidence: [
      ...record.evidence,
      {
        artifact_id: artifactId,
        artifact_kind: artifactKind,
        relevance,
        reasoning,
      },
    ],
  };
}

export function addPolicySelection(
  record: JudgmentRecord,
  policyName: string,
  policyVersion: number,
  matched: boolean,
  matchStrength: "strong" | "weak" | "partial",
  conditionsMet: string[]
): JudgmentRecord {
  return {
    ...record,
    policies_considered: [
      ...record.policies_considered,
      {
        policy_name: policyName,
        policy_version: policyVersion,
        matched,
        match_strength: matchStrength,
        conditions_met: conditionsMet,
      },
    ],
  };
}

export function addPrecedent(
  record: JudgmentRecord,
  precedentId: string,
  decisionId: string,
  similarityScore: number,
  outcomeMatches: boolean,
  reasoning: string
): JudgmentRecord {
  return {
    ...record,
    precedents: [
      ...record.precedents,
      {
        precedent_id: precedentId,
        decision_id: decisionId,
        similarity_score: similarityScore,
        outcome_similarity: outcomeMatches,
        cited_reasoning: reasoning,
      },
    ],
  };
}

export function addAlternative(
  record: JudgmentRecord,
  alternative: string,
  evaluation: string,
  rejectionReason: string
): JudgmentRecord {
  return {
    ...record,
    alternatives_evaluated: [
      ...record.alternatives_evaluated,
      {
        alternative,
        evaluation,
        rejected_reason: rejectionReason,
      },
    ],
  };
}

export function validateJudgmentRecord(
  record: JudgmentRecord
): { valid: boolean; issues: string[] } {
  const issues: string[] = [];

  if (!record.subject_artifact_id) {
    issues.push("Missing subject_artifact_id");
  }

  if (!record.decider_id) {
    issues.push("Missing decider_id");
  }

  if (!record.decision_outcome) {
    issues.push("Missing decision_outcome");
  }

  if (!record.decision_rationale) {
    issues.push("Missing decision_rationale");
  }

  if (!record.trace_id) {
    issues.push("Missing trace_id");
  }

  if (record.confidence_level < 0 || record.confidence_level > 1) {
    issues.push("confidence_level must be between 0 and 1");
  }

  if (record.evidence.length === 0) {
    issues.push("No evidence provided");
  }

  if (record.policies_considered.length === 0) {
    issues.push("No policies considered");
  }

  return {
    valid: issues.length === 0,
    issues,
  };
}
