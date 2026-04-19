/**
 * Unit tests for Signed Provenance & SLSA (Cluster B)
 */

import {
  generateSigningKeyPair,
  createSigner,
} from "../../../src/signing/artifact_signer";
import { createVerifier } from "../../../src/signing/signature_verifier";
import { createSLSABuilder } from "../../../src/slsa/slsa_builder";
import {
  createSignatureVerificationGate,
} from "../../../src/signing/signature_verification_gate";
import {
  createSignatureAuditLog,
} from "../../../src/audit/signature_audit_log";
import { v4 as uuidv4 } from "uuid";

describe("Artifact Signing", () => {
  test("generateSigningKeyPair creates RSA key pair", () => {
    const { publicKey, privateKey } = generateSigningKeyPair();

    expect(publicKey).toBeDefined();
    expect(privateKey).toBeDefined();
    expect(publicKey.asymmetricKeyType).toBe("rsa");
    expect(privateKey.asymmetricKeyType).toBe("rsa");
  });

  test("createSigner signs artifacts", () => {
    const { publicKey, privateKey } = generateSigningKeyPair();
    const signer = createSigner("key-1", privateKey, "test-signer");

    const artifact = {
      artifact_id: uuidv4(),
      artifact_kind: "test",
      content: { data: "test", value: 123 },
    };

    const signed = signer.signArtifact(
      artifact.artifact_id,
      artifact.artifact_kind,
      artifact.content
    );

    expect(signed.artifact_id).toBe(artifact.artifact_id);
    expect(signed.signature).toBeDefined();
    expect(signed.signer_key_id).toBe("key-1");
    expect(signed.signature_algorithm).toBe("RSA-SHA256");
  });

  test("createSigner signs multiple artifacts", () => {
    const { publicKey, privateKey } = generateSigningKeyPair();
    const signer = createSigner("key-1", privateKey, "test-signer");

    const artifacts = [
      { artifact_id: uuidv4(), artifact_kind: "type1", content: { a: 1 } },
      { artifact_id: uuidv4(), artifact_kind: "type2", content: { b: 2 } },
    ];

    const signed = signer.signMultiple(
      artifacts.map((a) => ({
        artifact_id: a.artifact_id,
        artifact_kind: a.artifact_kind,
        content: a.content,
      }))
    );

    expect(signed).toHaveLength(2);
    expect(signed[0].artifact_id).toBe(artifacts[0].artifact_id);
    expect(signed[1].artifact_id).toBe(artifacts[1].artifact_id);
  });

  test("createSignatureRecord creates ArtifactSignature", () => {
    const { publicKey, privateKey } = generateSigningKeyPair();
    const signer = createSigner("key-1", privateKey, "test-signer");

    const record = signer.createSignatureRecord(uuidv4(), { test: "data" });

    expect(record.signature_id).toBeDefined();
    expect(record.artifact_hash).toBeDefined();
    expect(record.signature).toBeDefined();
    expect(record.algorithm).toBe("RSA-SHA256");
  });
});

describe("Signature Verification", () => {
  test("verifySignature approves valid signature", () => {
    const { publicKey, privateKey } = generateSigningKeyPair();
    const signer = createSigner("key-1", privateKey, "signer");
    const verifier = createVerifier();
    verifier.registerTrustedKey("key-1", publicKey);

    const content = { data: "test", value: 123 };
    const signed = signer.signArtifact(uuidv4(), "test", content);

    const result = verifier.verifySignature(signed, content);

    expect(result.verified).toBe(true);
    expect(result.signature_valid).toBe(true);
    expect(result.key_trusted).toBe(true);
  });

  test("verifySignature rejects untrusted key", () => {
    const { publicKey, privateKey } = generateSigningKeyPair();
    const signer = createSigner("key-1", privateKey, "signer");
    const verifier = createVerifier();
    // Don't register the key - it's untrusted

    const content = { data: "test" };
    const signed = signer.signArtifact(uuidv4(), "test", content);

    const result = verifier.verifySignature(signed, content);

    expect(result.verified).toBe(false);
    expect(result.key_trusted).toBe(false);
  });

  test("verifySignature rejects modified content", () => {
    const { publicKey, privateKey } = generateSigningKeyPair();
    const signer = createSigner("key-1", privateKey, "signer");
    const verifier = createVerifier();
    verifier.registerTrustedKey("key-1", publicKey);

    const content = { data: "test" };
    const signed = signer.signArtifact(uuidv4(), "test", content);

    // Modify content
    const modifiedContent = { data: "modified" };

    const result = verifier.verifySignature(signed, modifiedContent);

    expect(result.verified).toBe(false);
    expect(result.errors.some((e) => e.error_code === "hash_mismatch")).toBe(
      true
    );
  });

  test("verifySignature rejects missing signature", () => {
    const { publicKey, privateKey } = generateSigningKeyPair();
    const signer = createSigner("key-1", privateKey, "signer");
    const verifier = createVerifier();
    verifier.registerTrustedKey("key-1", publicKey);

    const content = { data: "test" };
    const signed = signer.signArtifact(uuidv4(), "test", content);
    signed.signature = ""; // Empty signature

    const result = verifier.verifySignature(signed, content);

    expect(result.verified).toBe(false);
    expect(result.errors.some((e) => e.error_code === "missing_signature")).toBe(
      true
    );
  });

  test("verifyMultiple verifies batch of signatures", () => {
    const { publicKey, privateKey } = generateSigningKeyPair();
    const signer = createSigner("key-1", privateKey, "signer");
    const verifier = createVerifier();
    verifier.registerTrustedKey("key-1", publicKey);

    const artifacts = [
      { id: uuidv4(), content: { a: 1 } },
      { id: uuidv4(), content: { b: 2 } },
    ];

    const signed = artifacts.map((a) =>
      signer.signArtifact(a.id, "test", a.content)
    );

    const results = verifier.verifyMultiple(
      signed.map((s, i) => ({ signed: s, content: artifacts[i].content }))
    );

    expect(results).toHaveLength(2);
    expect(results.every((r) => r.verified)).toBe(true);
  });
});

describe("SLSA Compliance", () => {
  test("createSLSABuilder creates provenance statement", () => {
    const builder = createSLSABuilder("builder-1");

    const provenance = builder.createProvenanceStatement(
      uuidv4(),
      "docker-build",
      { image: "ubuntu:20.04" },
      [{ uri: "github.com/repo/file.txt", digest: { "sha256": "abc123" } }]
    );

    expect(provenance.build_definition.builder_id).toBe("builder-1");
    expect(provenance.build_definition.build_type).toBe("docker-build");
    expect(provenance.materials).toHaveLength(1);
  });

  test("verifySLSACompliance checks requirements", () => {
    const builder = createSLSABuilder("builder-1");
    const artifactId = uuidv4();

    builder.createProvenanceStatement(
      artifactId,
      "docker-build",
      { image: "ubuntu:20.04" },
      [{ uri: "github.com/repo/file.txt", digest: { "sha256": "abc123" } }]
    );

    const compliance = builder.verifySLSACompliance(artifactId, true);

    expect(compliance.level).toBe(3);
    expect(compliance.provenance_available).toBe(true);
    expect(compliance.provenance_signed).toBe(true);
    expect(compliance.build_as_code).toBe(true);
  });

  test("verifySLSACompliance detects gaps", () => {
    const builder = createSLSABuilder("builder-1");
    const artifactId = uuidv4();

    const compliance = builder.verifySLSACompliance(artifactId, false);

    expect(compliance.provenance_available).toBe(false);
    expect(compliance.gaps.length).toBeGreaterThan(0);
  });

  test("exportProvenanceAsJSON exports statement", () => {
    const builder = createSLSABuilder("builder-1");
    const artifactId = uuidv4();

    builder.createProvenanceStatement(
      artifactId,
      "build-type",
      { param: "value" },
      []
    );

    const json = builder.exportProvenanceAsJSON(artifactId);

    expect(json).toBeDefined();
    expect(JSON.parse(json!)).toHaveProperty("build_definition");
  });
});

describe("Signature Verification Gate", () => {
  test("checkPromotionSignatures approves valid artifacts", () => {
    const { publicKey, privateKey } = generateSigningKeyPair();
    const signer = createSigner("key-1", privateKey, "signer");
    const verifier = createVerifier();
    verifier.registerTrustedKey("key-1", publicKey);
    const slsaBuilder = createSLSABuilder("builder-1");
    const gate = createSignatureVerificationGate(verifier, slsaBuilder);

    const content = { data: "test" };
    const signed = signer.signArtifact(uuidv4(), "test", content);
    const artifactId = signed.artifact_id;

    slsaBuilder.createProvenanceStatement(
      artifactId,
      "test-build",
      {},
      []
    );

    const result = gate.checkPromotionSignatures(artifactId, signed, content);

    expect(result.promotion_approved).toBe(true);
    expect(result.signature_verification.verified).toBe(true);
  });

  test("checkPromotionSignatures blocks invalid signatures", () => {
    const { publicKey, privateKey } = generateSigningKeyPair();
    const signer = createSigner("key-1", privateKey, "signer");
    const verifier = createVerifier();
    // Don't register key - untrusted
    const slsaBuilder = createSLSABuilder("builder-1");
    const gate = createSignatureVerificationGate(verifier, slsaBuilder);

    const content = { data: "test" };
    const signed = signer.signArtifact(uuidv4(), "test", content);

    const result = gate.checkPromotionSignatures(
      signed.artifact_id,
      signed,
      content
    );

    expect(result.promotion_approved).toBe(false);
    expect(result.failed_checks.length).toBeGreaterThan(0);
  });

  test("generateVerificationReport formats report", () => {
    const { publicKey, privateKey } = generateSigningKeyPair();
    const signer = createSigner("key-1", privateKey, "signer");
    const verifier = createVerifier();
    verifier.registerTrustedKey("key-1", publicKey);
    const slsaBuilder = createSLSABuilder("builder-1");
    const gate = createSignatureVerificationGate(verifier, slsaBuilder);

    const content = { data: "test" };
    const signed = signer.signArtifact(uuidv4(), "test", content);

    const checkResult = gate.checkPromotionSignatures(
      signed.artifact_id,
      signed,
      content
    );
    const report = gate.generateVerificationReport(checkResult);

    expect(report).toContain("Signature Verification Report");
    expect(report).toContain(checkResult.artifact_id);
  });
});

describe("Signature Audit Log", () => {
  test("recordSigning logs signing operations", () => {
    const log = createSignatureAuditLog();
    const { publicKey, privateKey } = generateSigningKeyPair();
    const signer = createSigner("key-1", privateKey, "signer");

    const signed = signer.signArtifact(uuidv4(), "test", { data: "test" });

    const entry = log.recordSigning(
      signed.artifact_id,
      "signer",
      signed,
      "success"
    );

    expect(entry.operation).toBe("sign");
    expect(entry.result).toBe("success");
    expect(entry.actor).toBe("signer");
  });

  test("recordVerification logs verification operations", () => {
    const { publicKey, privateKey } = generateSigningKeyPair();
    const signer = createSigner("key-1", privateKey, "signer");
    const verifier = createVerifier();
    verifier.registerTrustedKey("key-1", publicKey);
    const log = createSignatureAuditLog();

    const content = { data: "test" };
    const signed = signer.signArtifact(uuidv4(), "test", content);
    const verification = verifier.verifySignature(signed, content);

    const entry = log.recordVerification(
      signed.artifact_id,
      "verifier",
      verification
    );

    expect(entry.operation).toBe("verify");
    expect(entry.result).toBe("success");
  });

  test("getSummary generates audit summary", () => {
    const { publicKey, privateKey } = generateSigningKeyPair();
    const signer = createSigner("key-1", privateKey, "signer");
    const log = createSignatureAuditLog();

    const signed = signer.signArtifact(uuidv4(), "test", { data: "test" });
    log.recordSigning(signed.artifact_id, "signer", signed, "success");

    const summary = log.getSummary();

    expect(summary.total_entries).toBeGreaterThan(0);
    expect(summary.operations_by_type["sign"]).toBeGreaterThan(0);
    expect(summary.success_rate).toBeGreaterThan(0);
  });

  test("getArtifactHistory filters by artifact", () => {
    const { publicKey, privateKey } = generateSigningKeyPair();
    const signer = createSigner("key-1", privateKey, "signer");
    const log = createSignatureAuditLog();

    const artifactId = uuidv4();
    const signed = signer.signArtifact(artifactId, "test", { data: "test" });
    log.recordSigning(artifactId, "signer", signed, "success");

    const history = log.getArtifactHistory(artifactId);

    expect(history.length).toBeGreaterThan(0);
    expect(history.every((e) => e.artifact_id === artifactId)).toBe(true);
  });

  test("exportAsJSON exports audit trail", () => {
    const { publicKey, privateKey } = generateSigningKeyPair();
    const signer = createSigner("key-1", privateKey, "signer");
    const log = createSignatureAuditLog();

    const signed = signer.signArtifact(uuidv4(), "test", { data: "test" });
    log.recordSigning(signed.artifact_id, "signer", signed, "success");

    const json = log.exportAsJSON();
    const parsed = JSON.parse(json);

    expect(Array.isArray(parsed)).toBe(true);
    expect(parsed[0].operation).toBe("sign");
  });
});
