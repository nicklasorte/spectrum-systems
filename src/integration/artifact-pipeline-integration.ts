import { PostgresStorageBackend } from "@/src/artifact-store/postgres-backend";
import { SLIBackend } from "@/src/governance/sli-backend";
import { LineageGraph } from "@/src/governance/lineage-graph";
import { v4 as uuidv4 } from "uuid";

/**
 * Artifact Pipeline Integration
 * Connects MVPs to Phase 2 storage and Phase 3 governance
 */

export class PipelineIntegrationHub {
  private storage: PostgresStorageBackend;
  private sliBackend: SLIBackend;
  private lineageGraph: LineageGraph;

  constructor(
    storage: PostgresStorageBackend,
    sliBackend: SLIBackend,
    lineageGraph: LineageGraph
  ) {
    this.storage = storage;
    this.sliBackend = sliBackend;
    this.lineageGraph = lineageGraph;
  }

  /**
   * Called by each MVP after artifact generation
   * Records artifact, SLI measurements, lineage edges
   */
  async recordMVPOutput(
    mvpName: string,
    artifact: any,
    sliMeasurements?: Record<string, number>,
    lineageEdges?: Array<{ sourceId: string; targetId: string; relationship: string }>
  ): Promise<void> {
    const traceId = artifact.trace?.trace_id || uuidv4();

    // 1. Store artifact durably
    await this.storage.store(artifact);

    // 2. Record audit entry
    await this.storage.writeAuditEntry(
      artifact.artifact_id,
      `${mvpName}_output`,
      "pass",
      ["artifact_generated"],
      mvpName,
      { artifact_kind: artifact.artifact_kind }
    );

    // 3. Record SLI measurements
    if (sliMeasurements) {
      for (const [sliName, value] of Object.entries(sliMeasurements)) {
        await this.sliBackend.recordMeasurement(
          sliName,
          value,
          artifact.artifact_id,
          { mvp: mvpName },
          traceId
        );
      }
    }

    // 4. Record lineage edges
    if (lineageEdges) {
      for (const edge of lineageEdges) {
        await this.lineageGraph.recordLineageEdge(
          edge.sourceId,
          edge.targetId,
          edge.relationship as any
        );
      }
    }
  }

  /**
   * Called at MVP-13 (certification) to check control signals
   * Returns list of blocking signals that prevent release
   */
  async checkReleaseGates(artifactId: string): Promise<{
    allowed: boolean;
    blockedBy: string[];
    warnings: string[];
  }> {
    // Query Phase 3 governance for blocking conditions
    const blockedBy: string[] = [];
    const warnings: string[] = [];

    // Example: check if eval_pass_rate SLI is below threshold
    // (In real implementation, would query SLO status)
    const recentAlerts = []; // await sliBackend.getActiveAlerts()

    if (recentAlerts.length > 0) {
      warnings.push("active_sli_alerts");
    }

    return {
      allowed: blockedBy.length === 0,
      blockedBy,
      warnings,
    };
  }
}
