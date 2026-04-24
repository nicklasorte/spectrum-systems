import { PipelineIntegrationHub } from "@/src/integration/artifact-pipeline-integration";
import { ControlLoopEngine } from "@/src/governance/control-loop-engine";
import { ingestTranscript } from "../mvp-1/transcript-ingestor";
import { assembleContextBundle } from "../mvp-2/context-bundle-assembler";
import { runIngestionEvalGate } from "../mvp-3/ingestion-eval-gate";
import { extractMeetingMinutes } from "../mvp-4/minutes-extraction-agent";
import { extractIssues } from "../mvp-5/issue-extraction-agent";
import { runExtractionEvalGate } from "../mvp-6/extraction-eval-gate";
import { structureIssuesForPaper } from "../mvp-7/issue-structuring";
import { generatePaperDraft } from "../mvp-8/paper-draft-generator";
import { runDraftEvalGate } from "../mvp-9/draft-eval-gate";
import { emitHumanReviewRequest, submitReview } from "../mvp-10/human-review-gate";
import { integrateRevisions } from "../mvp-11/revision-integrator";
import { formatPaperForPublication } from "../mvp-12/publication-formatter";
import { runGOV10Certification } from "../mvp-13/gov10-certification";
import { v4 as uuidv4 } from "uuid";

export interface MVPStageOutput {
  mvp_name: string;
  artifact: any;
  sli_measurements: Record<string, number>;
  lineage_edges: Array<{ sourceId: string; targetId: string; relationship: string }>;
  decision_gate?: string; // "allow" | "warn" | "freeze" | "block"
}

export class PipelineConnector {
  private hub?: PipelineIntegrationHub;
  private controlLoop?: ControlLoopEngine;
  private traceId: string;

  constructor(hub?: PipelineIntegrationHub, controlLoop?: ControlLoopEngine) {
    this.hub = hub;
    this.controlLoop = controlLoop;
    this.traceId = uuidv4();
  }

  async mvp1_transcript_ingestion(rawText: string, sourceFile: string): Promise<MVPStageOutput> {
    const startTime = Date.now();
    const result = await ingestTranscript({ raw_text: rawText, source_file: sourceFile });

    if (!result.success) {
      throw new Error(`MVP-1 failed: ${result.error_codes?.join(", ")}`);
    }

    const sliMeasurements: Record<string, number> = {
      transcription_latency: Date.now() - startTime,
      segment_count: result.transcript_artifact?.outputs?.metadata?.segment_count ?? 0,
    };

    const output: MVPStageOutput = {
      mvp_name: "MVP-1",
      artifact: result.transcript_artifact,
      sli_measurements: sliMeasurements,
      lineage_edges: [],
    };

    if (this.hub) {
      await this.hub.recordMVPOutput("MVP-1", output.artifact, sliMeasurements);
    }

    return output;
  }

  async mvp2_context_bundle(transcriptArtifact: any): Promise<MVPStageOutput> {
    const result = await assembleContextBundle(transcriptArtifact);

    const sliMeasurements: Record<string, number> = {
      manifest_hash_present: result.context_bundle?.metadata?.assembly_manifest_hash ? 1 : 0,
    };

    const output: MVPStageOutput = {
      mvp_name: "MVP-2",
      artifact: result.context_bundle,
      sli_measurements: sliMeasurements,
      lineage_edges: [],
    };

    if (this.hub) {
      await this.hub.recordMVPOutput("MVP-2", output.artifact, sliMeasurements);
    }

    return output;
  }

  async mvp3_eval_gate(transcriptArtifact: any, contextBundle: any): Promise<MVPStageOutput> {
    const result = await runIngestionEvalGate(transcriptArtifact, contextBundle);

    const rawDecision = result.control_decision?.decision;
    let decisionGate: string;
    if (rawDecision === "allow") {
      decisionGate = "allow";
    } else if (rawDecision === "require_review") {
      decisionGate = "warn";
    } else {
      decisionGate = "block";
    }

    const sliMeasurements: Record<string, number> = {
      pass_rate: result.eval_summary?.pass_rate ?? 0,
      eval_cases: result.eval_results?.length ?? 0,
    };

    const output: MVPStageOutput = {
      mvp_name: "MVP-3",
      artifact: result.control_decision,
      sli_measurements: sliMeasurements,
      lineage_edges: [],
      decision_gate: decisionGate,
    };

    if (this.hub) {
      await this.hub.recordMVPOutput("MVP-3", output.artifact, sliMeasurements);
    }

    return output;
  }

  async mvp13_certification(
    formattedPaperId: string,
    allEvalSummaries: any[],
    allExecutionRecords: any[]
  ): Promise<MVPStageOutput> {
    const result = await runGOV10Certification(formattedPaperId, allEvalSummaries, allExecutionRecords);

    const sliMeasurements: Record<string, number> = {
      certification_passed: result.done_certification_record?.status === "PASSED" ? 1 : 0,
    };

    const output: MVPStageOutput = {
      mvp_name: "MVP-13",
      artifact: result.done_certification_record,
      sli_measurements: sliMeasurements,
      lineage_edges: [],
      decision_gate: result.done_certification_record?.status === "PASSED" ? "allow" : "block",
    };

    if (this.hub) {
      await this.hub.recordMVPOutput("MVP-13", output.artifact, sliMeasurements);
    }

    return output;
  }
}
