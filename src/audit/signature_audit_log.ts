/**
 * Signature Audit Log
 * Records all signing and verification operations for compliance
 */

import { v4 as uuidv4 } from "uuid";
import { VerificationResult } from "../signing/signature_verifier";
import { SignedArtifact } from "../signing/artifact_signer";

export interface AuditLogEntry {
  entry_id: string;
  timestamp: string;
  operation: "sign" | "verify" | "verification_gate";
  artifact_id: string;
  actor: string;
  result: "success" | "failure";
  details: Record<string, any>;
}

export interface AuditSummary {
  total_entries: number;
  operations_by_type: Record<string, number>;
  success_rate: number;
  artifacts_signed: number;
  artifacts_verified: number;
  verification_failures: number;
  latest_entry: AuditLogEntry | null;
}

export class SignatureAuditLog {
  private entries: AuditLogEntry[] = [];

  recordSigning(
    artifactId: string,
    actor: string,
    signedArtifact: SignedArtifact,
    result: "success" | "failure",
    details?: Record<string, any>
  ): AuditLogEntry {
    const entry: AuditLogEntry = {
      entry_id: uuidv4(),
      timestamp: new Date().toISOString(),
      operation: "sign",
      artifact_id: artifactId,
      actor,
      result,
      details: {
        signer_key_id: signedArtifact.signer_key_id,
        signature_algorithm: signedArtifact.signature_algorithm,
        ...details,
      },
    };

    this.entries.push(entry);
    return entry;
  }

  recordVerification(
    artifactId: string,
    actor: string,
    verification: VerificationResult,
    details?: Record<string, any>
  ): AuditLogEntry {
    const entry: AuditLogEntry = {
      entry_id: uuidv4(),
      timestamp: new Date().toISOString(),
      operation: "verify",
      artifact_id: artifactId,
      actor,
      result: verification.verified ? "success" : "failure",
      details: {
        signature_valid: verification.signature_valid,
        key_trusted: verification.key_trusted,
        errors: verification.errors.map((e) => ({
          code: e.error_code,
          message: e.message,
          severity: e.severity,
        })),
        ...details,
      },
    };

    this.entries.push(entry);
    return entry;
  }

  recordVerificationGateCheck(
    artifactId: string,
    actor: string,
    approved: boolean,
    failedChecks: string[],
    details?: Record<string, any>
  ): AuditLogEntry {
    const entry: AuditLogEntry = {
      entry_id: uuidv4(),
      timestamp: new Date().toISOString(),
      operation: "verification_gate",
      artifact_id: artifactId,
      actor,
      result: approved ? "success" : "failure",
      details: {
        approved,
        failed_checks: failedChecks,
        check_count: failedChecks.length,
        ...details,
      },
    };

    this.entries.push(entry);
    return entry;
  }

  getEntries(
    filter?: {
      operation?: "sign" | "verify" | "verification_gate";
      artifact_id?: string;
      actor?: string;
      result?: "success" | "failure";
    }
  ): AuditLogEntry[] {
    if (!filter) return this.entries;

    return this.entries.filter((entry) => {
      if (filter.operation && entry.operation !== filter.operation) return false;
      if (filter.artifact_id && entry.artifact_id !== filter.artifact_id)
        return false;
      if (filter.actor && entry.actor !== filter.actor) return false;
      if (filter.result && entry.result !== filter.result) return false;
      return true;
    });
  }

  getSummary(): AuditSummary {
    const operationCounts: Record<string, number> = {};
    let successCount = 0;

    for (const entry of this.entries) {
      operationCounts[entry.operation] = (operationCounts[entry.operation] || 0) + 1;
      if (entry.result === "success") successCount++;
    }

    const artifactsSigned = this.entries.filter(
      (e) => e.operation === "sign" && e.result === "success"
    ).length;

    const artifactsVerified = new Set(
      this.entries
        .filter((e) => e.operation === "verify" && e.result === "success")
        .map((e) => e.artifact_id)
    ).size;

    const verificationFailures = this.entries.filter(
      (e) => e.operation === "verify" && e.result === "failure"
    ).length;

    const successRate =
      this.entries.length > 0 ? (successCount / this.entries.length) * 100 : 0;

    return {
      total_entries: this.entries.length,
      operations_by_type: operationCounts,
      success_rate: successRate,
      artifacts_signed: artifactsSigned,
      artifacts_verified: artifactsVerified,
      verification_failures: verificationFailures,
      latest_entry: this.entries[this.entries.length - 1] || null,
    };
  }

  exportAsJSON(): string {
    return JSON.stringify(this.entries, null, 2);
  }

  getArtifactHistory(artifactId: string): AuditLogEntry[] {
    return this.getEntries({ artifact_id: artifactId });
  }

  getActorHistory(actor: string): AuditLogEntry[] {
    return this.getEntries({ actor });
  }
}

export function createSignatureAuditLog(): SignatureAuditLog {
  return new SignatureAuditLog();
}
