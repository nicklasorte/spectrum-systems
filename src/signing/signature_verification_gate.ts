/**
 * Signature Verification Gate
 * Fail-closed gate for promotion requiring verified signatures
 */

import { v4 as uuidv4 } from "uuid";
import { SignatureVerifier, VerificationResult } from "./signature_verifier";
import { SignedArtifact } from "./artifact_signer";
import { SLSABuilder, SLSACompliance } from "../slsa/slsa_builder";

export interface PromotionSignatureCheckResult {
  artifact_id: string;
  promotion_approved: boolean;
  signature_verification: VerificationResult;
  slsa_compliance: SLSACompliance | null;
  failed_checks: string[];
  warnings: string[];
  timestamp: string;
}

export class SignatureVerificationGate {
  constructor(
    private verifier: SignatureVerifier,
    private slsaBuilder: SLSABuilder
  ) {}

  checkPromotionSignatures(
    artifactId: string,
    signedArtifact: SignedArtifact,
    originalContent: Record<string, any>
  ): PromotionSignatureCheckResult {
    const failedChecks: string[] = [];
    const warnings: string[] = [];

    // Check 1: Verify signature
    const signatureVerification = this.verifier.verifySignature(
      signedArtifact,
      originalContent
    );

    if (!signatureVerification.verified) {
      failedChecks.push(
        `Signature verification failed: ${signatureVerification.errors.map((e) => e.message).join("; ")}`
      );
    }

    // Check 2: Verify SLSA compliance
    const slsaCompliance = this.slsaBuilder.verifySLSACompliance(
      artifactId,
      signatureVerification.verified
    );

    if (slsaCompliance.gaps.length > 0) {
      warnings.push(`SLSA gaps: ${slsaCompliance.gaps.join("; ")}`);
    }

    if (!slsaCompliance.provenance_signed) {
      failedChecks.push("Provenance is not cryptographically signed");
    }

    if (!slsaCompliance.hermetic_build) {
      warnings.push("Build was not hermetic (external dependencies detected)");
    }

    // Aggregate warnings from verification
    warnings.push(...signatureVerification.warnings);

    const promotionApproved =
      signatureVerification.verified && failedChecks.length === 0;

    return {
      artifact_id: artifactId,
      promotion_approved: promotionApproved,
      signature_verification: signatureVerification,
      slsa_compliance: slsaCompliance,
      failed_checks: failedChecks,
      warnings,
      timestamp: new Date().toISOString(),
    };
  }

  checkMultiplePromotions(
    artifacts: Array<{
      artifact_id: string;
      signed: SignedArtifact;
      content: Record<string, any>;
    }>
  ): PromotionSignatureCheckResult[] {
    return artifacts.map((artifact) =>
      this.checkPromotionSignatures(
        artifact.artifact_id,
        artifact.signed,
        artifact.content
      )
    );
  }

  generateVerificationReport(
    result: PromotionSignatureCheckResult
  ): string {
    const lines = [
      `Signature Verification Report`,
      `=============================`,
      `Artifact: ${result.artifact_id}`,
      `Status: ${result.promotion_approved ? "✓ APPROVED" : "✗ BLOCKED"}`,
      `Timestamp: ${result.timestamp}`,
      ``,
      `Signature Verification:`,
      `  Verified: ${result.signature_verification.verified ? "✓" : "✗"}`,
      `  Valid: ${result.signature_verification.signature_valid ? "✓" : "✗"}`,
      `  Key Trusted: ${result.signature_verification.key_trusted ? "✓" : "✗"}`,
    ];

    if (result.signature_verification.errors.length > 0) {
      lines.push(`  Errors:`);
      for (const error of result.signature_verification.errors) {
        lines.push(`    - [${error.severity}] ${error.message}`);
      }
    }

    if (result.slsa_compliance) {
      lines.push(``, `SLSA Level 3 Compliance:`);
      for (const [requirement, met] of result.slsa_compliance.requirements_met) {
        lines.push(`  ${met ? "✓" : "✗"} ${requirement}`);
      }
    }

    if (result.failed_checks.length > 0) {
      lines.push(``, `Failed Checks:`);
      for (const check of result.failed_checks) {
        lines.push(`  ✗ ${check}`);
      }
    }

    if (result.warnings.length > 0) {
      lines.push(``, `Warnings:`);
      for (const warning of result.warnings) {
        lines.push(`  ⚠ ${warning}`);
      }
    }

    return lines.join("\n");
  }
}

export function createSignatureVerificationGate(
  verifier: SignatureVerifier,
  slsaBuilder: SLSABuilder
): SignatureVerificationGate {
  return new SignatureVerificationGate(verifier, slsaBuilder);
}
