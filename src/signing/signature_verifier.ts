/**
 * Signature Verifier
 * Verifies cryptographic signatures and artifact integrity
 */

import { v4 as uuidv4 } from "uuid";
import crypto from "crypto";
import { SignedArtifact } from "./artifact_signer";

export interface VerificationResult {
  verification_id: string;
  artifact_id: string;
  verified: boolean;
  signature_valid: boolean;
  key_trusted: boolean;
  verification_timestamp: string;
  verification_method: "public_key";
  errors: VerificationError[];
  warnings: string[];
}

export interface VerificationError {
  error_code:
    | "signature_invalid"
    | "key_not_found"
    | "key_not_trusted"
    | "hash_mismatch"
    | "missing_signature";
  message: string;
  severity: "critical" | "warning";
}

export class SignatureVerifier {
  private trustedKeys: Map<string, crypto.KeyObject> = new Map();

  registerTrustedKey(keyId: string, publicKey: crypto.KeyObject): void {
    this.trustedKeys.set(keyId, publicKey);
  }

  isTrustedKey(keyId: string): boolean {
    return this.trustedKeys.has(keyId);
  }

  verifySignature(
    signedArtifact: SignedArtifact,
    originalContent: Record<string, any>
  ): VerificationResult {
    const errors: VerificationError[] = [];
    const warnings: string[] = [];

    // Check 1: Signature exists
    if (!signedArtifact.signature) {
      errors.push({
        error_code: "missing_signature",
        message: "Artifact has no signature",
        severity: "critical",
      });
      return this.failedVerification(signedArtifact.artifact_id, errors, warnings);
    }

    // Check 2: Key is trusted
    if (!this.isTrustedKey(signedArtifact.signer_key_id)) {
      errors.push({
        error_code: "key_not_trusted",
        message: `Signer key ${signedArtifact.signer_key_id} is not in trusted key set`,
        severity: "critical",
      });
      return this.failedVerification(signedArtifact.artifact_id, errors, warnings);
    }

    // Check 3: Content hash matches
    const computedHash = this.hashContent(originalContent);
    if (computedHash !== signedArtifact.artifact_content_hash) {
      errors.push({
        error_code: "hash_mismatch",
        message: "Artifact content has been modified since signing",
        severity: "critical",
      });
      return this.failedVerification(signedArtifact.artifact_id, errors, warnings);
    }

    // Check 4: Verify signature cryptographically
    const publicKey = this.trustedKeys.get(signedArtifact.signer_key_id)!;
    const verify = crypto.createVerify("sha256");
    verify.update(signedArtifact.artifact_content_hash);

    let signatureValid = false;
    try {
      signatureValid = verify.verify(publicKey, signedArtifact.signature, "hex");
    } catch (e: any) {
      errors.push({
        error_code: "signature_invalid",
        message: `Signature verification failed: ${e.message}`,
        severity: "critical",
      });
      return this.failedVerification(signedArtifact.artifact_id, errors, warnings);
    }

    if (!signatureValid) {
      errors.push({
        error_code: "signature_invalid",
        message: "Cryptographic signature verification failed",
        severity: "critical",
      });
      return this.failedVerification(signedArtifact.artifact_id, errors, warnings);
    }

    // Warnings for timestamp staleness
    const signedTime = new Date(signedArtifact.signed_at);
    const ageMs = Date.now() - signedTime.getTime();
    const ageDays = ageMs / (1000 * 60 * 60 * 24);

    if (ageDays > 365) {
      warnings.push(`Signature is ${ageDays.toFixed(0)} days old`);
    }

    // Success
    return {
      verification_id: uuidv4(),
      artifact_id: signedArtifact.artifact_id,
      verified: true,
      signature_valid: true,
      key_trusted: true,
      verification_timestamp: new Date().toISOString(),
      verification_method: "public_key",
      errors: [],
      warnings,
    };
  }

  verifyMultiple(
    signedArtifacts: Array<{
      signed: SignedArtifact;
      content: Record<string, any>;
    }>
  ): VerificationResult[] {
    return signedArtifacts.map((artifact) =>
      this.verifySignature(artifact.signed, artifact.content)
    );
  }

  private hashContent(content: Record<string, any>): string {
    const jsonString = JSON.stringify(content, Object.keys(content).sort());
    return crypto.createHash("sha256").update(jsonString).digest("hex");
  }

  private failedVerification(
    artifactId: string,
    errors: VerificationError[],
    warnings: string[]
  ): VerificationResult {
    return {
      verification_id: uuidv4(),
      artifact_id: artifactId,
      verified: false,
      signature_valid: errors.some((e) => e.error_code === "signature_invalid")
        ? false
        : undefined,
      key_trusted: errors.some((e) => e.error_code === "key_not_trusted")
        ? false
        : undefined,
      verification_timestamp: new Date().toISOString(),
      verification_method: "public_key",
      errors,
      warnings,
    } as VerificationResult;
  }
}

export function createVerifier(): SignatureVerifier {
  return new SignatureVerifier();
}
