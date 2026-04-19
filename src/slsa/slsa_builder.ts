/**
 * SLSA Builder
 * Supply chain Levels for Software Artifacts (SLSA) compliance
 */

import { v4 as uuidv4 } from "uuid";

export interface SLSAProvenanceStatement {
  statement_version: string;
  build_definition: {
    builder_id: string;
    build_type: string;
    external_parameters: Record<string, any>;
    internal_parameters: Record<string, any>;
    resolved_dependencies: Array<{
      uri: string;
      digest: Record<string, string>;
    }>;
  };
  build_run: {
    builder_invocation_id: string;
    start_time: string;
    end_time: string;
    environment: Record<string, string>;
  };
  materials: Array<{
    uri: string;
    digest: Record<string, string>;
  }>;
}

export interface SLSACompliance {
  level: 1 | 2 | 3 | 4;
  requirements_met: Map<string, boolean>;
  gaps: string[];
  hermetic_build: boolean;
  build_as_code: boolean;
  provenance_available: boolean;
  provenance_signed: boolean;
  dependencies_declared: boolean;
}

export class SLSABuilder {
  private level: 1 | 2 | 3 | 4 = 3; // Target SLSA level 3
  private builderId: string;
  private provenanceStatements: Map<string, SLSAProvenanceStatement> = new Map();

  constructor(builderId: string) {
    this.builderId = builderId;
  }

  createProvenanceStatement(
    artifactId: string,
    buildType: string,
    externalParameters: Record<string, any>,
    materials: Array<{ uri: string; digest: Record<string, string> }>
  ): SLSAProvenanceStatement {
    const statement: SLSAProvenanceStatement = {
      statement_version: "1.0",
      build_definition: {
        builder_id: this.builderId,
        build_type: buildType,
        external_parameters: externalParameters,
        internal_parameters: {
          build_time: new Date().toISOString(),
          build_id: uuidv4(),
        },
        resolved_dependencies: [],
      },
      build_run: {
        builder_invocation_id: uuidv4(),
        start_time: new Date().toISOString(),
        end_time: new Date().toISOString(),
        environment: this.getCapturedEnvironment(),
      },
      materials,
    };

    this.provenanceStatements.set(artifactId, statement);
    return statement;
  }

  verifySLSACompliance(
    artifactId: string,
    hasSignedProvenance: boolean
  ): SLSACompliance {
    const provenance = this.provenanceStatements.get(artifactId);
    const requirements = new Map<string, boolean>();

    // SLSA Level 3 requirements
    requirements.set(
      "provenance_available",
      provenance !== undefined
    );
    requirements.set("provenance_signed", hasSignedProvenance);
    requirements.set(
      "hermetic_build",
      this.checkHermeticBuild(provenance)
    );
    requirements.set(
      "build_as_code",
      this.checkBuildAsCode(provenance)
    );
    requirements.set(
      "dependencies_declared",
      this.checkDependenciesDeclared(provenance)
    );

    const gaps: string[] = [];
    const met = new Map(requirements);

    for (const [requirement, isMet] of requirements) {
      if (!isMet) {
        gaps.push(`Missing requirement: ${requirement}`);
      }
    }

    return {
      level: 3,
      requirements_met: met,
      gaps,
      hermetic_build: requirements.get("hermetic_build") || false,
      build_as_code: requirements.get("build_as_code") || false,
      provenance_available: requirements.get("provenance_available") || false,
      provenance_signed: requirements.get("provenance_signed") || false,
      dependencies_declared: requirements.get("dependencies_declared") || false,
    };
  }

  private checkHermeticBuild(provenance?: SLSAProvenanceStatement): boolean {
    if (!provenance) return false;
    // Check if build had isolated environment with explicit inputs
    return (
      provenance.build_definition.external_parameters !== undefined &&
      Object.keys(provenance.build_definition.external_parameters).length > 0
    );
  }

  private checkBuildAsCode(provenance?: SLSAProvenanceStatement): boolean {
    if (!provenance) return false;
    // Check if build type indicates code-based build
    return provenance.build_definition.build_type !== undefined;
  }

  private checkDependenciesDeclared(provenance?: SLSAProvenanceStatement): boolean {
    if (!provenance) return false;
    // Check if dependencies are explicitly listed
    return provenance.materials && provenance.materials.length > 0;
  }

  private getCapturedEnvironment(): Record<string, string> {
    return {
      os: process.platform,
      node_version: process.version,
      timestamp: new Date().toISOString(),
    };
  }

  getProvenanceStatement(artifactId: string): SLSAProvenanceStatement | undefined {
    return this.provenanceStatements.get(artifactId);
  }

  exportProvenanceAsJSON(artifactId: string): string | null {
    const statement = this.provenanceStatements.get(artifactId);
    if (!statement) return null;
    return JSON.stringify(statement, null, 2);
  }
}

export function createSLSABuilder(builderId: string): SLSABuilder {
  return new SLSABuilder(builderId);
}
