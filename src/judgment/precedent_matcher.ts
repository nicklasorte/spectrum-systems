/**
 * Precedent Matcher
 * Finds similar past decisions and enables reuse of reasoning
 */

import { JudgmentRecord } from "./judgment_record";

export interface SimilarityMetrics {
  artifact_kind_match: boolean;
  context_similarity: number; // 0-1
  evidence_overlap: number; // 0-1
  policy_alignment: number; // 0-1
  overall_similarity: number; // 0-1
}

export interface MatchedPrecedent {
  precedent: JudgmentRecord;
  similarity: SimilarityMetrics;
  applicable: boolean;
  reasoning: string;
}

export class PrecedentMatcher {
  private precedents: Map<string, JudgmentRecord> = new Map();

  registerPrecedent(record: JudgmentRecord): void {
    this.precedents.set(record.decision_id, record);
  }

  findSimilarPrecedents(
    query: JudgmentRecord,
    threshold: number = 0.7
  ): MatchedPrecedent[] {
    const matches: MatchedPrecedent[] = [];

    for (const precedent of this.precedents.values()) {
      if (precedent.decision_id === query.decision_id) continue; // Skip self

      const similarity = this.calculateSimilarity(query, precedent);

      if (similarity.overall_similarity >= threshold) {
        matches.push({
          precedent,
          similarity,
          applicable: this.isApplicable(query, precedent, similarity),
          reasoning: this.generateReasoning(query, precedent, similarity),
        });
      }
    }

    // Sort by overall similarity, descending
    matches.sort((a, b) => b.similarity.overall_similarity - a.similarity.overall_similarity);

    return matches;
  }

  private calculateSimilarity(
    query: JudgmentRecord,
    precedent: JudgmentRecord
  ): SimilarityMetrics {
    const artifactKindMatch = query.subject_artifact_kind === precedent.subject_artifact_kind;

    const contextSimilarity = this.calculateContextSimilarity(
      query.decision_context,
      precedent.decision_context
    );

    const evidenceOverlap = this.calculateEvidenceOverlap(
      query.evidence,
      precedent.evidence
    );

    const policyAlignment = this.calculatePolicyAlignment(
      query.policies_considered,
      precedent.policies_considered
    );

    // Weight the overall similarity
    const overall =
      artifactKindMatch * 0.3 +
      contextSimilarity * 0.25 +
      evidenceOverlap * 0.25 +
      policyAlignment * 0.2;

    return {
      artifact_kind_match: artifactKindMatch,
      context_similarity: contextSimilarity,
      evidence_overlap: evidenceOverlap,
      policy_alignment: policyAlignment,
      overall_similarity: overall,
    };
  }

  private calculateContextSimilarity(
    queryContext: Record<string, any>,
    precedentContext: Record<string, any>
  ): number {
    const queryKeys = new Set(Object.keys(queryContext));
    const precedentKeys = new Set(Object.keys(precedentContext));

    if (queryKeys.size === 0 && precedentKeys.size === 0) return 1.0;
    if (queryKeys.size === 0 || precedentKeys.size === 0) return 0.0;

    const intersection = new Set([...queryKeys].filter((k) => precedentKeys.has(k)));
    const union = new Set([...queryKeys, ...precedentKeys]);

    return intersection.size / union.size;
  }

  private calculateEvidenceOverlap(
    queryEvidence: Array<{ artifact_kind: string }>,
    precedentEvidence: Array<{ artifact_kind: string }>
  ): number {
    if (queryEvidence.length === 0 && precedentEvidence.length === 0) return 1.0;
    if (queryEvidence.length === 0 || precedentEvidence.length === 0) return 0.0;

    const queryKinds = new Set(queryEvidence.map((e) => e.artifact_kind));
    const precedentKinds = new Set(precedentEvidence.map((e) => e.artifact_kind));

    const intersection = new Set(
      [...queryKinds].filter((k) => precedentKinds.has(k))
    );
    const union = new Set([...queryKinds, ...precedentKinds]);

    return intersection.size / union.size;
  }

  private calculatePolicyAlignment(
    queryPolicies: Array<{ policy_name: string }>,
    precedentPolicies: Array<{ policy_name: string }>
  ): number {
    if (queryPolicies.length === 0 && precedentPolicies.length === 0) return 1.0;
    if (queryPolicies.length === 0 || precedentPolicies.length === 0) return 0.0;

    const queryNames = new Set(queryPolicies.map((p) => p.policy_name));
    const precedentNames = new Set(precedentPolicies.map((p) => p.policy_name));

    const intersection = new Set(
      [...queryNames].filter((n) => precedentNames.has(n))
    );
    const union = new Set([...queryNames, ...precedentNames]);

    return intersection.size / union.size;
  }

  private isApplicable(
    query: JudgmentRecord,
    precedent: JudgmentRecord,
    similarity: SimilarityMetrics
  ): boolean {
    // Artifact kind must match for applicability
    if (!similarity.artifact_kind_match) return false;

    // High similarity required for applicability
    if (similarity.overall_similarity < 0.7) return false;

    // Same decision outcome suggests applicability
    const outcomeMatches = query.decision_outcome === precedent.decision_outcome;

    // Applicability increases with higher similarity
    return outcomeMatches || similarity.overall_similarity > 0.8;
  }

  private generateReasoning(
    query: JudgmentRecord,
    precedent: JudgmentRecord,
    similarity: SimilarityMetrics
  ): string {
    const parts = [
      `Precedent similarity: ${(similarity.overall_similarity * 100).toFixed(1)}%`,
      `- Artifact kind match: ${similarity.artifact_kind_match ? "yes" : "no"}`,
      `- Context similarity: ${(similarity.context_similarity * 100).toFixed(1)}%`,
      `- Evidence overlap: ${(similarity.evidence_overlap * 100).toFixed(1)}%`,
      `- Policy alignment: ${(similarity.policy_alignment * 100).toFixed(1)}%`,
      ``,
      `Precedent decision: ${precedent.decision_outcome}`,
      `Precedent rationale: ${precedent.decision_rationale}`,
    ];

    if (query.decision_outcome === precedent.decision_outcome) {
      parts.push(`✓ Same decision outcome - reasoning highly applicable`);
    } else {
      parts.push(
        `⚠ Different outcome (${precedent.decision_outcome} vs ${query.decision_outcome}) - review for context differences`
      );
    }

    return parts.join("\n");
  }

  getPrecedentReport(): {
    total_precedents: number;
    by_outcome: Record<string, number>;
    by_artifact_kind: Record<string, number>;
  } {
    const byOutcome: Record<string, number> = {};
    const byArtifactKind: Record<string, number> = {};

    for (const precedent of this.precedents.values()) {
      byOutcome[precedent.decision_outcome] = (byOutcome[precedent.decision_outcome] || 0) + 1;
      byArtifactKind[precedent.subject_artifact_kind] =
        (byArtifactKind[precedent.subject_artifact_kind] || 0) + 1;
    }

    return {
      total_precedents: this.precedents.size,
      by_outcome: byOutcome,
      by_artifact_kind: byArtifactKind,
    };
  }
}

export function createPrecedentMatcher(): PrecedentMatcher {
  return new PrecedentMatcher();
}
