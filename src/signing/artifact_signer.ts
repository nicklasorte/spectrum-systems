/**
 * Artifact Signer
 * Cryptographic signing of artifacts for supply-chain integrity
 */

import { v4 as uuidv4 } from "uuid";
import crypto from "crypto";

export interface SignedArtifact {
  artifact_id: string;
  artifact_kind: string;
  artifact_content_hash: string;
  signature: string;
  signature_algorithm: "RSA-SHA256" | "ECDSA-SHA256";
  signer_key_id: string;
  signed_at: string;
  signed_by: string;
}

export interface ArtifactSignature {
  signature_id: string;
  artifact_id: string;
  artifact_hash: string;
  signature: string;
  algorithm: "RSA-SHA256" | "ECDSA-SHA256";
  signer_key_id: string;
  created_at: string;
  created_by: string;
}

export class ArtifactSigner {
  private signerKeyId: string;
  private signingKey: crypto.KeyObject;
  private createdBy: string;

  constructor(
    signerKeyId: string,
    signingKey: crypto.KeyObject,
    createdBy: string
  ) {
    this.signerKeyId = signerKeyId;
    this.signingKey = signingKey;
    this.createdBy = createdBy;
  }

  signArtifact(
    artifactId: string,
    artifactKind: string,
    artifactContent: Record<string, any>
  ): SignedArtifact {
    // Create hash of artifact content
    const contentHash = this.hashContent(artifactContent);

    // Sign the hash
    const sign = crypto.createSign("sha256");
    sign.update(contentHash);
    const signature = sign.sign(this.signingKey, "hex");

    return {
      artifact_id: artifactId,
      artifact_kind: artifactKind,
      artifact_content_hash: contentHash,
      signature,
      signature_algorithm: "RSA-SHA256",
      signer_key_id: this.signerKeyId,
      signed_at: new Date().toISOString(),
      signed_by: this.createdBy,
    };
  }

  signMultiple(
    artifacts: Array<{
      artifact_id: string;
      artifact_kind: string;
      content: Record<string, any>;
    }>
  ): SignedArtifact[] {
    return artifacts.map((artifact) =>
      this.signArtifact(
        artifact.artifact_id,
        artifact.artifact_kind,
        artifact.content
      )
    );
  }

  createSignatureRecord(
    artifactId: string,
    artifactContent: Record<string, any>
  ): ArtifactSignature {
    const contentHash = this.hashContent(artifactContent);
    const sign = crypto.createSign("sha256");
    sign.update(contentHash);
    const signature = sign.sign(this.signingKey, "hex");

    return {
      signature_id: uuidv4(),
      artifact_id: artifactId,
      artifact_hash: contentHash,
      signature,
      algorithm: "RSA-SHA256",
      signer_key_id: this.signerKeyId,
      created_at: new Date().toISOString(),
      created_by: this.createdBy,
    };
  }

  private hashContent(content: Record<string, any>): string {
    const jsonString = JSON.stringify(content, Object.keys(content).sort());
    return crypto.createHash("sha256").update(jsonString).digest("hex");
  }
}

export function generateSigningKeyPair(): {
  publicKey: crypto.KeyObject;
  privateKey: crypto.KeyObject;
} {
  const { publicKey, privateKey } = crypto.generateKeyPairSync("rsa", {
    modulusLength: 2048,
    publicKeyEncoding: { type: "spki", format: "pem" },
    privateKeyEncoding: { type: "pkcs8", format: "pem" },
  });

  // Re-import to get KeyObject types
  const pub = crypto.createPublicKey(publicKey);
  const priv = crypto.createPrivateKey(privateKey);

  return { publicKey: pub, privateKey: priv };
}

export function createSigner(
  signerKeyId: string,
  signingKey: crypto.KeyObject,
  signerIdentity: string
): ArtifactSigner {
  return new ArtifactSigner(signerKeyId, signingKey, signerIdentity);
}
